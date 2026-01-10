from __future__ import annotations

import re
import asyncio
from dataclasses import dataclass
from typing import Any

from backend.core.workers.provider_pipeline import ProviderPipeline, FetchAndProcessResult


_ID_LIST_RE = re.compile(r"^\s*\d+(?:\s*,\s*\d+)*\s*$")


@dataclass(frozen=True)
class SyncSearchAndProcessResult:
    ok: bool
    provider_code: str
    query: str
    applied: list[FetchAndProcessResult]
    skipped: int = 0
    error: str | None = None


class SyncSearchAndProcessUseCase:
    def __init__(self, *, pipeline: ProviderPipeline):
        self._pipeline = pipeline

    async def _apply_ids(
        self,
        *,
        provider_code: str,
        ids: list[str | int],
        mode: str,
        limit: int,
    ) -> SyncSearchAndProcessResult:
        picked = ids[: max(1, limit)]
        skipped = max(0, len(ids) - len(picked))

        applied: list[FetchAndProcessResult] = []
        for ext_id in picked:
            # ВАЖНО: строго последовательно, иначе SQLAlchemy flush конфликтует
            r = await self._pipeline.fetch_and_process(
                provider_code=provider_code,
                external_id=ext_id,
                mode=mode,
            )
            applied.append(r)

        return SyncSearchAndProcessResult(
            ok=True,
            provider_code=provider_code,
            query="",
            applied=applied,
            skipped=skipped,
            error=None,
        )

    async def execute(
        self,
        *,
        provider_code: str,
        query: str,
        mode: str = "title",
        max_results: int = 10,
        limit: int = 5,
    ) -> SyncSearchAndProcessResult:
        code = (provider_code or "").strip().lower()
        q = (query or "").strip()
        m = (mode or "title").strip().lower()

        if not code:
            return SyncSearchAndProcessResult(ok=False, provider_code=code, query=q, applied=[], error="provider_code_required")
        if not q:
            return SyncSearchAndProcessResult(ok=False, provider_code=code, query=q, applied=[], error="query_required")

        # CASE 1: в query передали список numeric external_id: "1,2,3"
        if _ID_LIST_RE.match(q):
            ids = [int(x.strip()) for x in q.split(",") if x.strip()]
            if not ids:
                return SyncSearchAndProcessResult(ok=False, provider_code=code, query=q, applied=[], error="no_candidates")
            return await self._apply_ids(provider_code=code, ids=ids, mode=m, limit=limit)

        # CASE 2: обычный поиск -> список кандидатов -> применяем первые N
        try:
            source = self._pipeline._resolver.resolve(code)
            ids_any = await self._pipeline._call_provider(source.search_external_ids, q, max_results=max_results)
            # провайдер может возвращать как int, так и str (например, AniMedia использует name как ключ)
            ids: list[str | int] = []
            for x in (ids_any or []):
                if x is None:
                    continue
                if isinstance(x, bool):
                    continue
                s = str(x).strip()
                if not s:
                    continue
                # попробуем сохранить числа как int, остальное — как str
                try:
                    ids.append(int(s))
                except Exception:
                    ids.append(s)
        except Exception as e:
            return SyncSearchAndProcessResult(ok=False, provider_code=code, query=q, applied=[], error=str(e))

        if not ids:
            return SyncSearchAndProcessResult(ok=False, provider_code=code, query=q, applied=[], error="no_candidates")

        res = await self._apply_ids(provider_code=code, ids=ids, mode=m, limit=limit)
        return SyncSearchAndProcessResult(
            ok=res.ok,
            provider_code=code,
            query=q,
            applied=res.applied,
            skipped=res.skipped,
            error=res.error,
        )
