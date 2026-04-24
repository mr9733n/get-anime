# backend/adapters/animedia_provider.py
"""
Adapter: AniMediaAdapter → uniform backend interface.

AniMedia does not have a "fetch by ID" endpoint.
To work around this, search_external_ids() returns compound tokens of the form
    "<external_id>@@<title_name>"
and get_details() accepts either a plain id or such a token.
fetch_payload_by_external_id() on AniMediaPayloadSource does the same.
"""
from __future__ import annotations

import asyncio
import concurrent.futures
from dataclasses import dataclass
from typing import Any

PROVIDER_ANIMEDIA = "animedia"


@dataclass(frozen=True)
class SearchResult:
    """Search result from AniMedia."""
    external_id: int | str
    name_ru: str | None
    name_en: str | None
    poster_url: str | None
    year: int | None = None
    raw: dict | None = None


@dataclass(frozen=True)
class TitleDetails:
    """Title details from AniMedia."""
    external_id: int | str
    name_ru: str | None
    name_en: str | None
    code: str | None
    description: str | None
    poster_url: str | None
    status_code: int | None
    status_string: str | None
    year: int | None
    type_string: str | None
    episodes: list
    torrents: list
    host_for_player: str | None
    raw: dict | None = None


def _run_async(coro) -> Any:
    """Run a coroutine synchronously, safe inside an already-running event loop."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop is not None and loop.is_running():
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, coro).result()
    return asyncio.run(coro)


class AniMediaProviderAdapter:
    """
    Synchronous facade over AniMediaAdapter for the backend layer.

    api_adapter: providers.animedia.v0.adapter.AniMediaAdapter
    """

    def __init__(self, api_adapter: Any) -> None:
        self._api = api_adapter

    @property
    def provider_name(self) -> str:
        return PROVIDER_ANIMEDIA

    # ── Search ───────────────────────────────────────────────────────────────

    def search(self, query: str, *, max_results: int = 10) -> list[SearchResult]:
        """Search titles by name. Returns list of SearchResult."""
        q = (query or "").strip()
        if not q:
            return []

        items: list[dict] = _run_async(self._api.get_by_title(q, max_titles=max_results)) or []
        results: list[SearchResult] = []
        for item in items[:max_results]:
            if not isinstance(item, dict):
                continue
            names = item.get("names") or {}
            season = item.get("season") or {}
            results.append(SearchResult(
                external_id=item.get("external_id"),
                name_ru=names.get("ru"),
                name_en=names.get("en"),
                poster_url=self._extract_poster_url(item),
                year=season.get("year"),
                raw=item,
            ))
        return results

    # ── Details ──────────────────────────────────────────────────────────────

    def get_details(self, external_id_or_token: str | int) -> TitleDetails | None:
        """
        Fetch full title details.

        external_id_or_token:
          - "20693@@One Punch Man"  → search by name, match by id
          - plain int / str id      → search by id (fallback: first result)
        """
        token = str(external_id_or_token).strip()
        ext_id_part: str | None = None
        name_part: str = token

        if "@@" in token:
            left, right = token.split("@@", 1)
            ext_id_part = left.strip() or None
            name_part = (right or "").strip() or token

        items: list[dict] = _run_async(self._api.get_by_title(name_part, max_titles=25)) or []

        if not items:
            return None

        # Prefer exact external_id match
        matched: dict | None = None
        if ext_id_part is not None:
            for it in items:
                if not isinstance(it, dict):
                    continue
                if str(it.get("external_id", "")).strip() == ext_id_part:
                    matched = it
                    break

        if matched is None:
            matched = next((it for it in items if isinstance(it, dict)), None)

        if matched is None:
            return None

        return self._map_to_details(matched)

    def get_details_batch(
        self, tokens: list[str | int]
    ) -> list[TitleDetails]:
        """Fetch details for multiple titles (sequential, AniMedia has no batch endpoint)."""
        results = []
        for token in tokens:
            details = self.get_details(token)
            if details is not None:
                results.append(details)
        return results

    # ── Schedule ─────────────────────────────────────────────────────────────

    def get_schedule(self, day: int | None = None) -> list[dict[str, Any]]:
        """
        Return raw schedule pages:  [{"page": int, "titles": [str]}, ...]
        Each str is a separator-encoded ScheduleItem.
        day is ignored at this level; filtering happens in AniMediaScheduleSource.
        """
        return _run_async(self._api.get_new_titles(60)) or []

    # ── Internal ─────────────────────────────────────────────────────────────

    def _map_to_details(self, raw: dict) -> TitleDetails:
        names = raw.get("names") or {}
        status = raw.get("status") or {}
        season = raw.get("season") or {}
        type_info = raw.get("type") or {}
        player = raw.get("player") or {}
        torrents_data = raw.get("torrents") or {}

        return TitleDetails(
            external_id=raw.get("external_id"),
            name_ru=names.get("ru"),
            name_en=names.get("en"),
            code=raw.get("code"),
            description=raw.get("description"),
            poster_url=self._extract_poster_url(raw),
            status_code=status.get("code"),
            status_string=status.get("string"),
            year=season.get("year"),
            type_string=type_info.get("full_string"),
            episodes=list(player.get("list") or {}).copy(),
            torrents=(torrents_data.get("list") or []).copy(),
            host_for_player=player.get("host"),
            raw=raw,
        )

    def _extract_poster_url(self, raw: dict) -> str | None:
        posters = raw.get("posters") or {}
        for key in ("original", "medium", "small"):
            entry = posters.get(key) or {}
            url = entry.get("url")
            if url:
                return str(url)
        return None

    # ── Async proxy (for AniMediaPayloadSource / AniMediaScheduleSource) ─────
    # AniMediaPayloadSource awaits self.api.get_by_title().
    # AniMediaScheduleSource calls asyncio.run(self.api.get_new_titles()).
    # These proxies let both sources accept either a raw AniMediaAdapter OR
    # this adapter, without changes to the infra layer.

    async def get_by_title(
        self, name: str, max_titles: int = 5
    ) -> list[dict[str, Any]]:
        """Async proxy → AniMediaAdapter.get_by_title()."""
        return await self._api.get_by_title(name, max_titles=max_titles)

    async def get_new_titles(self, max_titles: int = 60) -> list[dict[str, Any]]:
        """Async proxy → AniMediaAdapter.get_new_titles()."""
        return await self._api.get_new_titles(max_titles)
