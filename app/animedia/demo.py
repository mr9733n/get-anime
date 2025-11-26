import asyncio

from app.animedia.animedia_adapter import AnimediaAdapter
from qasync import QEventLoop, asyncSlot

async def demo():
    adapter = AnimediaAdapter("https://amedia.online")
    data = await adapter.get_by_title("Yano-kun no Futsuu no Hibi")
    for rec in data:
        print(f"ID={rec['id']} (orig={rec['animedia_original_id']}) "
              f"– {len(rec['episode_links'])} эпизодов")

    print(data)
asyncio.run(demo())
