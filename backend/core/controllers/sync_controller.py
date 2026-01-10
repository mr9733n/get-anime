from __future__ import annotations

from typing import Any

from backend.core.ports.provider_resolver import IProviderResolver
from backend.core.workers.provider_pipeline import ProviderPipeline
from backend.core.use_cases.sync_search_and_process import SyncSearchAndProcessUseCase


class SyncController:
    def __init__(
        self,
        *,
        provider_resolver: IProviderResolver,
        pipeline: ProviderPipeline,
        search_and_process_uc: SyncSearchAndProcessUseCase,
    ) -> None:
        self._resolver = provider_resolver
        self._pipeline = pipeline
        self._search_uc = search_and_process_uc

    async def search_and_process(
        self,
        *,
        provider_code: str,
        query: str,
        mode: str = "title",
        max_results: int = 10,
        limit: int = 5,
    ):
        return await self._search_uc.execute(
            provider_code=provider_code,
            query=query,
            mode=mode,
            max_results=max_results,
            limit=limit,
        )

    async def fetch_and_process(
        self,
        *,
        provider_code: str,
        external_id: str | int | None = None,
        query: str | None = None,
        mode: str = "title_full",
        max_results: int = 5,
    ):
        return await self._pipeline.fetch_and_process(
            provider_code=provider_code,
            external_id=external_id,
            query=query,
            mode=mode,
            max_results=max_results,
        )

    async def search_external_ids(
        self,
        *,
        provider_code: str,
        query: str,
        max_results: int = 10,
    ) -> list[str | int]:
        source = self._resolver.resolve(provider_code)
        ids_any = await self._pipeline._call_provider(source.search_external_ids, query, max_results=max_results)

        ids: list[str | int] = []
        for x in (ids_any or []):
            if x is None or isinstance(x, bool):
                continue
            s = str(x).strip()
            if not s:
                continue
            try:
                ids.append(int(s))
            except Exception:
                ids.append(s)
        return ids

    async def fetch_payload(
        self,
        *,
        provider_code: str,
        external_id: str | int | None = None,
        query: str | None = None,
        max_results: int = 10,
    ) -> dict[str, Any] | None:
        _ext_id, payload = await self._pipeline.fetch_payload(
            provider_code=provider_code,
            external_id=external_id,
            query=query,
            max_results=max_results,
        )
        return payload
