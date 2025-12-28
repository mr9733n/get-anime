# app/qt/app_state.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, List

from app.qt.app_constants import SHOW_DEFAULT


@dataclass
class TitleRef:
    title_id: int
    name_ru: str | None
    name_en: str | None
    provider: str | None
    provider_name: str | None
    external_id: str | None


@dataclass(frozen=True)
class ViewState:
    show_mode: str = SHOW_DEFAULT
    title_id: Optional[int] = None
    title_ids: Optional[List[int]] = None
    day_of_week: Optional[int] = None
    am_offset: int = 0
    am_page_size: int = 12
