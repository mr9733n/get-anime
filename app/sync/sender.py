# sender.py
import asyncio, json, struct, os, hashlib
import sqlite3
from nacl.public import PrivateKey, PublicKey, Box
from nacl.utils import random as nacl_random

CHUNK_SIZE = 2 * 1024 * 1024  # 2 MiB

def make_snapshot(original_db, snapshot_path):
    # Создаём консистентный snapshot через backup API
    src = sqlite3.connect(original_db)
    dst = sqlite3.connect(snapshot_path)
    with dst:
        src.backup(dst)
    src.close()
    dst.close()

async def send_file(host, port, snapshot_path, schema_version="1"):
    reader, writer = await asyncio.open_connection(host, port)
    size = os.path.getsize(snapshot_path)
    hello = {"role":"sender","schema_version":schema_version,"file_size":size,"chunk_size":CHUNK_SIZE}
    writer.write((json.dumps(hello)+"\n").encode()); await writer.drain()

    # key exchange
    priv = PrivateKey.generate()
    pub = bytes(priv.public_key)
    # send our pub
    writer.write(pub); await writer.drain()
    # receive receiver pub
    receiver_pub = await reader.readexactly(32)
    box = Box(priv, PublicKey(receiver_pub))

    # send chunks
    sha = hashlib.sha256()
    seq = 0
    async with await asyncio.to_thread(open, snapshot_path, "rb") as f:
        while True:
            chunk = f.read(CHUNK_SIZE)
            if not chunk: break
            sha.update(chunk)
            # encrypt chunk: Box.encrypt adds nonce + ciphertext
            enc = box.encrypt(chunk)
            # header
            writer.write(b"CHNK")
            writer.write(struct.pack("!Q", seq))
            writer.write(struct.pack("!Q", len(enc)))
            writer.write(enc)
            await writer.drain()
            # wait for ACK line
            line = await reader.readline()
            ack = json.loads(line.decode())
            if ack.get("ack") != seq:
                print("Bad ack", ack)
                break
            seq += 1

    # send DONE + sha
    writer.write(b"DONE")
    writer.write((sha.hexdigest()+"\n").encode())
    await writer.drain()
    writer.close()
    await writer.wait_closed()
    print("Send finished, total seq", seq)

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        print("Usage: python sender.py <receiver_ip> <path_to_db>")
        sys.exit(1)
    host = sys.argv[1]
    db = sys.argv[2]
    snap = "db_snapshot.sqlite"
    make_snapshot(db, snap)
    asyncio.run(send_file(host, 8765, snap))
