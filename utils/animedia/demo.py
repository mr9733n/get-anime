import asyncio
import json
import os
import pathlib

from animedia_adapter import AnimediaAdapter
from utils.net_client import NetClient
from utils.config_manager import ConfigManager

async def demo():
    config_manager = ConfigManager(pathlib.Path('config/config.ini'))
    """Loads the configuration settings needed by the application."""
    network_config = config_manager.network
    net_client = NetClient(network_config)
    adapter = AnimediaAdapter("https://amd.online", net_client=net_client)
    data = await adapter.get_all_titles(max_titles=5*10)

    # Statistics
    if data:
        print(f"{data}")

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
