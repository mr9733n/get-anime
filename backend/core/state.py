# app/core/state.py
"""
Бизнес-состояние приложения.
Чистый Python — без Qt зависимостей.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class BusinessState:
    """
    Runtime состояние приложения.
    Не содержит UI-виджетов, Qt-типов и т.п.
    """

    # === App Info ===
    app_version: str = "0.0.0"
    current_template: str = "default"

    # === View State ===
    current_title_id: int | None = None
    current_title_ids: list[int] | None = None
    current_day_of_week: int | None = None
    current_show_mode: str = "default"
    current_offset: int = 0
    am_last_loaded_page: int = 0

    # === Config (read-only после init) ===
    user_id: int = 1
    titles_batch_size: int = 12
    titles_list_batch_size: int = 50

    # === Transient Data ===
    current_data: Any = None
    current_titles: list | None = None
    total_titles: list | set = field(default_factory=list)
    am_total_count: int = 0
    playlists: dict = field(default_factory=dict)
    discovered_links: list = field(default_factory=list)
    sanitized_titles: list = field(default_factory=list)
    title_names: list = field(default_factory=list)

    # === Playlist ===
    playlist_filename: str | None = None
    stream_video_url: str | None = None

    # === ViewState object (сохраняем для совместимости) ===
    view_state: Any = None  # ViewState | None

    def to_dict(self) -> dict[str, Any]:
        """Сериализует состояние для сохранения."""
        return {
            "current_title_id": self.current_title_id,
            "current_title_ids": self.current_title_ids,
            "current_day": self.current_day_of_week,
            "player_offset": self.current_offset,
            "template_name": self.current_template,
            "show_mode": self.current_show_mode,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BusinessState:
        """Восстанавливает состояние из словаря."""
        state = cls()
        state.current_title_id = data.get("current_title_id")
        state.current_title_ids = data.get("current_title_ids")
        state.current_day_of_week = data.get("current_day")
        state.current_offset = data.get("player_offset", 0)
        state.current_template = data.get("template_name", "default")
        state.current_show_mode = data.get("show_mode", "default")
        return state