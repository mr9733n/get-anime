from __future__ import annotations

import asyncio
import inspect
from dataclasses import dataclass
from typing import Any

from backend.core.ports.provider_resolver import IProviderResolver
from backend.core.controllers.process_controller import ProcessController


@dataclass(frozen=True)
class FetchAndProcessResult:
    provider_code: str
    mode: str
    external_id: str | int | None
    title_id: int | None
    ok: bool
    details: dict[str, Any] | None = None
    error: str | None = None


class ProviderPipeline:
    def __init__(self, *, resolver: IProviderResolver, process: ProcessController) -> None:
        self._resolver = resolver
        self._process = process

    async def _call_provider(self, fn, *args, **kwargs):
        if inspect.iscoroutinefunction(fn):
            res = fn(*args, **kwargs)
        else:
            res = await asyncio.to_thread(fn, *args, **kwargs)

        if inspect.isawaitable(res):
            return await res
        return res

    async def fetch_payload(
            self,
            *,
            provider_code: str,
            external_id: str | int | None = None,
            query: str | None = None,
            max_results: int = 10,
            force_refresh: bool = False,
    ) -> tuple[str | int | None, dict[str, Any] | None]:
        if external_id is None and (query is None or not query.strip()):
            raise ValueError("Either external_id or query must be provided")

        source = self._resolver.resolve(provider_code)

        if external_id is None:
            ids = await self._call_provider(source.search_external_ids, query.strip(), max_results=max_results)
            if not ids:
                return None, None
            external_id = ids[0]

        supports_force_refresh = "force_refresh" in inspect.signature(source.fetch_payload_by_external_id).parameters
        if supports_force_refresh:
            payload = await self._call_provider(
                source.fetch_payload_by_external_id,
                external_id,
                force_refresh=force_refresh,
            )
        else:
            payload = await self._call_provider(source.fetch_payload_by_external_id, external_id)
        if payload is None:
            return external_id, None
        if isinstance(payload, dict) and payload.get("error"):
            return external_id, None

        # НОРМАЛИЗАЦИЯ external_id ДЛЯ КОНСИСТЕНТНОСТИ:
        # если payload содержит реальный external_id (обычно int), используем его.
        if isinstance(payload, dict):
            real_ext = payload.get("external_id")
            if real_ext is not None:
                try:
                    real_ext_int = int(real_ext)
                    external_id = real_ext_int
                except Exception:
                    pass

        return external_id, payload

    async def fetch_and_process(
        self,
        *,
        provider_code: str,
        external_id: str | int | None = None,
        query: str | None = None,
        mode: str = "auto",
        max_results: int = 10,
        force_refresh: bool = False,
    ) -> FetchAndProcessResult:
        try:
            ext_id, payload = await self.fetch_payload(
                provider_code=provider_code,
                external_id=external_id,
                query=query,
                max_results=max_results,
                force_refresh=force_refresh,
            )
            if payload is None:
                return FetchAndProcessResult(
                    provider_code=provider_code,
                    mode=mode,
                    external_id=ext_id,
                    title_id=None,
                    ok=False,
                    error="payload_not_found",
                )

            res = await asyncio.to_thread(
                self._process.apply_provider_payload,
                provider_code=provider_code,
                payload=payload,
                mode=mode,
            )

            return FetchAndProcessResult(
                provider_code=provider_code,
                mode=mode,
                external_id=ext_id,
                title_id=res.title_id,
                ok=res.ok,
                details=res.details,
                error=res.error,
            )
        except Exception as e:
            return FetchAndProcessResult(
                provider_code=provider_code,
                mode=mode,
                external_id=external_id,
                title_id=None,
                ok=False,
                error=str(e),
            )

    async def random_and_process(
        self,
        *,
        provider_code: str,
        mode: str = "title_full",
    ) -> FetchAndProcessResult:
        try:
            source = self._resolver.resolve(provider_code)
            fetch_random_payload = getattr(source, "fetch_random_payload", None)
            if fetch_random_payload is None:
                return FetchAndProcessResult(
                    provider_code=provider_code,
                    mode=mode,
                    external_id=None,
                    title_id=None,
                    ok=False,
                    error="provider_random_not_supported",
                )

            payload = await self._call_provider(fetch_random_payload)
            if not isinstance(payload, dict) or payload.get("error"):
                return FetchAndProcessResult(
                    provider_code=provider_code,
                    mode=mode,
                    external_id=None,
                    title_id=None,
                    ok=False,
                    error="payload_not_found",
                )

            external_id = payload.get("external_id") or payload.get("id")
            res = await asyncio.to_thread(
                self._process.apply_provider_payload,
                provider_code=provider_code,
                payload=payload,
                mode=mode,
            )

            return FetchAndProcessResult(
                provider_code=provider_code,
                mode=mode,
                external_id=external_id,
                title_id=res.title_id,
                ok=res.ok,
                details=res.details,
                error=res.error,
            )
        except Exception as e:
            return FetchAndProcessResult(
                provider_code=provider_code,
                mode=mode,
                external_id=None,
                title_id=None,
                ok=False,
                error=str(e),
            )
