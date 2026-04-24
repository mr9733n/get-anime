from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MarkWatchedResult:
    """Result of history.mark_watched op."""
    ok: bool
    title_id: int
    episode_id: int | None
    is_watched: bool
    error: str | None = None


@dataclass(frozen=True)
class MarkAllWatchedResult:
    """Result of history.mark_all_watched op."""
    ok: bool
    title_id: int
    is_watched: bool
    episodes_affected: int
    error: str | None = None


@dataclass(frozen=True)
class NeedToSeeResult:
    """Result of history.set_need_to_see op."""
    ok: bool
    title_id: int
    need_to_see: bool
    error: str | None = None
