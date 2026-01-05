# app/core/ports/__init__.py
"""
Порты (интерфейсы) для внешних зависимостей.

Это границы системы — всё, что находится за ними,
может быть заменено без изменения бизнес-логики.

Порты определены как Protocol (structural typing),
что позволяет использовать duck typing без явного наследования.
"""

from app.core.ports.repositories import (
    ITitleRepository,
    IPosterRepository,
    IScheduleRepository,
    IHistoryRepository,
)
from app.core.ports.providers import (
    IAnimeProvider,
    ISearchResult,
    ITitleDetails,
)
from app.core.ports.services import (
    IPlaylistService,
    IPosterDownloader,
)

__all__ = [
    # Repositories
    "ITitleRepository",
    "IPosterRepository",
    "IScheduleRepository",
    "IHistoryRepository",
    # Providers
    "IAnimeProvider",
    "ISearchResult",
    "ITitleDetails",
    # Services
    "IPlaylistService",
    "IPosterDownloader",
]