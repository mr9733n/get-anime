# app/qt/controllers/bootstrap.py
from __future__ import annotations

from typing import Any, Callable


class BootstrapController:
    """
    Переходный контроллер (stage-2/3):
    - svc: доступ к db/api/ui/logger/config/playlist
    - app: доступ к orchestration-методам (display_titles, show_error_notification, invoke_database_save, ...)
    """

    def __init__(self, app: Any, svc: Any | None = None):
        self.app = app
        self.svc = svc

    @property
    def db(self):
        return self.svc.db

    @property
    def ui(self):
        return self.svc.ui

    @property
    def log(self):
        return self.svc.logger

    @property
    def api(self):
        return self.svc.api

    def get_cfg(self, section: str, option: str, default: Any, *, lower: bool = False) -> Any:
        """
        Возвращает значение из конфигурации.
        Если чтение падает – возвращает `default`.
        Параметр lower приводит строку к нижнему регистру (удобно для булевых флагов).
        """
        try:
            value = self.app.config_manager.get_setting(section, option)
            return value.lower() if lower and isinstance(value, str) else value
        except Exception:
            return default

    def setup_paths(self):
        """Sets up paths based on the current platform and returns them for use."""
        video_player_path = self.app.config_manager.get_video_player_path()
        torrent_client_path = self.app.config_manager.get_torrent_client_path()
        return video_player_path, torrent_client_path

