# app/qt/controllers/actions.py
from __future__ import annotations

from typing import TYPE_CHECKING, Callable
from dataclasses import dataclass

from app.qt.app_constants import PROVIDER_ANILIBERTY, PROVIDER_ANIMEDIA
from app.qt.app_exceptions import APIClientError
from app.qt.app_state import TitleRef
from app.qt.protocols import (
    IDisplayController,
    IPersistenceController,
    IUIManager,
    IAPIAdapter,
)
from app.qt.ui_helpers import ui_operation, ui_operation_async, cleanup_ui

if TYPE_CHECKING:
    from logging import Logger
    from app.qt.app_context import AppContext
    from providers.animedia.v0.adapter import AniMediaAdapter
    from app.core.use_cases.title_search_use_case import TitleSearchUseCase, TitleSearchResult

@dataclass
class ActionsControllerDeps:
    """Явные зависимости ActionsController"""
    logger: Logger
    db: any  # DBManager — можно тоже сделать протокол
    api: IAPIAdapter
    ui: IUIManager
    display: IDisplayController
    persistence: IPersistenceController
    context: AppContext
    animedia_adapter: AniMediaAdapter  # для async worker
    use_case: "TitleSearchUseCase | None" = None
    on_show_title: Callable[[int], None] | None = None
    on_show_titles: Callable[[list[int]], None] | None = None
    on_notify_error: Callable[[str, str], None] | None = None
    on_notify_info: Callable[[str, str], None] | None = None
    on_notify_warning: Callable[[str, str], None] | None = None
    on_notify_success: Callable[[str, str], None] | None = None
    on_refresh: Callable[[], None] | None = None

