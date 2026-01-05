# app/core/ports/repositories.py
"""
Порты для репозиториев (хранилищ данных).
Абстрагируют доступ к БД.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable, Any, TypeVar, Generic
from datetime import datetime


# === Value Objects ===

class TitleData:
    """Value object для данных тайтла."""
    __slots__ = (
        "title_id", "external_id", "provider",
        "name_ru", "name_en", "code",
        "description", "status_code", "status_string",
        "season_year", "type_full_string",
        "episodes", "host_for_player",
    )

    def __init__(self, **kwargs):
        for slot in self.__slots__:
            setattr(self, slot, kwargs.get(slot))


class EpisodeData:
    """Value object для данных эпизода."""
    __slots__ = (
        "episode_id", "title_id", "episode_number", "name",
        "hls_fhd", "hls_hd", "hls_sd",
        "skips_opening", "skips_ending",
    )

    def __init__(self, **kwargs):
        for slot in self.__slots__:
            setattr(self, slot, kwargs.get(slot))


# === Repository Protocols ===

@runtime_checkable
class ITitleRepository(Protocol):
    """
    Порт для работы с тайтлами.

    Реализация: DBManager (адаптер над SQLite/SQLAlchemy).
    """

    def get_by_id(self, title_id: int) -> TitleData | None:
        """Получить тайтл по внутреннему ID."""
        ...

    def get_by_ids(
            self,
            title_ids: list[int],
            *,
            offset: int = 0,
            limit: int | None = None,
    ) -> list[TitleData]:
        """Получить тайтлы по списку ID с пагинацией."""
        ...

    def get_by_external_id(
            self,
            provider: str,
            external_id: str | int,
    ) -> TitleData | None:
        """Получить тайтл по внешнему ID провайдера."""
        ...

    def search_by_keywords(
            self,
            keywords: str,
    ) -> tuple[list[int], list[str]]:
        """
        Поиск по ключевым словам.

        Returns:
            Tuple[title_ids, providers] — ID найденных тайтлов и их провайдеры
        """
        ...

    def save(self, title_data: dict) -> tuple[bool, int | None]:
        """
        Сохранить тайтл.

        Returns:
            Tuple[success, title_id]
        """
        ...

    def save_batch(self, titles: list[dict]) -> list[int]:
        """Сохранить несколько тайтлов. Возвращает список title_id."""
        ...

    def get_total_count(self, show_mode: str = "default") -> int:
        """Получить общее количество тайтлов для режима отображения."""
        ...

    def get_titles_list(
            self,
            *,
            batch_size: int = 50,
            offset: int = 0,
    ) -> list[TitleData]:
        """Получить список тайтлов с пагинацией."""
        ...


@runtime_checkable
class IPosterRepository(Protocol):
    """Порт для работы с постерами."""

    def get_blob(
            self,
            title_id: int,
            size_key: str = "original",
    ) -> tuple[bytes | None, bool]:
        """
        Получить постер.

        Returns:
            Tuple[data, is_placeholder]
        """
        ...

    def save_blob(
            self,
            title_id: int,
            size_key: str,
            data: bytes,
    ) -> bool:
        """Сохранить постер."""
        ...

    def get_poster_link(
            self,
            title_id: int,
            size_key: str = "original",
    ) -> str | None:
        """Получить URL постера для скачивания."""
        ...

    def get_last_updated(
            self,
            title_id: int,
            size_key: str = "original",
    ) -> datetime | None:
        """Получить дату последнего обновления постера."""
        ...


@runtime_checkable
class IScheduleRepository(Protocol):
    """Порт для работы с расписанием."""

    def get_titles_for_day(self, day: int) -> list[TitleData]:
        """Получить тайтлы для дня недели (1-7)."""
        ...

    def save_schedule(
            self,
            day: int,
            title_id: int,
            last_updated: datetime,
    ) -> bool:
        """Сохранить запись расписания."""
        ...

    def remove_from_day(
            self,
            title_ids: set[int],
            day: int,
    ) -> bool:
        """Удалить тайтлы из расписания дня."""
        ...


@runtime_checkable
class IHistoryRepository(Protocol):
    """Порт для работы с историей просмотров."""

    def get_watch_status(
            self,
            user_id: int,
            title_id: int,
            episode_id: int | None = None,
    ) -> tuple[bool, bool]:
        """
        Получить статус просмотра.

        Returns:
            Tuple[is_watched, is_downloaded]
        """
        ...

    def save_watch_status(
            self,
            user_id: int,
            title_id: int,
            *,
            episode_id: int | None = None,
            is_watched: bool | None = None,
            is_downloaded: bool | None = None,
    ) -> bool:
        """Сохранить статус просмотра."""
        ...

    def get_need_to_see(self, user_id: int, title_id: int) -> bool:
        """Проверить, помечен ли тайтл как 'нужно посмотреть'."""
        ...

    def save_need_to_see(
            self,
            user_id: int,
            title_id: int,
            need_to_see: bool,
    ) -> bool:
        """Установить флаг 'нужно посмотреть'."""
        ...