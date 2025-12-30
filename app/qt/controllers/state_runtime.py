# app/qt/controllers/state_runtime.py
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable

from app.qt.app_constants import (
    SHOW_DEFAULT, SHOW_SYSTEM, DEFAULT_TEMPLATE,
    SHOW_AM_SCHEDULE, SHOW_AM_TITLES, LIST_MODES,
)
from app.qt.app_state import ViewState
from app.qt.protocols import IDisplayController, IDBManager

if TYPE_CHECKING:
    from logging import Logger
    from app.qt.app_context import AppContext


@dataclass
class StateRuntimeControllerDeps:
    """Явные зависимости StateRuntimeController"""
    logger: Logger
    db: IDBManager
    context: AppContext

    # Lazy callbacks
    get_display_controller: Callable[[], IDisplayController] | None = None
    get_animedia_controller: Callable[[], Any] | None = None  # ← ДОБАВИТЬ


class StateRuntimeController:
    """
    Контроллер управления состоянием приложения.
    Отвечает за ViewState, сохранение/восстановление состояния.
    """

    def __init__(self, deps: StateRuntimeControllerDeps):
        self._deps = deps
        self._display: IDisplayController | None = None
        self._animedia = None

    # === Lazy Dependencies ===

    @property
    def display(self) -> IDisplayController:
        """Ленивая загрузка DisplayController."""
        if self._display is None:
            if self._deps.get_display_controller:
                self._display = self._deps.get_display_controller()
            else:
                raise RuntimeError("DisplayController not configured")
        return self._display

    @property
    def animedia(self):
        """Ленивая загрузка AniMediaController."""
        if self._animedia is None:
            if self._deps.get_animedia_controller:
                self._animedia = self._deps.get_animedia_controller()
        return self._animedia

    # === Simple Properties ===

    @property
    def log(self) -> Logger:
        return self._deps.logger

    @property
    def db(self) -> IDBManager:
        return self._deps.db

    @property
    def ctx(self) -> AppContext:
        return self._deps.context

    # === Public API: State Management ===

    def get_current_state(self) -> dict[str, Any]:
        """Возвращает сериализуемый снимок текущего состояния."""
        return {
            "current_title_id": self.ctx.current_title_id,
            "current_title_ids": self.ctx.current_title_ids,
            "current_day": self.ctx.current_day_of_week,
            "player_offset": self.ctx.current_offset,
            "template_name": self.ctx.current_template,
            "show_mode": self.ctx.current_show_mode,
        }

    def set_view_state(self, state: ViewState) -> None:
        """Устанавливает текущее состояние отображения."""
        self.ctx.view_state = state
        self.ctx.current_show_mode = state.show_mode
        self.ctx.current_title_id = state.title_id
        self.ctx.current_title_ids = state.title_ids
        self.ctx.current_day_of_week = state.day_of_week

    def restore_state(self, state: dict[str, Any]) -> None:
        """Восстанавливает UI из сохранённого снимка состояния."""
        try:
            self._restore_template(state)
            self._restore_offset(state)
            self._restore_view(state)

        except Exception as exc:
            self.log.exception(f"Error restoring app state: {exc}")

    # === Public API: Navigation ===

    def navigate_animedia_mode(self, show_mode: str, go_forward: bool) -> bool:
        """Навигация по страницам AniMedia режимов."""
        st = self.ctx.view_state or ViewState(show_mode=show_mode)
        total_count = self.ctx.am_total_count or 0

        new_offset = self._calc_offset(st.am_offset, total_count, st.am_page_size, go_forward)

        self.set_view_state(ViewState(
            show_mode=show_mode,
            am_offset=new_offset,
            am_page_size=st.am_page_size,
        ))

        display_fn = self._get_animedia_display_fn(show_mode)
        if not display_fn:
            return False

        display_fn()
        return True

    # === Private: Restore Helpers ===

    def _restore_template(self, state: dict[str, Any]) -> None:
        """Восстанавливает шаблон."""
        self.ctx.current_template = state.get("template_name", DEFAULT_TEMPLATE)
        self.log.info(f"Restored template: {self.ctx.current_template}")

    def _restore_offset(self, state: dict[str, Any]) -> None:
        """Восстанавливает offset пагинации."""
        if "player_offset" in state:
            try:
                self.ctx.current_offset = int(state["player_offset"])
            except (TypeError, ValueError):
                self.ctx.current_offset = 0
            self.log.info(f"Offset restored: {self.ctx.current_offset}")

    def _restore_view(self, state: dict[str, Any]) -> None:
        """Восстанавливает вид в зависимости от сохранённого состояния."""
        day = state.get("current_day")
        title_id = state.get("current_title_id")
        title_ids = state.get("current_title_ids")
        show_mode = state.get("show_mode", SHOW_DEFAULT)

        # Определяем стратегию восстановления
        strategy = self._determine_restore_strategy(day, title_id, title_ids, show_mode)
        strategy()

    def _determine_restore_strategy(
            self,
            day: int | None,
            title_id: int | None,
            title_ids: list[int] | str | None,
            show_mode: str,
    ) -> Callable[[], None]:
        """Определяет стратегию восстановления на основе состояния."""
        has_day = day is not None
        has_title_id = title_id is not None
        has_title_ids = bool(title_ids)

        if has_day and not has_title_id and not has_title_ids:
            return lambda: self._restore_day(day)

        if has_title_id and (not has_title_ids or (has_day and has_title_id)):
            return lambda: self._restore_title(title_id)

        if has_title_ids:
            return lambda: self._restore_titles(title_ids, show_mode)

        if show_mode == SHOW_AM_SCHEDULE:
            return self._restore_animedia_schedule

        if show_mode == SHOW_AM_TITLES:
            return self._restore_animedia_titles

        if show_mode == SHOW_SYSTEM:
            return lambda: self.display.display_titles(show_mode=SHOW_SYSTEM)

        # Fallback
        return lambda: self._restore_default()

    def _restore_day(self, day: int) -> None:
        """Восстанавливает расписание для дня."""
        self.log.info(f"Restoring schedule for day {day}")
        self.ctx.current_day_of_week = day
        self.display.display_titles_for_day(day)

    def _restore_title(self, title_id: int) -> None:
        """Восстанавливает один тайтл."""
        self.log.info(f"Restoring title {title_id}")
        self.display.display_info(title_id)

    def _restore_titles(self, title_ids: list[int] | str, show_mode: str) -> None:
        """Восстанавливает список тайтлов."""
        # Декодируем JSON если нужно
        if isinstance(title_ids, str):
            try:
                title_ids = json.loads(title_ids)
            except json.JSONDecodeError:
                self.log.error("Failed to decode title IDs JSON")
                title_ids = []

        if show_mode in LIST_MODES:
            # Режим списка — восстанавливаем через offset
            self.display.display_titles(
                show_mode=show_mode,
                batch_size=self.ctx.titles_list_batch_size,
            )
            return

        count = len(title_ids)
        if count >= 12:
            self.log.info(f"Using titles_list mode for {count} titles")
            self.display.display_titles(
                show_mode=show_mode,
                batch_size=self.ctx.titles_list_batch_size,
                title_ids=title_ids,
            )
        else:
            self.log.info(f"Using default mode for {count} titles")
            self.display.display_titles(title_ids=title_ids)

    def _restore_animedia_schedule(self) -> None:
        """Восстанавливает AniMedia schedule screen."""
        self.log.info("Restoring AniMedia schedule screen")
        if self.animedia:
            self.animedia.display_animedia_schedule_screen()

    def _restore_animedia_titles(self) -> None:
        """Восстанавливает AniMedia titles screen."""
        self.log.info("Restoring AniMedia titles screen")
        if self.animedia:
            self.animedia.display_animedia_titles_screen()

    def _restore_default(self) -> None:
        """Восстановление по умолчанию."""
        self.log.info("Falling back to offset-based restore")
        self.display.display_titles(start=True)

    # === Private: Navigation Helpers ===

    def _get_animedia_display_fn(self, mode: str) -> Callable[[], None] | None:
        """Возвращает функцию отображения для AniMedia режима."""
        if not self.animedia:
            return None

        mapping = {
            SHOW_AM_SCHEDULE: self.animedia.display_animedia_schedule_screen,
            SHOW_AM_TITLES: self.animedia.display_animedia_titles_screen,
        }
        return mapping.get(mode)

    @staticmethod
    def _calc_offset(offset: int, total: int, page_size: int, go_forward: bool) -> int:
        """Вычисляет новый offset для пагинации."""
        if total <= 0:
            return 0
        if go_forward:
            return 0 if offset + page_size >= total else offset + page_size
        return max(0, offset - page_size)