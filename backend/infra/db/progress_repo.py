from __future__ import annotations

from sqlalchemy import func

from storage.tables import History, Episode


class SqlAlchemyProgressRepo:
    def __init__(self, session_factory):
        self._Session = session_factory

    def get_last_watched_episode_numbers(self, *, user_id: int, title_ids: list[int]) -> dict[int, int]:
        title_ids = [int(x) for x in (title_ids or [])]
        if not title_ids:
            return {}

        with self._Session() as session:
            rows = (
                session.query(
                    History.title_id.label("title_id"),
                    func.max(Episode.episode_number).label("max_ep"),
                )
                .join(Episode, Episode.episode_id == History.episode_id)
                .filter(History.user_id == int(user_id))
                .filter(History.title_id.in_(title_ids))
                .filter(History.is_watched == True)
                .group_by(History.title_id)
                .all()
            )
            out = {int(r.title_id): int(r.max_ep or 0) for r in rows}
            # fill zeros for missing
            for tid in title_ids:
                out.setdefault(int(tid), 0)
            return out
