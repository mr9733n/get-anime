# db_transfer.py
import os, hmac, time, json, gzip, shutil, socket, struct, asyncio, sqlite3, hashlib, aiofiles, argparse

from pathlib import Path
from nacl.secret import SecretBox
from nacl.public import PrivateKey, PublicKey
from nacl import bindings as nacl_bindings
from typing import Optional, Callable, Dict, Any

try:
    from zeroconf import Zeroconf, ServiceInfo
except Exception:
    Zeroconf = None
    ServiceInfo = None


# --- Конфиги по умолчанию ---
MDNS_SERVICE_TYPE = "_playersync._tcp.local."
DEFAULT_PORT = 8765
DEFAULT_CHUNK = 2 * 1024 * 1024  # 2 MiB
TOFU_FILE: Path = Path.home() / ".player_db_trust.json"


# --- Вспомогательные функции ---
def hkdf_extract(salt: bytes, ikm: bytes) -> bytes:
    return hmac.new(salt or b'\x00'*32, ikm, hashlib.sha256).digest()

def hkdf_expand(prk: bytes, info: bytes, length: int) -> bytes:
    # простой HKDF expand (RFC5869)
    hash_len = hashlib.sha256().digest_size
    n = (length + hash_len - 1) // hash_len
    okm = b""
    t = b""
    for i in range(1, n+1):
        t = hmac.new(prk, t + info + bytes([i]), hashlib.sha256).digest()
        okm += t
    return okm[:length]

def hkdf(salt: bytes, ikm: bytes, info: bytes, length: int = 32) -> bytes:
    prk = hkdf_extract(salt, ikm)
    return hkdf_expand(prk, info, length)

def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def compute_sas(pub_a: bytes, pub_b: bytes, digits: int = 6) -> str:
    x = pub_a + pub_b if pub_a < pub_b else pub_b + pub_a
    h = hashlib.sha256(x).digest()
    return f"{int.from_bytes(h[:4],'big') % 1_000_000:06d}"

def sqlite_make_snapshot(src_path: str, dst_path: str):
    src = sqlite3.connect(src_path)
    dst = sqlite3.connect(dst_path)
    with dst:
        src.backup(dst)
    src.close()
    dst.close()

