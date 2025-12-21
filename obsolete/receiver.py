# receiver.py
import asyncio
import json
import struct
import os
import hashlib
import sqlite3
import aiofiles
from nacl.public import PrivateKey, PublicKey, Box
from hashlib import sha256

PORT = 8765
CHUNK_DIR = "./incoming"
TMP_NAME = "incoming.db.tmp"
FINAL_NAME = "player.db"
CHUNK_ACK_TIMEOUT = 30  # seconds

async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    peer = writer.get_extra_info('peername')
    print(f"[+] connection from {peer}")

    # 1) read hello line (json\n)
    line = await reader.readline()
    hello = json.loads(line.decode())
    print("[>] HELLO:", hello)
    chunk_size = hello.get("chunk_size", 2*1024*1024)
    file_size = hello.get("file_size", 0)

    # 2) receive sender pubkey (32 bytes)
    sender_pub = await reader.readexactly(32)
    # generate own keypair
    priv = PrivateKey.generate()
    pub = bytes(priv.public_key)
    # send our pubkey
    writer.write(pub)
    await writer.drain()

    # compute SAS (6 digits) for user verification
    h = sha256(sender_pub + pub).digest()
    sas = int.from_bytes(h[:4], "big") % 1_000_000
    print(f"[!] SAS-code to verify with sender: {sas:06d}")
    print("  -> show this code to the sender; wait for confirmation in your UI/terminal.")
    input("Press Enter after you confirmed SAS on both sides (or Ctrl+C to cancel)...")

    box = Box(priv, PublicKey(sender_pub))

    os.makedirs(CHUNK_DIR, exist_ok=True)
    tmp_path = os.path.join(CHUNK_DIR, TMP_NAME)
    f = await aiofiles.open(tmp_path, "wb")

    received = 0
    seq_expected = 0

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
                # decrypt (Box.decrypt expects nonce+ciphertext)
                try:
                    plain = box.decrypt(enc)
                except Exception as e:
                    print("[-] decrypt error:", e)
                    writer.write((json.dumps({"error": "decrypt"}) + "\n").encode()); await writer.drain()
                    break

                # write
                await f.write(plain)
                received += len(plain)
                # send ACK for this seq
                writer.write((json.dumps({"ack": seq}) + "\n").encode())
                await writer.drain()
                seq_expected = seq + 1

                # optional: progress
                print(f"[>] got seq {seq}, bytes={len(plain)}, total_received={received}/{file_size}", end="\r")

            elif typ == "DONE":
                # next line contains sha hex + newline
                sha_line = await reader.readline()
                expected_sha = sha_line.decode().strip()
                print("\n[>] DONE received; expected sha:", expected_sha)
                break
            else:
                print("[-] unknown header:", typ)
                break
    except asyncio.IncompleteReadError:
        print("\n[-] connection closed unexpectedly")
    finally:
        await f.close()
        writer.close()
        await writer.wait_closed()

    # verify SHA
    sha = hashlib.sha256()
    async with aiofiles.open(tmp_path, "rb") as fr:
        while True:
            data = await fr.read(1024*1024)
            if not data:
                break
            sha.update(data)
    got = sha.hexdigest()
    print(f"[>] calculated sha: {got}")
    if got == expected_sha:
        final = os.path.join(CHUNK_DIR, FINAL_NAME)
        os.replace(tmp_path, final)
        print("[+] saved DB to", final)
    else:
        print("[-] SHA mismatch! file kept as", tmp_path)

async def start_server(host="0.0.0.0", port=PORT):
    server = await asyncio.start_server(handle_client, host=host, port=port)
    addr = server.sockets[0].getsockname()
    print(f"Listening on {addr} ...")
    async with server:
        await server.serve_forever()

if __name__ == "__main__":
    try:
        asyncio.run(start_server())
    except KeyboardInterrupt:
        print("\nStopped by user")
