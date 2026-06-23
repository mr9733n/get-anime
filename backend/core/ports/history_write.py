from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class IHistoryWritePort(Protocol):
    """Write port for user watch history and watchlist."""

    def mark_watched(
        self,
        *,
        user_id: int,
        title_id: int,
        episode_id: int | None,
        is_watched: bool,
    ) -> None:
        """Mark a single episode (or the whole title) as watched/unwatched."""
        ...

    def mark_all_watched(
        self,
        *,
        user_id: int,
        title_id: int,
        is_watched: bool,
        episode_ids: list[int] | None = None,
    ) -> int:
        """
        Mark all episodes of a title watched/unwatched.

        episode_ids: explicit list to mark; None = all episodes.
        Returns number of records affected.
        """
        ...

    def set_need_to_see(
        self,
        *,
        user_id: int,
        title_id: int,
        need_to_see: bool,
    ) -> None:
        """Add or remove a title from the user's watchlist."""
        ...
