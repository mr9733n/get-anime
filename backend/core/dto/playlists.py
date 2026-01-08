from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PlaylistBundleDTO:
    """
    Результат генерации плейлиста:
    - m3u: стримы (.m3u8)
    - urls: веб-ссылки (страницы/плееры)
    """
    name: str
    mode: str
    quality: str

    m3u_name: str
    m3u_path: str
    urls_name: str
    urls_path: str

    streams_count: int
    web_count: int

    key: str | None = None  # опционально: sha1 по host+links
    host: str | None = None
