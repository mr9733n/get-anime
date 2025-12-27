# providers/animedia/v0/adapter.py
import logging
from typing import Any

from .service import AniMediaService
from .models import Title


class AniMediaAdapter:
    """
    Public API: facade over Service.
    Трансформирует domain models в legacy format для обратной совместимости.
    """

    def __init__(
        self,
        service: AniMediaService,
        logger: logging.Logger | None = None,
    ):
        self._service = service
        self._logger = logger or logging.getLogger(__name__)

    async def get_by_title(
        self,
        anime_name: str,
        max_titles: int = 5,
    ) -> list[dict[str, Any]]:
        """
        Поиск тайтлов по названию.
        Returns: list of legacy-formatted dicts for DB storage.
        """
        titles = await self._service.get_titles_by_name(anime_name, max_titles)
        result = [self._to_legacy_format(t) for t in titles]
        self._logger.info(f"get_by_title: returning {len(result)} titles for '{anime_name}'")
        return result

    async def get_new_titles(self, max_titles: int = 60) -> list[dict[str, Any]]:
        """
        Получить расписание новых серий.
        Returns: list of {"page": int, "titles": list[str]}
        """
        return await self._service.get_schedule(max_titles)

    async def get_all_titles(
        self,
        max_titles: int = 60,
        pages: int = 5,
    ) -> list[dict[str, Any]]:
        """
        Получить каталог всех тайтлов.
        Returns: list of {"page": int, "titles": list[str]}
        """
        return await self._service.get_all_titles(max_titles, pages)

    def _to_legacy_format(self, title: Title) -> dict[str, Any]:
        """
        Convert domain model to legacy dict structure.
        Использует встроенный метод Title.to_legacy().
        """
        return title.to_legacy()