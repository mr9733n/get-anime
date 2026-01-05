# app/adapters/title_repository.py
"""
Адаптер: DBManager → ITitleRepository
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass


class DBTitleRepository:
    """
    Адаптер над DBManager, реализующий ITitleRepository.
    """

    def __init__(self, db_manager):
        self._db = db_manager

    def get_by_id(self, title_id: int):
        """Получить тайтл по ID."""
        results = self._db.get_titles_from_db(
            show_all=False,
            title_id=title_id,
        )
        return results[0] if results else None

    def get_by_ids(
            self,
            title_ids: list[int],
            *,
            offset: int = 0,
            limit: int | None = None,
    ) -> list:
        """Получить тайтлы по списку ID."""
        return self._db.get_titles_from_db(
            show_all=False,
            title_ids=title_ids,
            offset=offset,
            batch_size=limit,
        )

    def get_by_external_id(
            self,
            provider: str,
            external_id: str | int,
    ):
        """Получить тайтл по external_id провайдера."""
        return self._db.get_title_by_external_id(provider, str(external_id))

    def search_by_keywords(
            self,
            keywords: str,
    ) -> tuple[list[int], list[str]]:
        """
        Поиск по ключевым словам.
        Использует существующий метод get_titles_by_keywords.
        """
        return self._db.get_titles_by_keywords(keywords)

    def save(self, title_data: dict) -> tuple[bool, int | None]:
        """Сохранить тайтл через process_manager."""
        try:
            # process_titles ожидает список и возвращает список title_ids
            result = self._db.process_titles([title_data])
            if result and len(result) > 0:
                return True, result[0]
            return False, None
        except Exception:
            return False, None

    def save_batch(self, titles: list[dict]) -> list[int]:
        """Сохранить несколько тайтлов."""
        return self._db.process_titles(titles) or []

    def get_total_count(self, show_mode: str = "default") -> int:
        """Получить общее количество тайтлов."""
        return self._db.get_total_titles_count(show_mode)