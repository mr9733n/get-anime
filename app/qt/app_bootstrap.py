# app/qt/app_bootstrap.py
from __future__ import annotations

from typing import Any

class BootstrapMixin:
    def _get_cfg(self, section: str, option: str, default: Any, *, lower: bool = False) -> Any:
        """
        Возвращает значение из конфигурации.
        Если чтение падает – возвращает `default`.
        Параметр lower приводит строку к нижнему регистру (удобно для булевых флагов).
        """
        try:
            value = self.config_manager.get_setting(section, option)
            return value.lower() if lower and isinstance(value, str) else value
        except Exception:
            return default

    def setup_paths(self):
        """Sets up paths based on the current platform and returns them for use."""
        video_player_path = self.config_manager.get_video_player_path()
        torrent_client_path = self.config_manager.get_torrent_client_path()
        return video_player_path, torrent_client_path

