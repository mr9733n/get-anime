from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

from backend.core.workers.provider_pipeline import ProviderPipeline, FetchAndProcessResult


@dataclass(frozen=True)
class SearchAndProcessParams:
    provider_code: str
    query: str
    mode: str = "title"          # title / title_full
    max_results: int = 10
    limit: int = 5               # сколько кандидатов реально применять


@dataclass(frozen=True)
class SearchAndProcessResult:
    ok: bool
    provider_code: str
    query: str
    applied: list[FetchAndProcessResult]
    skipped: int = 0
    error: str | None = None


class ProviderSearchAndProcessUseCase:
    def __init__(self, *, pipeline: ProviderPipeline):
        self._pipeline = pipeline

    async def execute(self, params: SearchAndProcessParams) -> SearchAndProcessResult:
        provider_code = (params.provider_code or "").strip().lower()
        query = (params.query or "").strip()
        if not provider_code:
            return SearchAndProcessResult(ok=False, provider_code="", query=query, applied=[], error="provider_code is empty")
        if not query:
            return SearchAndProcessResult(ok=False, provider_code=provider_code, query=query, applied=[], error="query is empty")

        # 1) получить список ids кандидатов
        try:
            source = self._pipeline._resolver.resolve(provider_code)
            ids = await self._pipeline._call_provider(source.search_external_ids, query, max_results=params.max_results)
        except Exception as e:
            return SearchAndProcessResult(ok=False, provider_code=provider_code, query=query, applied=[], error=str(e))

        if not ids:
            return SearchAndProcessResult(ok=False, provider_code=provider_code, query=query, applied=[], error="no_candidates")

        # 2) применить limit кандидатов
        picked = list(ids)[: max(1, int(params.limit or 1))]
        skipped = max(0, len(ids) - len(picked))

        tasks = [
            self._pipeline.fetch_and_process(
                provider_code=provider_code,
                external_id=ext_id,
                mode=params.mode,
            )
            for ext_id in picked
        ]
        applied = await asyncio.gather(*tasks, return_exceptions=False)

        return SearchAndProcessResult(
            ok=True,
            provider_code=provider_code,
            query=query,
            applied=applied,
            skipped=skipped,
            error=None,
        )
