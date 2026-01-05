# app/qt/app_context.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QGridLayout, QLineEdit, QComboBox, QScrollArea, QWidget
    from app.qt.app_state import ViewState


@dataclass
class AppContext:
    """
    Контейнер для общего состояния приложения.
    Централизует все runtime-атрибуты, которые раньше были разбросаны по self.app.xxx
    """

    # === App Info ===
    app_version: str = "0.0.0"
    current_template: str = "default"

    # === Runtime View State ===
    view_state: ViewState | None = None
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

    # === UI Widgets (устанавливаются после init_ui) ===
    title_search_entry: QLineEdit | None = None
    quality_dropdown: QComboBox | None = None
    posters_layout: QGridLayout | None = None
    scroll_area: QScrollArea | None = None
    poster_container: QWidget | None = None

    # === Internal reference (для callbacks в контроллерах) ===
    _parent: Any = None  # ссылка на AnimePlayerAppVer3