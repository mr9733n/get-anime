import asyncio

from app.animedia.animedia_adapter import AnimediaAdapter


async def demo():
    adapter = AnimediaAdapter("https://amedia.online")
    data = await adapter.get_by_title("Обычные дни Яно")
    for rec in data:
        print(f"ID={rec['id']} (orig={rec['animedia_original_id']}) "
              f"– {len(rec['episode_links'])} эпизодов")

asyncio.run(demo())
