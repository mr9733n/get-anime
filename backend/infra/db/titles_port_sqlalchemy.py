from __future__ import annotations

from sqlalchemy.orm import joinedload

from backend.core.ports.titles_port import ITitlesPort

from storage.tables import (
    TitleProviderMap, Title, TitleGenreRelation, Genre, History,
    TeamMember, TitleTeamRelation, FranchiseRelease,
)


class SqlAlchemyTitlesPort(ITitlesPort):
    def __init__(self, db_manager):
        self._db = db_manager

    # --- titles ---
    def get_titles(
        self,
        *,
        show_all: bool = False,
        day_of_week: int | None = None,
        batch_size: int | None = None,
        title_id: int | None = None,
        title_ids: list[int] | None = None,
        offset: int = 0,
    ):
        return self._db.get_titles_from_db(
            show_all=show_all,
            day_of_week=day_of_week,
            batch_size=batch_size,
            title_id=title_id,
            title_ids=title_ids,
            offset=offset,
        )

    # --- search ---
    def _has_filters(
        self,
        year: int | None,
        genre: str | None,
        status_filter: str | None,
        type_filter: str | None,
        need_to_see: bool | None,
        team_member_id: int | None,
        team_member: str | None,
        franchise_id: int | None,
        sort: str | None,
    ) -> bool:
        return (
            any(x is not None for x in (year, genre, status_filter, type_filter))
            or need_to_see is True
            or team_member_id is not None
            or team_member is not None
            or franchise_id is not None
            or sort == "recent"
        )

    def _filtered_query(self, session, query: str,
                        year: int | None, genre: str | None,
                        status_filter: str | None, type_filter: str | None,
                        need_to_see: bool | None, user_id: int,
                        team_member_id: int | None, team_member: str | None,
                        franchise_id: int | None):
        """
        #9: SQLAlchemy query that applies optional filters.
        Falls back to legacy get_titles_search_query when no filters given.
        """
        q = session.query(Title.title_id)

        # Text search (name_ru / name_en / alternative_name)
        if query:
            like = f"%{query}%"
            q = q.filter(
                Title.name_ru.ilike(like)
                | Title.name_en.ilike(like)
                | Title.alternative_name.ilike(like)
            )

        if year is not None:
            q = q.filter(Title.season_year == year)

        if status_filter:
            q = q.filter(Title.status_string.ilike(f"%{status_filter}%"))

        if type_filter:
            q = q.filter(Title.type_string.ilike(f"%{type_filter}%"))

        if genre:
            q = (
                q.join(TitleGenreRelation, TitleGenreRelation.title_id == Title.title_id)
                 .join(Genre, Genre.genre_id == TitleGenreRelation.genre_id)
                 .filter(Genre.name.ilike(f"%{genre}%"))
            )

        if team_member_id is not None:
            q = (
                q.join(TitleTeamRelation, TitleTeamRelation.title_id == Title.title_id)
                 .filter(TitleTeamRelation.team_member_id == int(team_member_id))
                 .distinct()
            )
        elif team_member:
            q = (
                q.join(TitleTeamRelation, TitleTeamRelation.title_id == Title.title_id)
                 .join(TeamMember, TeamMember.id == TitleTeamRelation.team_member_id)
                 .filter(TeamMember.name.ilike(f"%{team_member}%"))
                 .distinct()
            )

        if franchise_id is not None:
            q = (
                q.join(FranchiseRelease, FranchiseRelease.title_id == Title.title_id)
                 .filter(FranchiseRelease.franchise_id == int(franchise_id))
                 .distinct()
            )

        if need_to_see is True:
            q = (
                q.join(History, History.title_id == Title.title_id)
                 .filter(History.user_id == int(user_id))
                 .filter(History.need_to_see.is_(True))
                 .distinct()
            )

        return q

    def _ordered_query(self, q, sort: str | None):
        if sort == "recent":
            return q.order_by(
                Title.last_updated.desc(),
                Title.updated.desc(),
                Title.title_id.desc(),
            )
        return q.order_by(Title.title_id.desc())

    def search_title_ids(
        self,
        query: str,
        *,
        limit: int = 50,
        offset: int = 0,
        year: int | None = None,
        genre: str | None = None,
        status_filter: str | None = None,
        type_filter: str | None = None,
        need_to_see: bool | None = None,
        team_member_id: int | None = None,
        team_member: str | None = None,
        franchise_id: int | None = None,
        user_id: int = 42,
        sort: str | None = None,
    ) -> list[int]:
        """
        When any filter is set, use a direct SQLAlchemy query.
        Without filters, delegate to the legacy get_titles_search_query.
        """
        sort = (sort or "").strip().lower() or None
        if self._has_filters(
            year, genre, status_filter, type_filter, need_to_see,
            team_member_id, team_member, franchise_id, sort,
        ):
            with self._db.Session() as session:
                q = self._filtered_query(
                    session, query or "", year, genre, status_filter, type_filter, need_to_see, user_id,
                    team_member_id, team_member, franchise_id,
                )
                rows = self._ordered_query(q, sort).offset(int(offset)).limit(int(limit)).all()
                return [int(r[0]) for r in rows]

        # Legacy path (no filters)
        rows = self._db.get_titles_search_query(query=query)  # list[dict]
        ids: list[int] = []
        for r in rows or []:
            if isinstance(r, dict) and "title_id" in r:
                try:
                    ids.append(int(r["title_id"]))
                except Exception:
                    continue
        if offset:
            ids = ids[int(offset):]
        if limit is not None:
            ids = ids[: int(limit)]
        return ids

    def search_title_ids_with_providers(self, query: str) -> tuple[list[int], list[str]]:
        """
        Быстрый поиск (для titles_ids.search): используем существующий DbManager.get_titles_by_keywords.
        """
        title_ids, providers = self._db.get_titles_by_keywords(query)
        title_ids = [int(x) for x in (title_ids or [])]
        providers = list(providers or [])
        return title_ids, providers

    def count_search_titles(
        self,
        query: str,
        *,
        year: int | None = None,
        genre: str | None = None,
        status_filter: str | None = None,
        type_filter: str | None = None,
        need_to_see: bool | None = None,
        team_member_id: int | None = None,
        team_member: str | None = None,
        franchise_id: int | None = None,
        user_id: int = 42,
        sort: str | None = None,
    ) -> int:
        sort = (sort or "").strip().lower() or None
        if self._has_filters(
            year, genre, status_filter, type_filter, need_to_see,
            team_member_id, team_member, franchise_id, sort,
        ):
            with self._db.Session() as session:
                q = self._filtered_query(
                    session, query or "", year, genre, status_filter, type_filter, need_to_see, user_id,
                    team_member_id, team_member, franchise_id,
                )
                return q.count()
        rows = self._db.get_titles_search_query(query=query)
        return len(rows) if rows else 0

    # --- provider links ---
    def get_provider_links_map(self, title_ids: list[int]) -> dict[int, list[dict]]:
        """
        Это НЕ DbManager метод, поэтому реализуем тут (infra).
        Никаких вызовов из controller, только через порт.
        """
        if not title_ids:
            return {}

        title_ids = [int(x) for x in title_ids]
        out: dict[int, list[dict]] = {tid: [] for tid in title_ids}

        with self._db.Session() as session:
            links = (
                session.query(TitleProviderMap)
                .options(joinedload(TitleProviderMap.provider))
                .filter(TitleProviderMap.title_id.in_(title_ids))
                .all()
            )

            for link in links:
                tid = int(getattr(link, "title_id"))
                p = getattr(link, "provider", None)
                out.setdefault(tid, []).append(
                    {
                        "id": int(getattr(link, "id")),
                        "provider_id": int(getattr(link, "provider_id")),
                        "provider_code": getattr(p, "code", None) if p else None,
                        "provider_name": getattr(p, "name", None) if p else None,
                        "external_title_id": str(getattr(link, "external_title_id")),
                    }
                )

        return out
