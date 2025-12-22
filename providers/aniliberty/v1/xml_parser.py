from __future__ import annotations

from typing import Any, Dict, List, Optional
import xml.etree.ElementTree as Et


def _strip_ns(tag: str) -> str:
    # "{namespace}tag" -> "tag"
    if "}" in tag:
        return tag.split("}", 1)[1]
    return tag


def _find_text(el: Et.Element, name: str) -> Optional[str]:
    for child in el:
        if _strip_ns(child.tag) == name:
            return (child.text or "").strip() or None
    return None


def _find_child(el: Et.Element, name: str) -> Optional[Et.Element]:
    for child in el:
        if _strip_ns(child.tag) == name:
            return child
    return None


def parse_torrents_rss(xml_bytes: bytes) -> Dict[str, Any]:
    """
    Парсит RSS XML в JSON-подобный dict.

    Возвращает:
    {
      "channel": {...},
      "items": [ ... ]
    }
    """
    if not xml_bytes:
        return {"channel": {}, "items": []}

    try:
        root = Et.fromstring(xml_bytes)
    except Et.ParseError:
        return {"channel": {}, "items": [], "error": "Invalid XML"}

    # RSS обычно: <rss><channel>...</channel></rss>
    channel = None
    if _strip_ns(root.tag).lower() == "rss":
        channel = _find_child(root, "channel")
    elif _strip_ns(root.tag).lower() == "feed":
        # на случай Atom (вдруг когда-нибудь)
        channel = root

    if channel is None:
        return {"channel": {}, "items": [], "error": "No channel/feed"}

    channel_info = {
        "title": _find_text(channel, "title"),
        "link": _find_text(channel, "link"),
        "description": _find_text(channel, "description"),
        "language": _find_text(channel, "language"),
        "lastBuildDate": _find_text(channel, "lastBuildDate"),
        "pubDate": _find_text(channel, "pubDate"),
    }

    items: List[Dict[str, Any]] = []
    for item in channel:
        if _strip_ns(item.tag) != "item":
            continue

        enclosure = _find_child(item, "enclosure")
        enclosure_dict = None
        if enclosure is not None:
            enclosure_dict = {
                "url": enclosure.attrib.get("url"),
                "length": enclosure.attrib.get("length"),
                "type": enclosure.attrib.get("type"),
            }

        guid_el = _find_child(item, "guid")
        guid = guid_el.text.strip() if (guid_el is not None and guid_el.text) else None
        guid_is_permalink = None
        if guid_el is not None and "isPermaLink" in guid_el.attrib:
            guid_is_permalink = guid_el.attrib.get("isPermaLink")

        items.append(
            {
                "title": _find_text(item, "title"),
                "link": _find_text(item, "link"),
                "guid": guid,
                "guid_isPermaLink": guid_is_permalink,
                "pubDate": _find_text(item, "pubDate"),
                "description": _find_text(item, "description"),
                "enclosure": enclosure_dict,
            }
        )

    return {"channel": channel_info, "items": items}
