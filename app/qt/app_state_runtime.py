# app/qt/app_state_runtime.py
from __future__ import annotations

import json
from typing import Any, Union, List, Dict
from app.qt.app_constants import (
    PROVIDER_ANILIBERTY, PROVIDER_ANIMEDIA,
    SHOW_DEFAULT, SHOW_SYSTEM, SHOW_ONE_TITLE,
    SHOW_AM_SCHEDULE, SHOW_AM_TITLES,
    SCHEDULE_KEY, ALL_TITLES_KEY, DEFAULT_TEMPLATE,
)
from app.qt.app_state import ViewState


def get_current_state(self) -> Dict[str, Any]:
    """Return a serialisable snapshot of the current UI state."""
    return {
        "current_title_id": self.current_title_id,
        "current_title_ids": self.current_title_ids,
        "current_day": self.current_day_of_week,
        "player_offset": self.current_offset,
        "template_name": self.current_template,
        "show_mode": self.current_show_mode,
    }

def set_view_state(self, state: ViewState) -> None:
    self.view_state = state
    self.current_show_mode = state.show_mode
    self.current_title_id = state.title_id
    self.current_title_ids = state.title_ids
    self.current_day_of_week = state.day_of_week

def restore_state(self, state: Dict[str, Any]) -> None:
    """Re-create the UI from a previously saved snapshot."""
    try:
        self.current_template = state.get("template_name", DEFAULT_TEMPLATE)
        self.logger.info("Restored template: %s", self.current_template)

        if "player_offset" in state:
            try:
                self.current_offset = int(state["player_offset"])
            except (TypeError, ValueError):
                self.current_offset = 0
            self.logger.info("Offset restored: %d", self.current_offset)

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
            self.display_animedia_schedule_screen()
        elif show_mode == SHOW_AM_TITLES:
            self.display_animedia_titles_screen()
        elif show_mode == SHOW_SYSTEM:
            self.display_titles(show_mode=SHOW_SYSTEM)
        else:
            self.logger.info("Falling back to offset-based restore")
            self.display_titles(start=True)

    except Exception as exc:
        self.logger.exception("Error restoring app state: %s", exc)

def _restore_day(self, day: int) -> None:
    self.logger.info("Restoring schedule for %s", day)
    self.current_day_of_week = day
    self.display_titles_for_day(day)

def _restore_title(self, title_id: int) -> None:
    self.logger.info("Restoring title %s", title_id)
    self.display_info(title_id)

def _restore_titles(
    self,
    title_ids: Union[str, List[int]],
    show_mode: str,
) -> None:
    """Restore a list of titles, accepting JSON‑encoded strings."""
    if isinstance(title_ids, str):
        try:
            self.logger.info("Restoring titles from JSON")
            title_ids = json.loads(title_ids)
        except json.JSONDecodeError:
            self.logger.error("Failed to decode title IDs JSON")
            title_ids = []

    count = len(title_ids)
    if count >= 12:
        self.logger.info(
            "Using titles_list mode for %d titles (show_mode=%s)",
            count,
            show_mode,
        )
        self.display_titles(
            show_mode=show_mode,
            batch_size=self.titles_list_batch_size,
            title_ids=title_ids,
        )
    else:
        self.logger.info("Using default mode for %d titles", count)
        self.display_titles(title_ids=title_ids)

def _navigate_animedia_mode(self, show_mode: str, go_forward: bool) -> bool:
    st = self.view_state or ViewState(show_mode=show_mode)

    # total_count уже посчитан при display_* и лежит в self._am_total_count
    total_count = int(self._am_total_count or 0)

    new_offset = self._calc_offset(st.am_offset, total_count, st.am_page_size, go_forward)

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
        SHOW_AM_SCHEDULE: self.display_animedia_schedule_screen,
        SHOW_AM_TITLES: self.display_animedia_titles_screen,
    }.get(mode)