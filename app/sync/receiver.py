# receiver.py
import asyncio, json, os, hashlib, struct
from zeroconf import ServiceInfo, Zeroconf
from nacl.public import PrivateKey, PublicKey, Box
from nacl.hash import blake2b
import aiofiles

SERVICE_TYPE = "_dbshare._tcp.local."
SERVICE_NAME = "player-db-receiver._dbshare._tcp.local."

CHUNK_DIR = "./incoming"
TMP_FILENAME = "incoming.db.tmp"

async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    peer = writer.get_extra_info('peername')
    print("Conn from", peer)

    # 1) hello JSON
    data = await reader.readline()
    hello = json.loads(data.decode())
    print("HELLO from sender:", hello)
    schema_version = hello.get("schema_version")

    # 2) key exchange - receive sender pubkey (32 bytes)
    sender_pub = await reader.readexactly(32)
    # generate own keypair
    priv = PrivateKey.generate()
    pub = bytes(priv.public_key)
    # send our pubkey
    writer.write(pub); await writer.drain()

    # create Box
    box = Box(priv, PublicKey(sender_pub))
    # symmetric key (derive)
    sym = blake2b(bytes(box.shared_key()), digest_size=32)

    # prepare temp file
    os.makedirs(CHUNK_DIR, exist_ok=True)
    tmp_path = os.path.join(CHUNK_DIR, TMP_FILENAME)
    f = await aiofiles.open(tmp_path, 'wb')

    total_size = hello.get("file_size")
    chunk_size = hello.get("chunk_size", 2*1024*1024)
    expected_sha = None
    received = 0
    # loop receiving chunks
    while True:
        header = await reader.readexactly(4)
        if not header:
            break
        typ = header.decode()
        if typ == "CHNK":
            seq_bytes = await reader.readexactly(8)
            seq = struct.unpack("!Q", seq_bytes)[0]
            lng_bytes = await reader.readexactly(8)
            l = struct.unpack("!Q", lng_bytes)[0]
            enc = await reader.readexactly(l)
            # decrypt with box (we used nacl Box which expects nonce+cipher? we'll assume sender uses box.encrypt)
            from nacl.utils import random as nacl_random
            # Using box, sender should have used Box(sender_priv, receiver_pub).encrypt(payload)
            # For simplicity: we use box.decrypt (it expects encrypted = nonce + ciphertext)
            try:
                plain = box.decrypt(enc)
            except Exception as e:
                print("Decrypt error", e)
                writer.write(json.dumps({"error":"decrypt"}).encode()+b"\n"); await writer.drain(); break

            await f.write(plain)
            received += len(plain)
            # send ACK
            writer.write(json.dumps({"ack": seq}).encode()+b"\n"); await writer.drain()

        elif typ == "DONE":
            # next comes SHA length + sha hex
            sha_line = await reader.readline()
            expected_sha = sha_line.decode().strip()
            print("Got DONE, expected sha:", expected_sha)
            break
        else:
            print("Unknown header", typ)
            break

    await f.close()
    writer.close()
    await writer.wait_closed()
    # verify sha
    sha = hashlib.sha256()
    async with aiofiles.open(tmp_path, 'rb') as f2:
        while True:
            data = await f2.read(1024*1024)
            if not data: break
            sha.update(data)
    got = sha.hexdigest()
    print("Calculated sha:", got)
    if expected_sha and got == expected_sha:
        final = os.path.join(CHUNK_DIR, "player.db")
        os.replace(tmp_path, final)
        print("Saved DB to", final)
    else:
        print("SHA mismatch! keeping tmp file:", tmp_path)

async def start_server(port=8765):
    # publish service via zeroconf
    desc = {'name': 'player-db-receiver'}
    info = ServiceInfo(SERVICE_TYPE, SERVICE_NAME, addresses=[b'\x7f\x00\x00\x01'], port=port, properties=desc)
    zc = Zeroconf()
    zc.register_service(info)
    server = await asyncio.start_server(handle_client, host='0.0.0.0', port=port)
    addr = server.sockets[0].getsockname()
    print(f"Serving on {addr}")
    async with server:
        await server.serve_forever()

if __name__ == "__main__":
    asyncio.run(start_server())
