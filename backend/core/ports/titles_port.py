from __future__ import annotations
from typing import Protocol, Any

class ITitlesPort(Protocol):
    # --- titles ---
    def get_titles(
        self,
        *,
        show_all: bool = False,
        day_of_week: int | None = None,
        batch_size: int | None = None,
        title_id: int | None = None,
        title_ids: list[int] | None = None,
        offset: int = 0,
    ) -> list[Any]:
        """Возвращает список ORM Title (как делает DbManager.get_titles_from_db)."""
        ...

    # --- search ---
    def search_title_ids(
        self,
        query: str,
        *,
        limit: int = 50,
        offset: int = 0,
        year: int | None = None,
        genre: str | None = None,
        status_filter: str | None = None,
        type_filter: str | None = None,
    ) -> list[int]:
        """Возвращает только title_id по строке поиска (с опциональными фильтрами)."""
        ...

    def search_title_ids_with_providers(self, query: str) -> tuple[list[int], list[str]]:
        """
        Возвращает (title_ids, providers) как быстрый поиск для старого UI.
        providers — параллельный список (того же размера), где provider — строка (как возвращает DbManager.get_titles_by_keywords).
        """
        ...

    def count_search_titles(
        self,
        query: str,
        *,
        year: int | None = None,
        genre: str | None = None,
        status_filter: str | None = None,
        type_filter: str | None = None,
    ) -> int:
        """Total number of titles matching query + optional filters (for pagination)."""
        ...

    # --- provider links ---
    def get_provider_links_map(self, title_ids: list[int]) -> dict[int, list[dict]]:
        """
        {title_id: [ {id, provider_id, provider_code, provider_name, external_title_id}, ... ]}
        """
        ...

