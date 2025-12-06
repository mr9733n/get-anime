import asyncio
import json
import os

from _animedia_adapter import AnimediaAdapter


async def demo():
    adapter = AnimediaAdapter("https://amedia.online")
    data = await adapter.get_by_title("Yano-kun no Futsuu no Hibi")

    # Statistics
    for rec in data:
        print(f"ID={rec['id']} (orig={rec['animedia_id']})"
              f"- {rec['code']}")

    out_path = "out/"
    os.makedirs(out_path, exist_ok=True)
    utils_json = os.path.join(out_path, 'response.json')

    try:
        with open(utils_json, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"data saved to {utils_json}")
    except Exception as e:
        print(f"write error: {e}")

asyncio.run(demo())
