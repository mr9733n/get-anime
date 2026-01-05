# app/core/ports/services.py
"""
Порты для сервисов.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable
from dataclasses import dataclass


@dataclass
class PlaylistBundle:
    """Результат создания playlist bundle."""
    m3u_name: str | None
    web_name: str | None
    streams_count: int
    web_count: int


@runtime_checkable
class IPlaylistService(Protocol):
    """Порт для работы с плейлистами."""

    def create_bundle(
            self,
            title_names: list[str],
            links: list[str],
            host: str | None,
    ) -> PlaylistBundle:
        """Создать bundle из ссылок (m3u + web urls)."""
        ...

    def make_full_url(self, link: str, host: str | None) -> str | None:
        """Собрать полный URL из относительной ссылки и хоста."""
        ...

    def play(self, filename: str, player_path: str) -> bool:
        """Запустить плейлист во внешнем плеере."""
        ...


@runtime_checkable
class IPosterDownloader(Protocol):
    """Порт для скачивания постеров."""

    def queue_download(
            self,
            title_id: int,
            url: str,
            size_key: str,
    ) -> None:
        """Добавить постер в очередь скачивания."""
        ...

    def process_queue(self) -> int:
        """
        Обработать очередь скачивания.

        Returns:
            Количество успешно скачанных постеров
        """
        ...