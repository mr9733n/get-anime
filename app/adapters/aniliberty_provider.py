# app/adapters/aniliberty_provider.py
"""
Адаптер: APIAdapter → IAnimeProvider
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.qt.app_constants import PROVIDER_ANILIBERTY

if TYPE_CHECKING:
    pass


@dataclass(frozen=True)
class SearchResult:
    """Результат поиска."""
    external_id: int | str
    name_ru: str | None
    name_en: str | None
    poster_url: str | None
    year: int | None = None
    raw: dict | None = None


@dataclass(frozen=True)
class TitleDetails:
    """Детали тайтла."""
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


class AniLibertyProviderAdapter:
    """
    Адаптер над APIAdapter (AniLiberty), реализующий IAnimeProvider.
    """

    def __init__(self, api_adapter):
        self._api = api_adapter

    @property
    def provider_name(self) -> str:
        return PROVIDER_ANILIBERTY

    def search(self, query: str, *, max_results: int = 10) -> list[SearchResult]:
        """Поиск тайтлов."""
        raw_results = self._api.get_search_by_title(query)

        if not raw_results:
            return []

        # API возвращает dict или list
        if isinstance(raw_results, dict):
            if 'error' in raw_results:
                return []
            items = raw_results.get("list", [])
        else:
            items = raw_results

        results = []
        for item in items[:max_results]:
            names = item.get("names", {}) or {}
            season = item.get("season", {}) or {}

            results.append(SearchResult(
                external_id=item.get("id"),
                name_ru=names.get("ru"),
                name_en=names.get("en"),
                poster_url=self._extract_poster_url(item),
                year=season.get("year"),
                raw=item,
            ))

        return results

    def get_details(self, external_id: str | int) -> TitleDetails | None:
        """Получить детали тайтла."""
        try:
            raw = self._api.get_release_full(int(external_id))
        except (ValueError, TypeError):
            return None

        if not raw:
            return None

        return self._map_to_details(raw)

    def get_details_batch(
            self,
            external_ids: list[str | int],
    ) -> list[TitleDetails]:
        """Получить детали для нескольких тайтлов."""
        int_ids = []
        for eid in external_ids:
            try:
                int_ids.append(int(eid))
            except (ValueError, TypeError):
                continue

        if not int_ids:
            return []

        raw_list = self._api.get_releases_full(int_ids)

        return [
            self._map_to_details(raw)
            for raw in (raw_list or [])
            if raw
        ]

    def get_schedule(self, day: int | None = None) -> list:
        """Получить расписание."""
        return self._api.get_schedule(day) or []

    def get_random(self) -> TitleDetails | None:
        """Получить случайный тайтл."""
        raw = self._api.get_random_title()

        if not raw:
            return None

        return self._map_to_details(raw)

    def _map_to_details(self, raw: dict) -> TitleDetails:
        """Преобразовать raw dict в TitleDetails."""
        names = raw.get("names", {}) or {}
        status = raw.get("status", {}) or {}
        season = raw.get("season", {}) or {}
        type_info = raw.get("type", {}) or {}
        player = raw.get("player", {}) or {}
        torrents_data = raw.get("torrents", {}) or {}

        return TitleDetails(
            external_id=raw.get("id"),
            name_ru=names.get("ru"),
            name_en=names.get("en"),
            code=raw.get("code"),
            description=raw.get("description"),
            poster_url=self._extract_poster_url(raw),
            status_code=status.get("code"),
            status_string=status.get("string"),
            year=season.get("year"),
            type_string=type_info.get("full_string"),
            episodes=player.get("list", []),
            torrents=torrents_data.get("list", []),
            host_for_player=player.get("host"),
            raw=raw,
        )

    def _extract_poster_url(self, raw: dict) -> str | None:
        """Извлечь URL постера."""
        posters = raw.get("posters", {}) or {}
        original = posters.get("original", {}) or {}
        return original.get("url")