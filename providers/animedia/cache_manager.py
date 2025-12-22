# providers/animedia/cache_manager.py
import json
import time
from dataclasses import dataclass
from pathlib import Path
from enum import Enum, auto
from typing import Any, Tuple, Optional, Generic, TypeVar
from typing import Mapping, MutableMapping, Any


ItemKey = str
T = TypeVar("T")


@dataclass(frozen=True)
class AniMediaCacheConfig:
    base_dir: Path
    vlink_key: str = "am_vlink_cache"
    schedule_key: str = "am_schedule_cache"
    vlink_ttl: int = 24 * 60 * 60   # 24h
    schedule_ttl: int = 1 * 60 * 60  # 1h


class AniMediaCacheStatus(Enum):
    VALID = auto()
    EXPIRED = auto()
    MISSING = auto()
    SAVED = auto()


class AniMediaCacheManager(Generic[T]):
    """Файловый кэш с поддержкой произвольных TTL."""

    def __init__(self, base_dir: Path):
        self.cfg = AniMediaCacheConfig(base_dir=base_dir)
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _file(self, key: str) -> Path:
        safe = key.replace("/", "_")
        return self.base_dir / f"{safe}.json"

    def _serialize_items(self, items: Mapping[ItemKey, dict]) -> str:
        return json.dumps({"items": items}, ensure_ascii=False, indent=2)

    def _serialize(self, ts: int | None, data: T) -> str:
        payload = {"last_updated": int(time.time()) if ts is None else ts, "data": data}
        return json.dumps(payload, ensure_ascii=False, indent=2)

    def _write_atomic(self, path: Path, content: str) -> None:
        tmp_path = path.with_suffix(".tmp")
        tmp_path.write_text(content, encoding="utf-8")
        tmp_path.replace(path)

    def is_nonempty(self, data: Any) -> bool:
        if data is None:
            return False

        if isinstance(data, list) and all(isinstance(i, str) for i in data):
            return bool(data)

        if isinstance(data, list) and all(isinstance(i, dict) for i in data):
            for entry in data:
                if "page" not in entry or "titles" not in entry:
                    return False
                if not isinstance(entry["titles"], list):
                    return False
            return bool(data)
        return False

    def load_vlink(self, original_id: str) -> Optional[dict[str, str]]:
        status, data = self.load_item(self.cfg.vlink_key, original_id, ttl=self.cfg.vlink_ttl)
        if status is AniMediaCacheStatus.VALID and isinstance(data, dict):
            return data
        return None

    def load_item(self, key: str, item_id: ItemKey, ttl: int) -> Tuple[AniMediaCacheStatus, Optional[T]]:
        p = self._file(key)
        if not p.is_file():
            return AniMediaCacheStatus.MISSING, None

        try:
            raw = json.loads(p.read_text(encoding="utf-8"))
            entry = raw.get("items", {}).get(item_id)
            if entry is None:
                return AniMediaCacheStatus.MISSING, None
            ts = entry.get("last_updated", 0)
            data = entry.get("data")
        except Exception:
            return AniMediaCacheStatus.MISSING, None

        if 0 < ttl <= int(time.time()) - ts:
            return AniMediaCacheStatus.EXPIRED, None
        return AniMediaCacheStatus.VALID, data

    def load(self, key: str, ttl: int) -> Tuple[AniMediaCacheStatus, Optional[T]]:
        p = self._file(key)
        if not p.is_file():
            return AniMediaCacheStatus.MISSING, None
        try:
            raw = json.loads(p.read_text(encoding="utf-8"))
            if "last_updated" in raw and "data" in raw:
                ts, data = raw["last_updated"], raw["data"]
            elif "items" in raw:
                ts = None
                data = raw
            else:
                return AniMediaCacheStatus.MISSING, None
        except Exception:
            return AniMediaCacheStatus.MISSING, None
        if ts is not None:
            if 0 < ttl <= int(time.time()) - ts:
                return AniMediaCacheStatus.EXPIRED, data
        return AniMediaCacheStatus.VALID, data

    def save(self, key: str, data: T) -> AniMediaCacheStatus:
        path = self._file(key)
        try:
            serialized = self._serialize(ts=None, data=data)
            self._write_atomic(path, serialized)
        except Exception as exc:
            raise IOError(f"Failed to write cache for key {key!r}") from exc
        return AniMediaCacheStatus.SAVED

    def save_vlink(self, original_id: str, vlink_dict: dict[str, str]) -> AniMediaCacheStatus:
        """
        Сохраняет словарь ссылок для одного title‑id.
        vlink_dict: {source_url: target_url, …}
        """
        # сохраняем только один элемент, а не весь большой словарь
        return self.save_item(self.cfg.vlink_key, original_id, vlink_dict)

    def save_item(self, key: str, item_id: ItemKey, data: T) -> AniMediaCacheStatus:
        path = self._file(key)

        try:
            raw = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
            items: MutableMapping[ItemKey, dict] = raw.get("items", {})
        except Exception:
            items = {}

        items[item_id] = {"last_updated": int(time.time()), "data": data}

        try:
            self._write_atomic(path, self._serialize_items(items))
        except Exception as exc:
            raise IOError(f"Failed to write cache for key {key!r}") from exc
        return AniMediaCacheStatus.SAVED

    def invalidate_item(self, key: str, item_id: ItemKey) -> AniMediaCacheStatus:
        path = self._file(key)
        try:
            raw = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
            items: MutableMapping[ItemKey, dict] = raw.get("items", {})

            if item_id not in items:
                return AniMediaCacheStatus.EXPIRED

            if item_id in items:
                items.pop(item_id, None)
                self._write_atomic(path, self._serialize_items(items))
            return AniMediaCacheStatus.EXPIRED
        except Exception as exc:
            raise IOError(f"Failed to invalidate item {item_id!r} in key {key!r}") from exc

    def invalidate_cache(self, key: str) -> AniMediaCacheStatus:
        path = self._file(key)
        try:
            path.unlink(missing_ok=True)
            return AniMediaCacheStatus.EXPIRED
        except Exception as exc:
            raise IOError(f"Failed to invalidate cache for key {key!r}: {exc}") from exc