class ActionsController:
    """
    Контроллер поиска и обновления тайтлов.
    Все зависимости — явные, через конструктор.
    """

    def __init__(self, deps: ActionsControllerDeps):
        self._deps = deps
        self._last_search_text: str | None = None
        self._animedia_worker = None

    # --- Properties для удобства ---

    @property
    def log(self):
        return self._deps.logger

    @property
    def db(self):
        return self._deps.db

    @property
    def api(self):
        return self._deps.api

    @property
    def ui(self):
        return self._deps.ui

    @property
    def display(self) -> IDisplayController:
        return self._deps.display

    @property
    def persistence(self) -> IPersistenceController:
        return self._deps.persistence

    @property
    def ctx(self) -> AppContext:
        return self._deps.context

    # --- Public API ---

    def get_update_title(self) -> bool:
        """Обновление с авто-определением провайдера."""
        return self._update_titles(provider_filter=None)

    def get_update_title_aniliberty(self) -> bool:
        """Обновление только через AniLiberty."""
        return self._update_titles(provider_filter=PROVIDER_ANILIBERTY)

    def get_update_title_animedia(self) -> bool:
        """Обновление только через AniMedia."""
        return self._update_titles(provider_filter=PROVIDER_ANIMEDIA)

    def get_search_by_title(self) -> bool:
        """Поиск тайтла: локальная БД → AniLiberty → Animedia."""
        return self._search_by_title(provider_filter=None, search_text=None)

    def get_search_by_title_aniliberty(self) -> bool:
        """Поиск тайтла: локальная БД → AniLiberty."""
        return self._search_by_title(provider_filter=PROVIDER_ANILIBERTY, search_text=None)

    def get_search_by_title_animedia(self, search_text: str | None = None) -> bool:
        """Поиск тайтла: локальная БД (провайдер = Animedia) → Animedia (async)."""
        return self._search_by_title(provider_filter=PROVIDER_ANIMEDIA, search_text=search_text)

    # --- Private implementation ---

    def _get_search_text(self) -> str:
        """Получает текст поиска из UI или текущего состояния"""
        search_text = ""

        if self.ctx.title_search_entry:
            search_text = self.ctx.title_search_entry.text().strip()
            self.ctx.title_search_entry.clear()

        return search_text

    def _get_fallback_search_text(self) -> str | None:
        """Fallback: используем текущие title_ids"""
        if self.ctx.current_title_ids:
            return ",".join(str(tid) for tid in self.ctx.current_title_ids)
        elif self.ctx.current_title_id is not None:
            return str(self.ctx.current_title_id)
        return None

    def _update_titles(self, provider_filter: str | None) -> bool:
        """Общая логика обновления тайтлов (через core use-case + AsyncWorker)."""
        from app.qt.workers import AsyncWorker

        if not self._deps.use_case:
            self._notify_error("Update", "use_case not configured")
            return False

        search_text = self._get_search_text()
        if not search_text:
            search_text = self._get_fallback_search_text()
            if not search_text:
                self.log.warning("Unable to update title(s): missing title ID(s)")
                self._notify_error("Error", "Unable to update title(s): missing title ID(s)")
                return False

        self.log.info(f"Updating title(s). Keywords: {search_text}")
        self._last_search_text = search_text

        with ui_operation_async(self.ui, "Updating title info..."):
            self._update_worker = AsyncWorker(
                self._deps.use_case.update_titles,
                search_text,
                provider_filter,
                max_titles_animedia=5,
            )
            self._update_worker.finished.connect(self._on_update_use_case_result)
            self._update_worker.error.connect(self._on_update_use_case_error)
            self._update_worker.start()

        return True

    def _on_update_use_case_result(self, result) -> None:
        try:
            if not getattr(result, "ok", False):
                msg = getattr(result, "error", None) or "Update failed."
                self._notify_error("Update", msg)
                return

            updated = getattr(result, "updated", 0)
            failed = getattr(result, "failed", 0)

            if failed:
                self._notify_warning("Update", f"Updated: {updated}, failed: {failed}")
            else:
                self._notify_success("Update", f"Updated: {updated}")

            self._refresh()

        except Exception as e:
            self.log.error(f"Error in _on_update_use_case_result: {e}", exc_info=True)
            self._notify_error("Update", "Unexpected error.")
        finally:
            cleanup_ui(self.ui)

    def _on_update_use_case_error(self, message: str) -> None:
        try:
            self.log.error(f"Update worker error: {message}")
            self._notify_error("Update error", message)
        finally:
            cleanup_ui(self.ui)

    def _search_by_title(self, provider_filter: str | None, search_text: str | None) -> bool:
        """Поиск тайтла через core use-case (DB -> AL -> AM)."""
        from app.qt.workers import AsyncWorker

        if not search_text:
            search_text = self._get_search_text()
        if not search_text:
            return False

        self._last_search_text = search_text

        with ui_operation_async(self.ui, "Fetching by title..."):
            self._search_worker = AsyncWorker(
                self._deps.use_case.search_by_title,
                search_text,
                provider_filter,
                max_titles_animedia=5,
            )
            self._search_worker.finished.connect(self._on_search_use_case_result)
            self._search_worker.error.connect(self._on_search_use_case_error)
            self._search_worker.start()

        return True

    def _on_search_use_case_result(self, result) -> None:
        """Callback: TitleSearchUseCase завершился."""
        try:
            if not getattr(result, "ok", False):
                msg = getattr(result, "error", None) or "No titles found."
                self._notify_error("Search", msg)
                return

            title_ids = getattr(result, "title_ids", None) or []
            if not title_ids:
                self._notify_warning("Search", "No titles found.")
                return

            self.ctx.current_data = getattr(result, "current_data", None)
            self._show_titles(title_ids)

        except Exception as e:
            self.log.error(f"Error in _on_search_use_case_result: {e}", exc_info=True)
            self._notify_error("Error", "Unexpected error.")
        finally:
            cleanup_ui(self.ui)

    def _on_search_use_case_error(self, message: str) -> None:
        try:
            self.log.error(f"Search worker error: {message}")
            self._notify_error("Search error", message)
        finally:
            cleanup_ui(self.ui)

    # callbacks

    def _refresh(self) -> None:
        if self._deps.on_refresh:
            self._deps.on_refresh()
        else:
            # fallback на старое поведение
            try:
                self.display.refresh_display()
            except Exception:
                pass

    def _notify_success(self, title: str, message: str) -> None:
        if self._deps.on_notify_success:
            self._deps.on_notify_success(title, message)
            return
        self._notify_info(title, message)

    def _notify_warning(self, title: str, message: str) -> None:
        if self._deps.on_notify_warning:
            self._deps.on_notify_warning(title, message)
            return
        self._notify_error(title, message)  # временно

    def _notify_error(self, title: str, message: str) -> None:
        if self._deps.on_notify_error:
            self._deps.on_notify_error(title, message)
        else:
            self.display.show_error_notification(title, message)

    def _notify_info(self, title: str, message: str) -> None:
        if self._deps.on_notify_info:
            self._deps.on_notify_info(title, message)
            return
        # fallback, если фабрика не прокинула notifier
        try:
            if hasattr(self.display, "show_info_notification"):
                self.display.show_info_notification(title, message)
            else:
                self.display.show_error_notification(title, message)
        except Exception:
            self.display.show_error_notification(title, message)

    def _show_titles(self, title_ids: list[int]) -> None:
        if len(title_ids) == 1:
            if self._deps.on_show_title:
                self._deps.on_show_title(title_ids[0])
            else:
                self.display.display_info(title_ids[0])
        else:
            if self._deps.on_show_titles:
                self._deps.on_show_titles(title_ids)
            else:
                self.display.display_titles(title_ids)
