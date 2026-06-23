from __future__ import annotations
from typing import Protocol, Any
from backend.core.dto.titles import TitleViewMode

class ITitlesEnricherPort(Protocol):
    def enrich_titles(
        self,
        titles: list[Any],
        *,
        user_id: int,
        view_mode: TitleViewMode = TitleViewMode.FULL,
    ) -> list[Any]:
        """Мутирует/обогащает ORM Title (через _pref_*), возвращает titles.
        TitleViewMode.CARD — пропускает тяжёлые per-episode/per-torrent запросы."""
        ...
