from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from backend.core.workers.provider_pipeline import ProviderPipeline, FetchAndProcessResult


@dataclass(frozen=True)
class TitleSearchParams:
    query: str
    provider_filter: list[str] | None = None
    max_results: int = 10
    update: bool = False


class TitleSearchUseCase:
    def __init__(self, *, pipeline: ProviderPipeline):
        self._pipeline = pipeline

    async def search_by_title(self, params: TitleSearchParams) -> list[FetchAndProcessResult]:
        q = (params.query or "").strip()
        if not q:
            return []

        providers: Iterable[str] = params.provider_filter or ["aniliberty", "animedia"]
        mode = "title_full" if params.update else "title"

        results: list[FetchAndProcessResult] = []

        for provider_code in providers:
            r = await self._pipeline.fetch_and_process(
                provider_code=provider_code,
                query=q,
                max_results=params.max_results,
                mode=mode,
            )
            results.append(r)

        return results
