# utils/playlist_key.py
from __future__ import annotations

import json
import logging
import hashlib
from typing import Any


logger = logging.getLogger(__name__)


def calc_bundle_key(title_id: int, links: list[str], host: str | None) -> str:
    try:
        host = (host or "").strip()
        # важно: порядок ссылок влияет на плейлист -> ключ должен учитывать порядок
        payload = host + "\n" + "\n".join([str(x) for x in (links or [])])
        key = hashlib.sha1(payload.encode("utf-8", errors="ignore")).hexdigest()
        logger.info(f"Created key: {key} for [tile_id: {title_id}] playlist.")
        return key
    except OSError as e:
        raise RuntimeError(f"Error creating key for {title_id}: {e}")