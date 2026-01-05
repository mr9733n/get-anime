# app/qt/app_context.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, TYPE_CHECKING

from app.core.state import BusinessState

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QGridLayout, QLineEdit, QComboBox, QScrollArea, QWidget
    from app.qt.app_state import ViewState

@dataclass
class UIState:
    """UI-специфичное состояние: виджеты, layouts."""
    title_search_entry: "QLineEdit | None" = None
    quality_dropdown: "QComboBox | None" = None
    posters_layout: "QGridLayout | None" = None
    scroll_area: "QScrollArea | None" = None
    poster_container: "QWidget | None" = None

@dataclass
class AppContext:
    """
    Контейнер для полного состояния приложения.

    Архитектура:
    - business: BusinessState — чистая бизнес-логика
    - ui: UIState — Qt-виджеты
    - _parent: ссылка на главное окно (для callbacks)

    Все старые атрибуты доступны напрямую через @property
    для обратной совместимости.
    """
    # Композиция вместо плоской структуры
    business: BusinessState = field(default_factory=BusinessState)
    ui: UIState = field(default_factory=UIState)

    # === Internal reference (для callbacks в контроллерах) ===
    _parent: Any = None  # ссылка на AnimePlayerAppVer3

    # =========================================================================
    # PROXY PROPERTIES — обратная совместимость
    # Весь старый код типа ctx.current_title_id продолжает работать
    # =========================================================================

    # --- App Info ---
    @property
    def app_version(self) -> str:
        return self.business.app_version

    @app_version.setter
    def app_version(self, value: str) -> None:
        self.business.app_version = value

    @property
    def current_template(self) -> str:
        return self.business.current_template

    @current_template.setter
    def current_template(self, value: str) -> None:
        self.business.current_template = value

    # --- View State ---
    @property
    def view_state(self) -> "ViewState | None":
        return self.business.view_state

    @view_state.setter
    def view_state(self, value: "ViewState | None") -> None:
        self.business.view_state = value

    @property
    def current_title_id(self) -> int | None:
        return self.business.current_title_id

    @current_title_id.setter
    def current_title_id(self, value: int | None) -> None:
        self.business.current_title_id = value

    @property
    def current_title_ids(self) -> list[int] | None:
        return self.business.current_title_ids

    @current_title_ids.setter
    def current_title_ids(self, value: list[int] | None) -> None:
        self.business.current_title_ids = value

    @property
    def current_day_of_week(self) -> int | None:
        return self.business.current_day_of_week

    @current_day_of_week.setter
    def current_day_of_week(self, value: int | None) -> None:
        self.business.current_day_of_week = value

    @property
    def current_show_mode(self) -> str:
        return self.business.current_show_mode

    @current_show_mode.setter
    def current_show_mode(self, value: str) -> None:
        self.business.current_show_mode = value

    @property
    def current_offset(self) -> int:
        return self.business.current_offset

    @current_offset.setter
    def current_offset(self, value: int) -> None:
        self.business.current_offset = value

    @property
    def am_last_loaded_page(self) -> int:
        return self.business.am_last_loaded_page

    @am_last_loaded_page.setter
    def am_last_loaded_page(self, value: int) -> None:
        self.business.am_last_loaded_page = value

    # --- Config ---
    @property
    def user_id(self) -> int:
        return self.business.user_id

    @user_id.setter
    def user_id(self, value: int) -> None:
        self.business.user_id = value

    @property
    def titles_batch_size(self) -> int:
        return self.business.titles_batch_size

    @titles_batch_size.setter
    def titles_batch_size(self, value: int) -> None:
        self.business.titles_batch_size = value

    @property
    def titles_list_batch_size(self) -> int:
        return self.business.titles_list_batch_size

    @titles_list_batch_size.setter
    def titles_list_batch_size(self, value: int) -> None:
        self.business.titles_list_batch_size = value

    # --- Transient Data ---
    @property
    def current_data(self) -> Any:
        return self.business.current_data

    @current_data.setter
    def current_data(self, value: Any) -> None:
        self.business.current_data = value

    @property
    def current_titles(self) -> list | None:
        return self.business.current_titles

    @current_titles.setter
    def current_titles(self, value: list | None) -> None:
        self.business.current_titles = value

    @property
    def total_titles(self) -> list | set:
        return self.business.total_titles

    @total_titles.setter
    def total_titles(self, value: list | set) -> None:
        self.business.total_titles = value

    @property
    def am_total_count(self) -> int:
        return self.business.am_total_count

    @am_total_count.setter
    def am_total_count(self, value: int) -> None:
        self.business.am_total_count = value

    @property
    def playlists(self) -> dict:
        return self.business.playlists

    @playlists.setter
    def playlists(self, value: dict) -> None:
        self.business.playlists = value

    @property
    def discovered_links(self) -> list:
        return self.business.discovered_links

    @discovered_links.setter
    def discovered_links(self, value: list) -> None:
        self.business.discovered_links = value

    @property
    def sanitized_titles(self) -> list:
        return self.business.sanitized_titles

    @sanitized_titles.setter
    def sanitized_titles(self, value: list) -> None:
        self.business.sanitized_titles = value

    @property
    def title_names(self) -> list:
        return self.business.title_names

    @title_names.setter
    def title_names(self, value: list) -> None:
        self.business.title_names = value

    # --- Playlist ---
    @property
    def playlist_filename(self) -> str | None:
        return self.business.playlist_filename

    @playlist_filename.setter
    def playlist_filename(self, value: str | None) -> None:
        self.business.playlist_filename = value

    @property
    def stream_video_url(self) -> str | None:
        return self.business.stream_video_url

    @stream_video_url.setter
    def stream_video_url(self, value: str | None) -> None:
        self.business.stream_video_url = value

    # --- UI Widgets (проксируем в UIState) ---
    @property
    def title_search_entry(self) -> "QLineEdit | None":
        return self.ui.title_search_entry

    @title_search_entry.setter
    def title_search_entry(self, value: "QLineEdit | None") -> None:
        self.ui.title_search_entry = value

    @property
    def quality_dropdown(self) -> "QComboBox | None":
        return self.ui.quality_dropdown

    @quality_dropdown.setter
    def quality_dropdown(self, value: "QComboBox | None") -> None:
        self.ui.quality_dropdown = value

    @property
    def posters_layout(self) -> "QGridLayout | None":
        return self.ui.posters_layout

    @posters_layout.setter
    def posters_layout(self, value: "QGridLayout | None") -> None:
        self.ui.posters_layout = value

    @property
    def scroll_area(self) -> "QScrollArea | None":
        return self.ui.scroll_area

    @scroll_area.setter
    def scroll_area(self, value: "QScrollArea | None") -> None:
        self.ui.scroll_area = value

    @property
    def poster_container(self) -> "QWidget | None":
        return self.ui.poster_container

    @poster_container.setter
    def poster_container(self, value: "QWidget | None") -> None:
        self.ui.poster_container = value