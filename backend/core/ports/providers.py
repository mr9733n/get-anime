# backend/core/ports/providers.py
"""
Порты для внешних провайдеров аниме.
Абстрагируют работу с API (AniLiberty, AniMedia, etc).
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable, TypedDict, Any
from dataclasses import dataclass


# === DTOs для результатов ===

@dataclass(frozen=True)
class ISearchResult:
    """Результат поиска от провайдера."""
    external_id: str | int
    name_ru: str | None
    name_en: str | None
    poster_url: str | None
    year: int | None = None
    status: str | None = None

    # Raw data для сохранения в БД
    raw: dict | None = None


@dataclass(frozen=True)
class ITitleDetails:
    """Детальная информация о тайтле от провайдера."""
    external_id: str | int
    name_ru: str | None
    name_en: str | None
    code: str | None
    description: str | None
    poster_url: str | None
    status_code: int | None
    status_string: str | None
    year: int | None
    type_string: str | None
    episodes: list[dict]
    torrents: list[dict]
    host_for_player: str | None

    # Raw data
    raw: dict | None = None


@dataclass(frozen=True)
class IScheduleItem:
    """Элемент расписания."""
    day: int
    external_id: str | int
    name_ru: str | None
    name_en: str | None

    raw: dict | None = None


# === Provider Protocol ===

@runtime_checkable
class IAnimeProvider(Protocol):
    """
    Порт для внешнего провайдера аниме.

    Реализации:
    - AniLibertyAdapter
    - AniMediaAdapter
    """

    @property
    def provider_name(self) -> str:
        """Уникальное имя провайдера (e.g., 'aniliberty', 'animedia')."""
        ...

    def search(self, query: str, *, max_results: int = 10) -> list[ISearchResult]:
        """
        Поиск тайтлов по запросу.

        Args:
            query: Поисковый запрос
            max_results: Максимум результатов

        Returns:
            Список результатов поиска
        """
        ...

    def get_details(self, external_id: str | int) -> ITitleDetails | None:
        """
        Получить детальную информацию о тайтле.

        Args:
            external_id: ID тайтла в системе провайдера

        Returns:
            Детали тайтла или None если не найден
        """
        ...

    def get_details_batch(
            self,
            external_ids: list[str | int],
    ) -> list[ITitleDetails]:
        """Получить детали для нескольких тайтлов."""
        ...

    def get_schedule(self, day: int | None = None) -> list[IScheduleItem]:
        """
        Получить расписание.

        Args:
            day: День недели (1-7) или None для всей недели

        Returns:
            Список элементов расписания
        """
        ...

    def get_random(self) -> ITitleDetails | None:
        """Получить случайный тайтл."""
        ...


@runtime_checkable
class IAsyncAnimeProvider(Protocol):
    """
    Асинхронный провайдер (для AniMedia и подобных).

    Методы возвращают сырые данные, которые обрабатываются в callback.
    """

    @property
    def provider_name(self) -> str:
        ...

    def search_async(
            self,
            query: str,
            *,
            max_results: int = 10,
            on_success: Any,  # Callable[[list[dict]], None]
            on_error: Any,  # Callable[[str], None]
    ) -> None:
        """Асинхронный поиск."""
        ...

    def get_all_titles_async(
            self,
            *,
            pages: int = 5,
            on_success: Any,
            on_error: Any,
    ) -> None:
        """Асинхронная загрузка каталога."""
        ...