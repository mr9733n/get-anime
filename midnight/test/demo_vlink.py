import asyncio
import json
import os
import pathlib

from providers.animedia.adapter import AnimediaAdapter
from utils.net_client import NetClient
from utils.config_manager import ConfigManager


async def demo():
    config_manager = ConfigManager(pathlib.Path('config/config.ini'))
    """Loads the configuration settings needed by the application."""
    network_config = config_manager.network
    net_client = NetClient(network_config)
    adapter = AnimediaAdapter("amd.online", net_client=net_client)
    data = await adapter.get_by_title("Yano-kun no Futsuu no Hibi")

    # Statistics
    for rec in data:
        print(f"(orig={rec['external_id']})"
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
