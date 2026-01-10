from __future__ import annotations
from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class RequestContext:
    backend: Any
    params: dict

    # --- базовые ---
    @property
    def user_id(self) -> int:
        return int(self.params.get("user_id", self.backend.ctx.user_id))

    @property
    def enrich(self) -> bool:
        return bool(self.params.get("enrich", self.backend.ctx.titles_enrich_default))

    # --- paging ---
    def limit(self, default: int) -> int:
        return int(self.params.get("limit", default))

    def offset(self, default: int) -> int:
        return int(self.params.get("offset", default))

    # --- sync / update ---
    def mode(self, default: str) -> str:
        return (self.params.get("mode") or default).strip().lower()

    def max_results(self, default: int) -> int:
        return int(self.params.get("max_results", default))

    # --- provider ---
    @property
    def provider_code(self) -> str | None:
        val = self.params.get("provider_code")
        if isinstance(val, str) and val.strip():
            return val.strip().lower()
        return None

    @property
    def query(self) -> str | None:
        q = self.params.get("query")
        return q.strip() if isinstance(q, str) and q.strip() else None

    @property
    def external_id(self) -> str | int | None:
        eid = self.params.get("external_id")
        if isinstance(eid, bool):
            return None
        return eid

    # --- ids ---
    def title_ids(self) -> list[int]:
        ids = self.params.get("title_ids")
        if not isinstance(ids, list) or not ids:
            raise ValueError("title_ids must be a non-empty list[int]")
        return [int(x) for x in ids]

    def title_id(self) -> int:
        return int(self.params["title_id"])
