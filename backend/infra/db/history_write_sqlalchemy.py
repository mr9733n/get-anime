from __future__ import annotations

from backend.core.ports.history_write import IHistoryWritePort


class SqlAlchemyHistoryWritePort(IHistoryWritePort):
    """History write operations via DatabaseManager."""

    def __init__(self, db) -> None:
        self._db = db

    def mark_watched(
        self,
        *,
        user_id: int,
        title_id: int,
        episode_id: int | None,
        is_watched: bool,
    ) -> None:
        self._db.save_watch_status(
            user_id=user_id,
            title_id=title_id,
            episode_id=episode_id,
            is_watched=is_watched,
        )

    def mark_all_watched(
        self,
        *,
        user_id: int,
        title_id: int,
        is_watched: bool,
        episode_ids: list[int] | None = None,
    ) -> int:
        affected = self._db.save_watch_all_episodes(
            user_id=user_id,
            title_id=title_id,
            is_watched=is_watched,
            episode_ids=episode_ids,
        )
        return int(affected or 0)

    def set_need_to_see(
        self,
        *,
        user_id: int,
        title_id: int,
        need_to_see: bool,
    ) -> None:
        self._db.save_need_to_see(
            user_id=user_id,
            title_id=title_id,
            need_to_see=need_to_see,
        )
