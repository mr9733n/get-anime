# app/qt/controllers/bootstrap.py
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from logging import Logger


@dataclass
class BootstrapControllerDeps:
    """Явные зависимости BootstrapController"""
    logger: Logger
    config_manager: Any  # ConfigManager


class BootstrapController:
    """
    Контроллер для начальной конфигурации.
    Независимый контроллер — не зависит от других контроллеров.
    """

    def __init__(self, deps: BootstrapControllerDeps):
        self._deps = deps

    @property
    def log(self) -> Logger:
        return self._deps.logger

    @property
    def config(self):
        return self._deps.config_manager

    # === Public API ===

    def get_cfg(
        self,
        section: str,
        option: str,
        default: Any,
        *,
        lower: bool = False,
    ) -> Any:
        """
        Возвращает значение из конфигурации.
        Если чтение падает — возвращает default.
        """
        try:
            value = self.config.get_setting(section, option)
            if lower and isinstance(value, str):
                return value.lower()
            return value
        except Exception:
            return default

    def get_cfg_bool(
        self,
        section: str,
        option: str,
        default: bool = False,
    ) -> bool:
        """Возвращает булево значение из конфигурации."""
        val = self.get_cfg(section, option, default)
        return str(val).lower() in ("1", "true", "yes", "on")

    def setup_paths(self) -> tuple[str, str]:
        """Возвращает пути к video player и torrent client."""
        video_player_path = self.config.get_video_player_path()
        torrent_client_path = self.config.get_torrent_client_path()
        return video_player_path, torrent_client_path