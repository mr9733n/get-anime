# sender.py
import asyncio
import json
import struct
import os
import hashlib
import sqlite3
from nacl.public import PrivateKey, PublicKey, Box
from hashlib import sha256

CHUNK_SIZE = 2 * 1024 * 1024  # 2 MiB
PORT = 8765
SNAPSHOT = "db_snapshot.sqlite"

def make_snapshot(src_db, snapshot_path=SNAPSHOT):
    print("[*] creating sqlite snapshot...")
    src = sqlite3.connect(src_db)
    dst = sqlite3.connect(snapshot_path)
    with dst:
        src.backup(dst)
    src.close()
    dst.close()
    print("[*] snapshot saved to", snapshot_path)

async def send_file(host, port, snapshot_path, schema_version="1"):
    reader, writer = await asyncio.open_connection(host, port)
    size = os.path.getsize(snapshot_path)
    hello = {"role":"sender","schema_version":schema_version,"file_size":size,"chunk_size":CHUNK_SIZE}
    writer.write((json.dumps(hello) + "\n").encode()); await writer.drain()

    # send our pubkey (32 bytes)
    priv = PrivateKey.generate()
    pub = bytes(priv.public_key)
    writer.write(pub); await writer.drain()

    # receive receiver pubkey
    receiver_pub = await reader.readexactly(32)

    # compute SAS and show
    h = sha256(pub + receiver_pub).digest()
    sas = int.from_bytes(h[:4], "big") % 1_000_000
    print(f"[!] SAS-code to verify with receiver: {sas:06d}")
    input("Press Enter after you confirmed SAS on both sides (or Ctrl+C to cancel)...")

    box = Box(priv, PublicKey(receiver_pub))

    sha = hashlib.sha256()
    seq = 0
    with open(snapshot_path, "rb") as f:
        while True:
            chunk = f.read(CHUNK_SIZE)
            if not chunk:
                break
            sha.update(chunk)
            enc = box.encrypt(chunk)  # nonce + ciphertext
            # header + seq + len
            writer.write(b"CHNK")
            writer.write(struct.pack("!Q", seq))
            writer.write(struct.pack("!Q", len(enc)))
            writer.write(enc)
            await writer.drain()

            # wait for ACK line
            line = await reader.readline()
            ack = json.loads(line.decode())
            if ack.get("ack") != seq:
                print("[-] bad ack, got:", ack)
                writer.close(); await writer.wait_closed(); return
            seq += 1
            print(f"[>] sent seq {seq-1}, total_sent={seq*CHUNK_SIZE}")

    # send DONE + sha
    writer.write(b"DONE")
    writer.write((sha.hexdigest() + "\n").encode())
    await writer.drain()
    writer.close()
    await writer.wait_closed()
    print("[+] send finished, total seq", seq)

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        print("Usage: python sender.py <receiver_ip> <path_to_db>")
        sys.exit(1)
    host = sys.argv[1]
    src_db = sys.argv[2]
    make_snapshot(src_db, SNAPSHOT)
    asyncio.run(send_file(host, PORT, SNAPSHOT))
