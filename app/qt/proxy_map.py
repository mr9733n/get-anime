# app/qt/proxy_map.py

from typing import Dict, Tuple

# public_name -> (controller_attr, method_name)
PROXY_MAP: Dict[str, Tuple[str, str]] = {
    "play_link": ("player", "play_link"),
    "open_web_link": ("player", "open_web_link"),
    "display_titles": ("display", "display_titles"),
    "display_info": ("display", "display_info"),
    # ...
}
