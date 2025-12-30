# app/qt/controllers/torrents.py
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.qt.protocols import IPosterController  # для sanitize_filename

if TYPE_CHECKING:
    from logging import Logger
    from utils.downloads.torrent_manager import TorrentManager


@dataclass
class TorrentControllerDeps:
    """Явные зависимости TorrentController"""
    logger: Logger
    torrent_manager: TorrentManager


class TorrentController:
    """
    Контроллер для работы с торрентами.
    Независимый контроллер.
    """

    def __init__(self, deps: TorrentControllerDeps):
        self._deps = deps

    @property
    def log(self) -> Logger:
        return self._deps.logger

    @property
    def torrent_manager(self) -> TorrentManager:
        return self._deps.torrent_manager

    # === Public API ===

    def save_torrent_wrapper(self, link: str, title_name: str, torrent_id: int) -> None:
        """Скачивает и сохраняет торрент файл."""
        try:
            sanitized_name = self._sanitize_filename(title_name)
            file_name = f"{sanitized_name}_{torrent_id}.torrent"

            self.torrent_manager.save_torrent_file(link, file_name)
            self.log.debug("Opening torrent client...")

        except Exception as e:
            self.log.error(f"Error in save_torrent_wrapper: {e}")

    @staticmethod
    def _sanitize_filename(name: str) -> str:
        """Очищает имя файла от недопустимых символов."""
        import re
        return re.sub(r'[<>:"/\\|?*]', '_', name)