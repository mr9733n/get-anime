# utils/animedia/cache_manager.py
import json
import time
from dataclasses import dataclass
from pathlib import Path
from enum import Enum, auto
from typing import Any, Tuple, Optional, Generic, TypeVar


T = TypeVar("T")


@dataclass(frozen=True)
class CacheConfig:
    base_dir: Path
    vlink_key: str = "am_vlink_cache"
    schedule_key: str = "am_schedule_cache"
    vlink_ttl: int = 24 * 60 * 60   # 24h
    schedule_ttl: int = 1 * 60 * 60  # 1h


class CacheStatus(Enum):
    VALID = auto()
    EXPIRED = auto()
    MISSING = auto()
    SAVED = auto()


class CacheManager(Generic[T]):
    """Файловый кэш с поддержкой произвольных TTL."""

    def __init__(self, base_dir: Path):
        self.cfg = CacheConfig(base_dir=base_dir)
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _file(self, key: str) -> Path:
        safe = key.replace("/", "_")
        return self.base_dir / f"{safe}.json"

    def _serialize(self, ts: int | None, data: T) -> str:
        if not ts:
            payload = {"last_updated": int(time.time()), "data": data}
        else:
            payload = {"last_updated": ts, "data": data}
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

    def load_vlink(self, original_id: int) -> Optional[dict[str, str]]:
        status, data = self.load(self.cfg.vlink_key, self.cfg.vlink_ttl)
        if status is not CacheStatus.VALID or not isinstance(data, dict):
            return None
        for k, v in data.items():
            try:
                if int(k) == original_id:
                    return v if isinstance(v, dict) else None
            except ValueError:
                continue
        return None

    def load(self, key: str, ttl: int) -> Tuple[CacheStatus, Optional[T]]:
        p = self._file(key)
        if not p.is_file():
            return CacheStatus.MISSING, None
        try:
            raw = json.loads(p.read_text(encoding="utf-8"))
            if "last_updated" in raw and "data" in raw:
                ts, data = raw["last_updated"], raw["data"]
            else:
                ts, data = 0, raw
        except Exception:
            return CacheStatus.MISSING, None

        if 0 < ttl <= int(time.time()) - ts:
            return CacheStatus.EXPIRED, None
        return CacheStatus.VALID, data

    def save_vlink(self, original_id: int, vlink_dict: dict[str, str]) -> CacheStatus:
        status, current = self.load(self.cfg.vlink_key, self.cfg.vlink_ttl)
        if status is CacheStatus.VALID and isinstance(current, dict):
            data: dict[int, dict[str, str]] = {
                int(k): v for k, v in current.items()
            }
        else:
            data = {}
        data[original_id] = vlink_dict
        return self.save(self.cfg.vlink_key, data)

    def save(self, key: str, data: T) -> CacheStatus:
        path = self._file(key)
        try:
            serialized = self._serialize(ts=None, data=data)
            self._write_atomic(path, serialized)
        except Exception as exc:
            raise IOError(f"Failed to write cache for key {key!r}") from exc
        return CacheStatus.SAVED

    def invalidate_cache(self, key: str) -> CacheStatus:
        path = self._file(key)
        try:
            path.unlink(missing_ok=True)
            return CacheStatus.EXPIRED
        except Exception as exc:
            raise IOError(f"Failed to invalidate cache for key {key!r}: {exc}") from exc


