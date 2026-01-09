# app/qt/protocols.py
from __future__ import annotations

from typing import Protocol, runtime_checkable, Any, Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from app.qt.app_state import ViewState
    from PyQt6.QtWidgets import QLayout


# === UI Protocols ===

@runtime_checkable
class IUIManager(Protocol):
    """Интерфейс для UI операций"""

    parent_widgets: dict[str, Any]

    def show_loader(self, message: str = "Loading...") -> None: ...

    def hide_loader(self) -> None: ...

    def set_buttons_enabled(self, enabled: bool) -> None: ...

    def update_pagination_info(
            self,
            current_page: int,
            total_pages: int,
            total_items: int,
            show_mode: str
    ) -> None: ...

    def setup_main_layout(
            self,
            main_layout: Any,
            all_layout_metadata: list,
            callbacks: dict
    ) -> None: ...


@runtime_checkable
class IUIGenerator(Protocol):
    """Интерфейс для генерации UI тайтлов"""

    def create_title_browser(self, title: Any, show_mode: str = "default") -> Any: ...

    def get_title_html(self, title: Any, show_mode: str = "default") -> str: ...


@runtime_checkable
class IUISystemGenerator(Protocol):
    """Интерфейс для генерации system screen"""

    def create_system_browser(self, statistics: dict, template: str) -> Any: ...


@runtime_checkable
class IUIAnimediaGenerator(Protocol):
    """Интерфейс для генерации AniMedia screens"""

    def create_animedia_schedule_browser(self, schedule: list) -> Any: ...

    def create_animedia_titles_browser(self, titles: list) -> Any: ...


# === Controller Protocols ===

@runtime_checkable
class IDisplayController(Protocol):
    """Интерфейс для отображения контента"""

    def display_info(self, title_id: int) -> None: ...

    def display_titles(
            self,
            title_ids: list[int] | None = None,
            batch_size: int | None = None,
            show_mode: str = "default",
            show_previous: bool = False,
            show_next: bool = False,
            start: bool = False,
    ) -> None: ...

    def display_titles_in_ui(
            self,
            titles: list,
            show_mode: str = "default",
            row_start: int = 0,
            col_start: int = 0,
    ) -> None: ...

    def show_error_notification(self, title: str, message: str) -> None: ...

    def refresh_display(self) -> None: ...

    def reset_offset(self) -> None: ...

    def setup_pagination_ui(
            self,
            count_titles: int,
            batch_size: int,
            description: str | None = None
    ) -> None: ...

    def clear_layout(self, layout: QLayout) -> None: ...


@runtime_checkable
class IPersistenceController(Protocol):
    """Интерфейс для сохранения данных"""

    def invoke_database_save(self, title_list: list[dict]) -> list[int]: ...

    def save_titles_list(self, titles_list: list[dict]) -> list[int]: ...


@runtime_checkable
class IStateController(Protocol):
    """Интерфейс для управления состоянием"""

    def set_view_state(self, state: ViewState) -> None: ...

    def get_current_state(self) -> dict[str, Any]: ...

    def navigate_animedia_mode(self, show_mode: str, go_forward: bool) -> bool: ...


@runtime_checkable
class IPosterController(Protocol):
    """Интерфейс для работы с постерами"""

    def clear_previous_posters(self) -> None: ...

    def get_poster_or_placeholder(
            self,
            title_id: int,
            size_key: str = "original",
            force_download: bool = False,
    ) -> bytes | None: ...


@runtime_checkable
class IAnimediaController(Protocol):
    """Интерфейс для AniMedia операций"""

    def display_animedia_schedule_screen(self, schedule_json: list | None = None) -> None: ...

    def display_animedia_titles_screen(self, titles_json: list | None = None) -> None: ...


@runtime_checkable
class IAniLibertyController(Protocol):
    """Интерфейс для AniLiberty операций"""

    def fetch_and_process_schedule(self, day_of_week: int) -> tuple[bool, set | None]: ...

    def reload_schedule(self) -> None: ...


@runtime_checkable
class IAPIAdapter(Protocol):
    """Интерфейс для API провайдера"""

    def get_release_full(self, title_id: int) -> dict: ...

    def get_releases_full(self, title_ids: list[int]) -> list[dict]: ...

    def get_search_by_title(self, search_text: str) -> dict | list: ...

    def get_schedule(self, day: int) -> list | None: ...

    def get_random_title(self) -> dict: ...


@runtime_checkable
class IDBManager(Protocol):
    """Интерфейс для работы с БД (основные методы)"""

    def get_titles_from_db(
            self,
            show_all: bool = True,
            title_id: int | None = None,
            title_ids: list[int] | None = None,
            day_of_week: int | None = None,
            batch_size: int | None = None,
            offset: int = 0,
    ) -> list: ...

    def get_total_titles_count(self, show_mode: str = "default") -> int: ...

    def get_statistics_from_db(self) -> dict: ...

    def get_player_host_by_title_id(self, title_id: int) -> str | None: ...