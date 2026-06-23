from __future__ import annotations

from backend.core.dto.history import (
    MarkWatchedResult,
    MarkAllWatchedResult,
    NeedToSeeResult,
)
from backend.core.ports.history_write import IHistoryWritePort


class HistoryController:
    """User watch history and watchlist write operations."""

    def __init__(self, write_port: IHistoryWritePort) -> None:
        self._write = write_port

    def mark_watched(
        self,
        *,
        user_id: int,
        title_id: int,
        episode_id: int | None,
        is_watched: bool,
    ) -> MarkWatchedResult:
        try:
            self._write.mark_watched(
                user_id=user_id,
                title_id=title_id,
                episode_id=episode_id,
                is_watched=is_watched,
            )
            return MarkWatchedResult(
                ok=True,
                title_id=title_id,
                episode_id=episode_id,
                is_watched=is_watched,
            )
        except Exception as exc:
            return MarkWatchedResult(
                ok=False,
                title_id=title_id,
                episode_id=episode_id,
                is_watched=is_watched,
                error=str(exc),
            )

    def mark_all_watched(
        self,
        *,
        user_id: int,
        title_id: int,
        is_watched: bool,
        episode_ids: list[int] | None = None,
    ) -> MarkAllWatchedResult:
        try:
            affected = self._write.mark_all_watched(
                user_id=user_id,
                title_id=title_id,
                is_watched=is_watched,
                episode_ids=episode_ids,
            )
            return MarkAllWatchedResult(
                ok=True,
                title_id=title_id,
                is_watched=is_watched,
                episodes_affected=affected,
            )
        except Exception as exc:
            return MarkAllWatchedResult(
                ok=False,
                title_id=title_id,
                is_watched=is_watched,
                episodes_affected=0,
                error=str(exc),
            )

    def set_need_to_see(
        self,
        *,
        user_id: int,
        title_id: int,
        need_to_see: bool,
    ) -> NeedToSeeResult:
        try:
            self._write.set_need_to_see(
                user_id=user_id,
                title_id=title_id,
                need_to_see=need_to_see,
            )
            return NeedToSeeResult(
                ok=True,
                title_id=title_id,
                need_to_see=need_to_see,
            )
        except Exception as exc:
            return NeedToSeeResult(
                ok=False,
                title_id=title_id,
                need_to_see=need_to_see,
                error=str(exc),
            )
