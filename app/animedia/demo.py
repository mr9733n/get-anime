import asyncio
import json
import os

from app.animedia.animedia_adapter import AnimediaAdapter


async def demo():
    adapter = AnimediaAdapter("https://amedia.online")
    data = await adapter.get_by_title("Yano-kun no Futsuu no Hibi")

    # Statistics
    for rec in data:
        print(f"ID={rec['id']} (orig={rec['animedia_id']})")

    out_path = "out/"
    os.makedirs(out_path, exist_ok=True)
    utils_json = os.path.join(out_path, 'response.json')
    utils_bin = os.path.join(out_path, 'response.bin')
    try:
        with open(utils_json, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"data saved to {utils_json}")
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        try:
            with open(utils_bin, 'wb') as fb:
                fb.write(data)
        except Exception as dump_err:
            print(f"Dump(bin) write error: {dump_err}")

asyncio.run(demo())