def load_tofu() -> Dict[str, Any]:
    """
    Безопасно читает TOFU JSON.
    Возвращает пустой словарь при отсутствии файла или ошибке парсинга.
    """
    try:
        if not TOFU_FILE.exists():
            return {}
        # Явно открыть через with
        with TOFU_FILE.open("r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError:
        # Повреждённый JSON — можно переименовать файл для отладки
        # TOFU_FILE.rename(TOFU_FILE.with_suffix(".corrupt"))
        return {}
    except Exception as e:
        # Здесь логируй e если нужен
        return {}

def save_tofu(data: Dict[str, Any]) -> None:
    """
    Безопасно сохраняет TOFU:
     - записывает в временный файл в той же папке,
     - делает flush+fsync чтобы данные гарантированно попали на диск,
     - атомарно переименовывает temp -> final (os.replace).
     - выставляет права 0o600 (если поддерживается платформой).
    """
    try:
        TOFU_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = TOFU_FILE.with_suffix(".tmp")
        # Открываем и записываем
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.flush()
            # гарантируем запись на диск (работает на POSIX/Windows)
            try:
                os.fsync(f.fileno())
            except OSError:
                # fsync может не поддерживаться в некоторых окружениях — игнорируем
                pass
        # атомарная замена
        os.replace(tmp, TOFU_FILE)
        # попытка выставить права 600 — полезно для приватности
        try:
            TOFU_FILE.chmod(0o600)
        except Exception:
            pass
    except Exception as e:
        # Логировать e при необходимости
        # нельзя оставлять tmp бесконтрольно — можно попытаться удалить
        try:
            if tmp.exists():
                tmp.unlink()
        except Exception:
            pass

def make_salt(pub_a: bytes, pub_b: bytes) -> bytes:
    if pub_a < pub_b:
        x = pub_a + pub_b
    else:
        x = pub_b + pub_a
    return hashlib.sha256(x).digest()

# --- Класс Receiver ---
class DBReceiver:
    def __init__(self, *,
                 host: str = "0.0.0.0",
                 port: int = DEFAULT_PORT,
                 chunk_dir: str = "./incoming",
                 tmp_name: str = "incoming.db.tmp",
                 final_name: str = "player.db",
                 mdns_advertise: bool = True,
                 mdns_name: str | None = None,
                 on_progress: Optional[Callable[[int, int], None]] = None,
                 sas_confirm: Optional[Callable[[str, str], bool]] = None,
                 on_done: Optional[Callable[[str], None]] = None,
                 allow_resume: bool = True,
                 verify_chunks: bool = False,
                 log: Optional[Callable[[str], None]] = None):
        self.host = host
        self.port = port
        self.chunk_dir = Path(chunk_dir)
        self.chunk_dir.mkdir(parents=True, exist_ok=True)
        self.tmp_name = tmp_name
        self.final_name = final_name
        self.on_progress = on_progress
        self.sas_confirm = sas_confirm
        self.on_done = on_done
        self._server = None
        self._running = False
        self.mdns_advertise = mdns_advertise
        self.mdns_name = mdns_name or f"PlayerSync-{socket.gethostname()}"
        self._zc = None
        self._mdns_info = None
        self.allow_resume = allow_resume
        self.verify_chunks = verify_chunks
        self._log_cb = log

    def _log(self, msg: str):
        if self._log_cb:
            self._log_cb(msg)
        else:
            print(msg)

    async def start_listen(self):
        self._server = await asyncio.start_server(self._handle_client, host=self.host, port=self.port)
        addr = self._server.sockets[0].getsockname()
        self._log(f"[receiver] listening on {addr}")
        # mDNS advertise
        if self.mdns_advertise and Zeroconf and ServiceInfo:
            try:
                # попытка взять «реальный» IP, не 127.0.0.1
                ip = None
                for s in self._server.sockets:
                    ip = s.getsockname()[0]
                    if ip and ip != "0.0.0.0":
                        break
                if not ip or ip == "0.0.0.0":
                    ip = socket.gethostbyname(socket.gethostname())  # best-effort

                self._zc = Zeroconf()
                props = {"name": self.mdns_name}
                self._mdns_info = ServiceInfo(
                    MDNS_SERVICE_TYPE,
                    f"{self.mdns_name}.{MDNS_SERVICE_TYPE}",
                    addresses=[socket.inet_aton(ip)],
                    port=self.port,
                    properties=props,
                )
                self._zc.register_service(self._mdns_info)
                self._log(f"[receiver] mDNS advertised: {self.mdns_name} @ {ip}:{self.port}")
            except Exception as e:
                self._log(f"[receiver] mDNS advertise failed: {e}")
        self._running = True
        async with self._server:
            await self._server.serve_forever()

    async def stop(self):
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            self._running = False
        # mDNS unreg
        try:
            if self._zc and self._mdns_info:
                self._zc.unregister_service(self._mdns_info)
        except Exception as e:
            self._log(f"[receiver] mDNS unregister failed: {type(e).__name__}: {e}")
        try:
            self._zc.close()
        except Exception:
            pass
        finally:
            self._zc = None
            self._mdns_info = None

    async def _handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        peer = writer.get_extra_info("peername")
        self._log(f"[receiver] connection from {peer}")
        # 1. read hello
        line = await reader.readline()
        if not line:
            self._log("[receiver] empty hello (client disconnected early)")
            writer.close(); await writer.wait_closed()
            return
        try:
            hello = json.loads(line.decode())
        except json.JSONDecodeError:
            self._log(f"[receiver] bad hello, not JSON: {line[:64]}")
            writer.close(); await writer.wait_closed()
            return

        gzip_mode = bool(hello.get("gzip"))
        file_size = int(hello.get("file_size", 0))
        chunk_size = int(hello.get("chunk_size", DEFAULT_CHUNK))

        # 2. receive sender pubkey (32 bytes)
        try:
            sender_pub = await reader.readexactly(32)
        except asyncio.IncompleteReadError:
            self._log("[receiver] disconnected before pubkey")
            writer.close();
            await writer.wait_closed()
            return
        # generate ephemeral keypair
        priv = PrivateKey.generate()
        pub = bytes(priv.public_key)
        # send our pub
        writer.write(pub); await writer.drain()

        # compute SAS and TOFU check
        sas = compute_sas(sender_pub, pub)
        sender_fp = sha256_hex(sender_pub)[:16]
        self._log(f"[receiver] SAS: {sas} (verify with sender)")

        # TOFU check: if known and matches, we can skip manual confirm
        tofu = load_tofu()
        trusted = tofu.get(sender_fp)

        if trusted:
            self._log(f"[receiver] trusted sender fingerprint {sender_fp} (TOFU)")
            confirmed = True
        else:
            if self.sas_confirm:
                self._log("[receiver] SAS: waiting for user confirmation…")
                loop = asyncio.get_running_loop()
                # Важное изменение: выносим подтверждение в thread executor
                confirmed = await loop.run_in_executor(None, lambda: bool(self.sas_confirm(sas, sender_fp)))
                self._log(f"[receiver] SAS: {'accepted' if confirmed else 'rejected'} by user")
            else:
                print("[receiver] please confirm SAS shown on sender device")
                input("Press Enter when user confirmed SAS (or Ctrl+C to cancel)...")
                confirmed = True
        if not confirmed:
            self._log("[receiver] SAS declined by user")
            writer.close(); await writer.wait_closed()
            return

        salt = make_salt(pub, sender_pub)
        is_sender_a = sender_pub < pub  # True, если отправитель — тот самый "A"

        # общий секрет (используем bytes(priv) для ясности)
        shared = nacl_bindings.crypto_scalarmult(bytes(priv), sender_pub)

        if is_sender_a:
            info = b"player-db-transfer:v1:a->b"  # поток идёт A->B к нам
        else:
            info = b"player-db-transfer:v1:b->a"  # поток идёт B->A к нам

        key_recv = hkdf(salt=salt, ikm=shared, info=info, length=32)
        box_recv = SecretBox(key_recv)

        # --- (необязательно) временный отладочный вывод: первые 4 байта ключа
        self._log(f"[receiver] key tag: {key_recv[:4].hex()}")
        # --- RESUME: check existing tmp ---
        tmp_path = self.chunk_dir / self.tmp_name
        resume_from = 0
        if gzip_mode:
            # Для gzip пока не поддерживаем resume — писать с нуля
            self._log("[receiver] gzip mode: resume disabled")
        else:
            tmp_path = self.chunk_dir / self.tmp_name
            if tmp_path.exists():
                try:
                    sz = os.path.getsize(tmp_path)
                    if 0 < sz < file_size and (sz % chunk_size == 0):
                        resume_from = sz
                        self._log(f"[receiver] resume possible from {resume_from} bytes")
                    else:
                        self._log("[receiver] resume not possible, removing bad tmp")
                        tmp_path.unlink(missing_ok=True)
                except Exception as e:
                    self._log(f"[receiver] resume check failed: {e}")
                    resume_from = 0

        # --- send resume_from to sender ---
        if not self.allow_resume or gzip_mode:
            resume_from = 0
        writer.write((json.dumps({"resume_from": resume_from}) + "\n").encode())
        await writer.drain()

        tmp_path = self.chunk_dir / self.tmp_name
        # если есть докачка — открываем в "append"
        mode = "ab" if resume_from else "wb"
        f = await aiofiles.open(tmp_path, mode)
        received = resume_from
        expected_seq = resume_from // chunk_size

        expected_sha = None

        try:
            while True:
                header = await reader.readexactly(4)
                typ = header.decode()
                if typ == "CHNK":
                    seq_bytes = await reader.readexactly(8)
                    seq = struct.unpack("!Q", seq_bytes)[0]
                    lng_bytes = await reader.readexactly(8)
                    l = struct.unpack("!Q", lng_bytes)[0]
                    enc = await reader.readexactly(l)
                    # decrypt
                    try:
                        plain = box_recv.decrypt(enc)
                        if seq != expected_seq:
                            self._log(f"[receiver] out-of-order chunk, expected: {expected_seq} got: {seq}")
                            break

                        await f.write(plain)
                        received += len(plain)
                        writer.write((json.dumps({"ack": seq}) + "\n").encode());
                        await writer.drain()
                        if self.on_progress:
                            self.on_progress(received, file_size)
                        expected_seq += 1
                    except Exception as e:
                        self._log(f"[receiver] decrypt error: {e}")
                        writer.write((json.dumps({"error":"decrypt"}) + "\n").encode()); await writer.drain()
                        break

                elif typ == "DONE":
                    sha_line = await reader.readline()
                    expected_sha = sha_line.decode().strip()
                    self._log(f"[receiver] DONE expected sha: {expected_sha}")
                    break
                else:
                    self._log(f"[receiver] unknown header: {typ}")
                    break
        except asyncio.IncompleteReadError:
            self._log(f"[receiver] connection closed unexpectedly during transfer")
        finally:
            await f.close()
            writer.close()
            try:
                await writer.wait_closed()
            except ConnectionResetError as e:
                self._log(f"[receiver] connection reset while closing: {e}")
            except OSError as e:
                self._log(f"[receiver] connection reset while closing: {e}")

            # verify sha (и при необходимости распаковка gzip)
            if gzip_mode:
                # --- gzip-ветка: распаковываем во временный .db и считаем SHA по распакованным данным ---

                sha = hashlib.sha256()
                # tmp_path сейчас указывает на gzip-файл (incoming.db.tmp, но он .gz внутри)
                db_tmp_path = tmp_path.with_suffix(".dbtmp")

                self._log(f"[receiver] gunzip {tmp_path} -> {db_tmp_path}")
                with gzip.open(tmp_path, "rb") as fin, open(db_tmp_path, "wb") as fout:
                    while True:
                        data = fin.read(1024 * 1024)
                        if not data:
                            break
                        fout.write(data)
                        sha.update(data)

                got = sha.hexdigest()
                self._log(f"[receiver] calculated sha (gunzipped): {got}")

                if expected_sha and got == expected_sha:
                    final = self.chunk_dir / self.final_name
                    os.replace(db_tmp_path, final)

                    # gzip-времянку можно удалить (если хочется)
                    try:
                        tmp_path.unlink()
                    except Exception:
                        pass

                    self._log(f"[receiver] saved DB to {final}")

                    # --- общий блок «успешного завершения» ---
                    if self.on_progress:
                        self.on_progress(file_size, file_size)
                    # уведомляем GUI о пути сохранения
                    if self.on_done:
                        try:
                            self.on_done(str(final))
                        except Exception:
                            pass
                    # persist TOFU if not existed
                    fp = sha256_hex(sender_pub)[:16]
                    tofu = load_tofu()
                    if fp not in tofu:
                        tofu[fp] = True
                        save_tofu(tofu)
                        self._log("[receiver] saved TOFU fingerprint")
                else:
                    self._log(f"[receiver] SHA mismatch or missing after gunzip; tmp kept at {db_tmp_path}")

            else:
                # --- обычная (не gzip) ветка — твой текущий код, чуть обёрнутый в else ---
                sha = hashlib.sha256()
                async with aiofiles.open(tmp_path, "rb") as fr:
                    while True:
                        data = await fr.read(1024 * 1024)
                        if not data:
                            break
                        sha.update(data)
                got = sha.hexdigest()
                self._log(f"[receiver] calculated sha: {got}")
                if expected_sha and got == expected_sha:
                    final = self.chunk_dir / self.final_name
                    os.replace(tmp_path, final)
                    self._log(f"[receiver] saved DB to {final}")

                    if self.on_progress:
                        self.on_progress(file_size, file_size)
                    # уведомляем GUI о пути сохранения
                    if self.on_done:
                        try:
                            self.on_done(str(final))
                        except Exception:
                            pass
                    # persist TOFU if not existed
                    fp = sha256_hex(sender_pub)[:16]
                    tofu = load_tofu()
                    if fp not in tofu:
                        tofu[fp] = True
                        save_tofu(tofu)
                        self._log("[receiver] saved TOFU fingerprint")
                else:
                    self._log(f"[receiver] SHA mismatch or missing; tmp kept at {tmp_path}")


# --- Класс Sender ---
class DBSender:
    def __init__(self, *,
                 chunk_size: int = DEFAULT_CHUNK,
                 throttle_kbps: Optional[int] = None,
                 on_progress: Optional[Callable[[int, int], None]] = None,
                 sas_confirm: Optional[Callable[[str, str], bool]] = None,
                 sas_info: Optional[Callable[[str, str], None]] = None,
                 log: Optional[Callable[[str], None]] = None,
                 use_gzip: bool = False,
                 vacuum_snapshot: bool = False):
        self.chunk_size = chunk_size
        self.throttle_kbps = throttle_kbps  # None/0 -> no limit
        self.on_progress = on_progress
        self.sas_confirm = sas_confirm
        self.sas_info = sas_info
        self._log_cb = log
        self.use_gzip = use_gzip
        self.vacuum_snapshot = vacuum_snapshot

    def _log(self, msg: str):
        if self._log_cb:
            self._log_cb(msg)
        else:
            print(msg)

    async def connect_and_send(self, host: str, port: int, src_db_path: str,
                               snapshot_path: str = "db_snapshot.sqlite", schema_version: str = "1"):
        # 1) make snapshot
        if not os.path.exists(snapshot_path):
            sqlite_make_snapshot(src_db_path, snapshot_path)

        if self.vacuum_snapshot:
            try:
                self._log(f"[sender] VACUUM snapshot {snapshot_path} ...")
                con = sqlite3.connect(snapshot_path)
                with con:
                    con.execute("PRAGMA optimize")
                    con.execute("VACUUM")
                con.close()
                self._log("[sender] VACUUM snapshot: done")
            except Exception as e:
                self._log(f"[sender] VACUUM snapshot failed: {e}")

        db_path = snapshot_path
        orig_size = os.path.getsize(db_path)

        if self.use_gzip:
            gz_path = snapshot_path + ".gz"  # или Path(...) / "db_snapshot.sqlite.gz"
            with open(db_path, "rb") as fin, gzip.open(gz_path, "wb") as fout:
                shutil.copyfileobj(fin, fout)
            xfer_path = gz_path
        else:
            xfer_path = db_path

        size = os.path.getsize(xfer_path)
        if self.use_gzip:
            if orig_size > 0:
                saved = (1.0 - size / orig_size) * 100.0
                self._log(
                    "[sender] gzip ratio: "
                    f"{orig_size / (1024*1024):.2f} MiB -> {size / (1024*1024):.2f} MiB "
                    f"({saved:.1f}% saved)"
                )
            else:
                self._log("[sender] gzip ratio: original size is 0?")

        # ===== SHA256 по ВСЕМУ снапшоту =====
        sha = hashlib.sha256()
        with open(snapshot_path, "rb") as ff:
            for block in iter(lambda: ff.read(1024 * 1024), b""):
                sha.update(block)
        full_sha_hex = sha.hexdigest()

        reader = writer = None
        last_err = None
        for _ in range(20):  # ~10 сек при интервале 0.5s
            try:
                reader, writer = await asyncio.open_connection(host, port)
                break
            except Exception as e:
                last_err = e
                await asyncio.sleep(0.5)
        if not reader:
            raise last_err or ConnectionError("Unable to connect")
        hello = {"role":"sender","schema_version":schema_version,"file_size":size,"chunk_size":self.chunk_size,"gzip": bool(self.use_gzip),}
        writer.write((json.dumps(hello) + "\n").encode()); await writer.drain()

        # send our ephemeral pubkey
        priv = PrivateKey.generate()
        pub = bytes(priv.public_key)
        writer.write(pub); await writer.drain()

        # receive receiver pubkey
        receiver_pub = await reader.readexactly(32)

        # SAS and TOFU check
        sas = compute_sas(pub, receiver_pub)
        recv_fp = sha256_hex(receiver_pub)[:16]

        if self.sas_info:
            try:
                self.sas_info(sas, recv_fp)  # мгновенно отправляем в UI
            except Exception:
                pass
        else:
            self._log(f"[sender] SAS: {sas}, peer FP: {recv_fp}")

        salt = make_salt(pub, receiver_pub)
        is_a_local = pub < receiver_pub  # True, если МЫ — "A"

        # общий секрет
        shared = nacl_bindings.crypto_scalarmult(bytes(priv), receiver_pub)

        if is_a_local:
            info = b"player-db-transfer:v1:a->b"  # мы шлём по A->B
        else:
            info = b"player-db-transfer:v1:b->a"  # мы шлём по B->A

        key_send = hkdf(salt=salt, ikm=shared, info=info, length=32)
        box_send = SecretBox(key_send)

        # --- (необязательно) временный отладочный вывод: первые 4 байта ключа
        self._log(f"[sender] key tag: {key_send[:4].hex()}")

        # узнаём, с какого байта продолжать
        line = await reader.readline()
        resume_from = 0
        try:
            msg = json.loads(line.decode())
            resume_from = int(msg.get("resume_from", 0))
        except:
            resume_from = 0

        if resume_from:
            self._log(f"[sender] receiver requests resume from {resume_from} bytes")

        # ===== начинаем передачу =====
        seq = resume_from // self.chunk_size

        start_window = time.monotonic()
        sent_in_window = 0
        window_sec = 1.0
        kbps = max(int(self.throttle_kbps or 0), 0)
        byte_budget = kbps * 1024 if kbps > 0 else None

        try:
            with open(xfer_path, "rb") as f:
                if resume_from:
                    f.seek(resume_from)
                while True:
                    chunk = f.read(self.chunk_size)
                    if not chunk:
                        break

                    enc = box_send.encrypt(chunk)  # nonce + ciphertext
                    writer.write(b"CHNK")
                    writer.write(struct.pack("!Q", seq))
                    writer.write(struct.pack("!Q", len(enc)))
                    writer.write(enc)
                    await writer.drain()

                    # простой лимитер по «окну» 1 сек
                    if byte_budget:
                        sent_in_window += len(chunk)
                        now = time.monotonic()
                        elapsed = now - start_window
                        if elapsed < window_sec and sent_in_window >= byte_budget:
                            await asyncio.sleep(window_sec - elapsed)
                            start_window = time.monotonic()
                            sent_in_window = 0
                        elif elapsed >= window_sec:
                            start_window = now
                            sent_in_window = 0

                    # wait ack на КАЖДЫЙ чанк
                    line = await reader.readline()
                    ack = json.loads(line.decode())
                    if ack.get("ack") != seq:
                        self._log(f"[sender] bad ack, abort {ack}")
                        writer.close()
                        await writer.wait_closed()
                        return
                    seq += 1

                    if self.on_progress:
                        # показываем реальное количество принятых байт
                        self.on_progress(min(seq * self.chunk_size, size), size)

            # send done + sha
            writer.write(b"DONE")
            writer.write((full_sha_hex + "\n").encode())
            await writer.drain()
            writer.close(); await writer.wait_closed()
            self._log(f"[sender] finished send, seqs: {seq}")
            if self.on_progress:
                try:
                    self.on_progress(size, size)
                except Exception:
                    pass

        finally:
            try:
                if snapshot_path and os.path.exists(snapshot_path):
                    os.remove(snapshot_path)
                if xfer_path and xfer_path != snapshot_path and os.path.exists(xfer_path):
                    os.remove(xfer_path)
            except Exception as e:
                self._log(f"[ERROR][sender] removing snapshot/xfer: {e}")
                pass

# --- Простые CLI-примеры ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="DB Transfer (Receiver or Sender)")
    sub = parser.add_subparsers(dest="cmd")

    r = sub.add_parser("receive")
    r.add_argument("--host", default="0.0.0.0")
    r.add_argument("--port", type=int, default=DEFAULT_PORT)
    r.add_argument("--out-dir", default="./incoming")

    s = sub.add_parser("send")
    s.add_argument("host")
    s.add_argument("db")
    s.add_argument("--port", type=int, default=DEFAULT_PORT)

    args = parser.parse_args()
    if args.cmd == "receive":
        rc = DBReceiver(host=args.host, port=args.port, chunk_dir=args.out_dir)
        try:
            asyncio.run(rc.start_listen())
        except KeyboardInterrupt:
            print("Stopped")
    elif args.cmd == "send":
        sd = DBSender()
        asyncio.run(sd.connect_and_send(args.host, args.port, args.db))
    else:
        parser.print_help()
