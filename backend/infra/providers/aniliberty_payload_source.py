from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from backend.core.ports.provider_payload_source import IProviderPayloadSource


def _first_list(value: Any) -> list[dict[str, Any]]:
    """
    Пытаемся достать список элементов из разных форматов ответов.
    Возвращаем list[dict].
    """
    if isinstance(value, list):
        return [x for x in value if isinstance(x, dict)]

    if not isinstance(value, dict):
        return []

    if value.get("error"):
        return []

    # самые частые ключи
    candidates = [
        value.get("list"),
        value.get("data"),
        value.get("items"),
        value.get("results"),
        value.get("releases"),
        value.get("titles"),
    ]
    for c in candidates:
        if isinstance(c, list):
            return [x for x in c if isinstance(x, dict)]

    # иногда: {"result": {...}} / {"data": {...}}
    for k in ("result", "payload", "data"):
        inner = value.get(k)
        if isinstance(inner, dict):
            for c in (
                inner.get("list"),
                inner.get("data"),
                inner.get("items"),
                inner.get("results"),
                inner.get("releases"),
                inner.get("titles"),
            ):
                if isinstance(c, list):
                    return [x for x in c if isinstance(x, dict)]

    return []


def _extract_id(item: dict[str, Any]) -> int | None:
    for k in ("id", "release_id", "title_id", "external_id"):
        v = item.get(k)
        if v is None:
            continue
        try:
            n = int(v)
            if n > 0:
                return n
        except Exception:
            continue
    return None


@dataclass(frozen=True)
class AniLibertyPayloadSource(IProviderPayloadSource):
    api: Any

    def _api_search(self, query: str) -> Any:
        # 1) прямой APIAdapter
        if hasattr(self.api, "get_search_by_title"):
            return self.api.get_search_by_title(query)

        # 2) adapter -> _api
        inner = getattr(self.api, "_api", None)
        if inner is not None and hasattr(inner, "get_search_by_title"):
            return inner.get_search_by_title(query)

        # 3) fallback: adapter.search()
        if hasattr(self.api, "search"):
            try:
                return self.api.search(query, max_results=10)
            except TypeError:
                return self.api.search(query)

        raise AttributeError("AniLiberty api has no search method")

    def _api_fetch_full(self, rid: int) -> Any:
        if hasattr(self.api, "get_release_full"):
            return self.api.get_release_full(rid)

        inner = getattr(self.api, "_api", None)
        if inner is not None and hasattr(inner, "get_release_full"):
            return inner.get_release_full(rid)

        if hasattr(self.api, "get_details"):
            details = self.api.get_details(rid)
            return getattr(details, "raw", None) if details is not None else None

        raise AttributeError("AniLiberty api has no fetch method")

    def search_external_ids(self, query: str, *, max_results: int = 10) -> list[int]:
        q = (query or "").strip()
        if not q:
            return []

        data = self._api_search(q)

        # если adapter.search() вернул объекты
        if isinstance(data, list) and data and not isinstance(data[0], dict) and hasattr(data[0], "external_id"):
            out: list[int] = []
            for it in data:
                try:
                    rid = int(getattr(it, "external_id", 0) or 0)
                except Exception:
                    continue
                if rid:
                    out.append(rid)
                if len(out) >= max_results:
                    break
            return out

        items = _first_list(data)
        out: list[int] = []
        for it in items:
            rid = _extract_id(it)
            if rid is None:
                continue
            out.append(rid)
            if len(out) >= max_results:
                break

        return out

    def fetch_payload_by_external_id(self, external_id: str | int) -> dict[str, Any] | None:
        try:
            rid = int(str(external_id).strip())
        except Exception:
            return None

        payload = self._api_fetch_full(rid)
        if not isinstance(payload, dict):
            return None
        if payload.get("error"):
            return None
        return payload
