# app/mpv/playback_request.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

@dataclass(frozen=True)
class PlaybackRequest:
    playlist: str | None = None          # url или путь к плейлисту
    title_id: int | None = None
    skip_data_b64: str | None = None     # base64 urlsafe json
    proxy: str | None = None             # "ip:port" или "scheme://ip:port"
    template: str | None = None          # например "dark" / "light" / "dark:blue" / json
    prod_key: str | None = None          # строка-ключ "разрешить запуск"
    verbose: bool = False
    log_file: str | None = None
    autoplay: bool = True
