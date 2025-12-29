# app/qt/controllers/state_runtime.py
from __future__ import annotations

import json
from typing import Any, Union, List, Dict
from app.qt.app_constants import (
    SHOW_DEFAULT, SHOW_SYSTEM, DEFAULT_TEMPLATE,
    SHOW_AM_SCHEDULE, SHOW_AM_TITLES, LIST_MODES,
)
from app.qt.app_state import ViewState

class StateRuntimeController:
    """
    Переходный контроллер (stage-2/3):
    - svc: доступ к db/api/ui/logger/config/playlist
    - app: доступ к orchestration-методам (display_titles, show_error_notification, invoke_database_save, ...)
    """

    def __init__(self, app: Any, svc: Any):
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

    def get_current_state(self) -> Dict[str, Any]:
        """Return a serialisable snapshot of the current UI state."""
        return {
            "current_title_id": self.app.current_title_id,
            "current_title_ids": self.app.current_title_ids,
            "current_day": self.app.current_day_of_week,
            "player_offset": self.app.current_offset,
            "template_name": self.app.current_template,
            "show_mode": self.app.current_show_mode,
        }

    def set_view_state(self, state: ViewState) -> None:
        self.app.view_state = state
        self.app.current_show_mode = state.show_mode
        self.app.current_title_id = state.title_id
        self.app.current_title_ids = state.title_ids
        self.app.current_day_of_week = state.day_of_week

    def restore_state(self, state: Dict[str, Any]) -> None:
        """Re-create the UI from a previously saved snapshot."""
        try:
            self.app.current_template = state.get("template_name", DEFAULT_TEMPLATE)
            self.log.info("Restored template: %s", self.app.current_template)

            if "player_offset" in state:
                try:
                    self.app.current_offset = int(state["player_offset"])
                except (TypeError, ValueError):
                    self.app.current_offset = 0
                self.log.info("Offset restored: %d", self.app.current_offset)

            day = state.get("current_day")
            title_id = state.get("current_title_id")
            title_ids = state.get("current_title_ids")
            show_mode = state.get("show_mode", SHOW_DEFAULT)

            has_day = day is not None
            has_title_id = title_id is not None
            has_title_ids = bool(title_ids)

            if has_day and not has_title_id and not has_title_ids:
                self._restore_day(day)
            elif has_day and has_title_id and not has_title_ids:
                self._restore_title(title_id)
            elif not has_day and has_title_id:
                self._restore_title(title_id)
            elif has_title_ids:
                self._restore_titles(title_ids, show_mode)
            elif show_mode == SHOW_AM_SCHEDULE:
                self.app.display_animedia_schedule_screen()
            elif show_mode == SHOW_AM_TITLES:
                self.app.display_animedia_titles_screen()
            elif show_mode == SHOW_SYSTEM:
                self.app.display_titles(show_mode=SHOW_SYSTEM)
            else:
                self.log.info("Falling back to offset-based restore")
                self.app.display_titles(start=True)

        except Exception as exc:
            self.log.exception("Error restoring app state: %s", exc)

    def _restore_day(self, day: int) -> None:
        self.log.info("Restoring schedule for %s", day)
        self.app.current_day_of_week = day
        self.app.display_titles_for_day(day)

    def _restore_title(self, title_id: int) -> None:
        self.log.info("Restoring title %s", title_id)
        self.app.display_info(title_id)

    def _restore_titles(
        self,
        title_ids: Union[str, List[int]],
        show_mode: str,
    ) -> None:
        """Restore a list of titles, accepting JSON‑encoded strings."""
        if isinstance(title_ids, str):
            try:
                self.log.info("Restoring titles from JSON")
                title_ids = json.loads(title_ids)
            except json.JSONDecodeError:
                self.log.error("Failed to decode title IDs JSON")
                title_ids = []

        if show_mode in LIST_MODES:
            # Восстанавливаем режим + offset, без фиксированной выборки title_ids
            self.app.display_titles(
                show_mode=show_mode,
                batch_size=self.app.titles_list_batch_size,
            )
            return

        count = len(title_ids)
        if count >= 12:
            self.log.info(
                "Using titles_list mode for %d titles (show_mode=%s)",
                count,
                show_mode,
            )
            self.app.display_titles(
                show_mode=show_mode,
                batch_size=self.app.titles_list_batch_size,
                title_ids=title_ids,
            )
        else:
            self.log.info("Using default mode for %d titles", count)
            self.app.display_titles(title_ids=title_ids)

    def navigate_animedia_mode(self, show_mode: str, go_forward: bool) -> bool:
        st = self.app.view_state or ViewState(show_mode=show_mode)

        # total_count уже посчитан при display_* и лежит в self._am_total_count
        total_count = int(self.app.am_total_count or 0)

        new_offset = self.app.calc_offset(st.am_offset, total_count, st.am_page_size, go_forward)

        self.set_view_state(ViewState(
            show_mode=show_mode,
            am_offset=new_offset,
            am_page_size=st.am_page_size,
        ))

        display_fn = self._animedia_display_for_mode(show_mode)
        if not display_fn:
            return False
        display_fn()
        return True

    def _animedia_display_for_mode(self, mode: str):
        return {
            SHOW_AM_SCHEDULE: self.app.display_animedia_schedule_screen,
            SHOW_AM_TITLES: self.app.display_animedia_titles_screen,
        }.get(mode)