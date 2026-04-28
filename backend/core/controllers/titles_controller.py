from __future__ import annotations

from backend.core.dto.titles import (
    TitleViewMode, TitleDetailsDTO, TitleCardDTO,
    EpisodeDTO, GenreDTO, FranchiseDTO, TeamMemberDTO,
    TorrentDTO, ProviderLinkDTO, ProductionStudioDTO, RatingDTO, HistoryDTO, ScheduleDTO,
)
from backend.core.dto.search import TitlesSearchResult
from backend.core.utils.urls import make_base_url, abs_url, abs_asset_url, normalize_provider_code, norm_str
from backend.core.ports.titles_enricher_port import ITitlesEnricherPort
from backend.core.ports.titles_port import ITitlesPort


class TitlesController:
    def __init__(self, titles_port: ITitlesPort, enricher: ITitlesEnricherPort, logger=None, config_manager=None):
        self._titles = titles_port
        self._enricher = enricher
        self.log = logger
        self.cfg = config_manager

    # -----------------------
    # titles.search (DB-only)
    # -----------------------
    def titles_ids_search(
            self,
            query: str,
            provider: str | None = None,
    ) -> TitlesSearchResult:
        query = (query or "").strip()
        if not query:
            return TitlesSearchResult(title_ids=[], providers=[])

        title_ids, providers = self._titles.search_title_ids_with_providers(query)
        title_ids = list(title_ids or [])
        providers = list(providers or [])

        # provider-filter (если у тебя providers параллелен title_ids)
        if provider:
            provider = str(provider).strip().lower()
            filtered_ids: list[int] = []
            filtered_providers: list[str] = []
            for tid, p in zip(title_ids, providers):
                if (p or "").lower() == provider:
                    filtered_ids.append(int(tid))
                    filtered_providers.append(p)
            title_ids, providers = filtered_ids, filtered_providers

        return TitlesSearchResult(title_ids=[int(x) for x in title_ids], providers=providers)

    def titles_search(
        self,
        query: str,
        *,
        user_id: int = 42,
        enrich: bool = True,
        limit: int = 50,
        offset: int = 0,
        view_mode: TitleViewMode = TitleViewMode.FULL,
        # #9 filters
        year: int | None = None,
        genre: str | None = None,
        status_filter: str | None = None,
        type_filter: str | None = None,
        need_to_see: bool | None = None,
        team_member_id: int | None = None,
        team_member: str | None = None,
        franchise_id: int | None = None,
        sort: str | None = None,
    ):
        title_ids = self._titles.search_title_ids(
            query=query, limit=limit, offset=offset,
            year=year, genre=genre,
            status_filter=status_filter, type_filter=type_filter,
            need_to_see=need_to_see,
            team_member_id=team_member_id,
            team_member=team_member,
            franchise_id=franchise_id,
            user_id=user_id,
            sort=sort,
        )
        if not title_ids:
            return []

        titles = self._titles.get_titles(title_ids=title_ids, show_all=True)
        titles = self._maybe_enrich(titles, user_id=user_id, enrich=enrich, view_mode=view_mode)

        # provider links
        links_map = self._titles.get_provider_links_map(title_ids)
        for t in titles:
            setattr(t, "_pref_provider_links", links_map.get(int(getattr(t, "title_id")), []))

        out = self._titles_return_card(titles) if view_mode == TitleViewMode.CARD else self._titles_return(titles)

        # сохранить порядок поиска
        order = {tid: i for i, tid in enumerate(title_ids)}
        out.sort(key=lambda dto: order.get(int(dto.title_id), 10 ** 9))
        return out

    def count_titles(
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
        """Total number of DB titles matching query + optional filters (for pagination)."""
        return self._titles.count_search_titles(
            query=(query or "").strip(),
            year=year, genre=genre,
            status_filter=status_filter, type_filter=type_filter,
            need_to_see=need_to_see,
            team_member_id=team_member_id,
            team_member=team_member,
            franchise_id=franchise_id,
            user_id=user_id,
            sort=sort,
        )

    # -----------------------
    # titles.get (DB-only)
    # -----------------------
    def titles_get(self, title_ids: list[int], *, user_id: int = 42, enrich: bool = True, view_mode: TitleViewMode = TitleViewMode.FULL):
        title_ids = [int(x) for x in (title_ids or [])]
        if not title_ids:
            return []

        titles = self._titles.get_titles(title_ids=title_ids, show_all=True)
        titles = self._maybe_enrich(titles, user_id=user_id, enrich=enrich, view_mode=view_mode)

        # provider links (batched)
        links_map = self._titles.get_provider_links_map(title_ids)
        for t in titles:
            setattr(t, "_pref_provider_links", links_map.get(int(getattr(t, "title_id")), []))

        if not titles:
            return []

        out = self._titles_return_card(titles) if view_mode == TitleViewMode.CARD else self._titles_return(titles)

        # фикс порядка входных id
        index = {tid: i for i, tid in enumerate(title_ids)}
        out.sort(key=lambda dto: index.get(int(dto.title_id), 10**9))
        return out

    def title_get(self, title_id: int, *, user_id: int = 41, enrich: bool = True, view_mode: TitleViewMode = TitleViewMode.FULL):
        title = self._titles.get_titles(title_id=title_id, show_all=True)
        title = self._maybe_enrich(title, user_id=user_id, enrich=enrich, view_mode=view_mode)

        if not title:
            raise ValueError(f"title_id not found: {title_id}")

        out = self._titles_return_card(title) if view_mode == TitleViewMode.CARD else self._titles_return(title)
        return out[0]

    # -----------------------
    # episodes.list (DB-only)
    # -----------------------
    def titles_list_episodes(self, title_ids: list[int]) -> dict[int, list[EpisodeDTO]]:
        title_ids = [int(x) for x in (title_ids or [])]
        titles = self._titles.get_titles(title_ids=title_ids, show_all=True)
        if not titles:
            return {}

        episodes_by_title: dict[int, list[EpisodeDTO]] = {}
        for t in titles:
            tid = int(getattr(t, "title_id"))
            eps = getattr(t, "episodes", []) or []
            items: list[EpisodeDTO] = []
            host = norm_str(getattr(t, "host_for_player", None))
            stream_base = make_base_url(host)
            provider_raw = getattr(t, "_pref_provider", None)
            provider_code = normalize_provider_code(provider_raw)
            for e in eps:
                items.append(self._episode_to_dto(e, provider_code=provider_code, stream_base=stream_base))
            episodes_by_title[tid] = items

        return episodes_by_title

    def title_list_episodes(self, title_id: int) -> list[EpisodeDTO]:
        m = self.titles_list_episodes([int(title_id)])
        items = m.get(int(title_id))
        if items is None:
            raise ValueError(f"title_id not found: {title_id}")
        return items

    # -----------------------
    # internal mapping helpers
    # -----------------------
    def _maybe_enrich(self, titles: list, user_id: int = 42, enrich: bool = True, view_mode: TitleViewMode = TitleViewMode.FULL) -> list:
        if not enrich or not titles:
            return titles
        try:
            return self._enricher.enrich_titles(titles, user_id=user_id, view_mode=view_mode)
        except Exception as e:
            if self.log:
                self.log.warning(f"titles enrich failed: {e}", exc_info=True)
            return titles

    def _genre_rel_to_dto(self, rel) -> GenreDTO:
        g = getattr(rel, "genre", None)
        return GenreDTO(
            genre_id=int(getattr(g, "genre_id", 0)) if g and getattr(g, "genre_id", None) is not None else None,
            name=getattr(g, "name", None) if g else None,
        )

    def _schedule_to_dto(self, sc) -> ScheduleDTO:
        day = getattr(sc, "day", None)
        return ScheduleDTO(
            day_of_week=int(getattr(sc, "day_of_week")),
            day_name=getattr(day, "day_name", None) if day else None,
            last_updated=getattr(sc, "last_updated", None),
        )

    def _franchise_to_dto(self, fr) -> FranchiseDTO:
        """
        Важно: не трогаем fr.franchise (relationship), чтобы не ловить lazy-load
        на отсоединённом ORM объекте.
        """
        if isinstance(fr, dict):
            return FranchiseDTO(
                id=int(fr.get("id", 0)),
                franchise_id=int(fr.get("franchise_id", 0)),
                code=fr.get("code"),
                ordinal=fr.get("ordinal"),
                name_ru=fr.get("name_ru"),
                name_en=fr.get("name_en"),
                name_alternative=fr.get("name_alternative"),
                franchise_name=fr.get("franchise_name"),
                related_title_id=fr.get("related_title_id"),
                related_title_name_ru=fr.get("related_title_name_ru"),
                related_title_name_en=fr.get("related_title_name_en"),
            )

        related_title_id = getattr(fr, "title_id", None)
        if related_title_id is not None:
            rels = getattr(fr, "franchises", []) or []
            first_rel = rels[0] if rels else None
            franchise_obj = getattr(first_rel, "franchise", None) if first_rel else None
            return FranchiseDTO(
                id=int(getattr(first_rel, "id", 0)) if first_rel else 0,
                franchise_id=int(getattr(first_rel, "franchise_id", 0)) if first_rel else 0,
                code=getattr(first_rel, "code", None) if first_rel else None,
                ordinal=getattr(first_rel, "ordinal", None) if first_rel else None,
                name_ru=getattr(first_rel, "name_ru", None) if first_rel else None,
                name_en=getattr(first_rel, "name_en", None) if first_rel else None,
                name_alternative=getattr(first_rel, "name_alternative", None) if first_rel else None,
                franchise_name=getattr(franchise_obj, "franchise_name", None) if franchise_obj else None,
                related_title_id=int(related_title_id),
                related_title_name_ru=getattr(fr, "name_ru", None),
                related_title_name_en=getattr(fr, "name_en", None),
            )

        return FranchiseDTO(
            id=int(getattr(fr, "id", 0)),
            franchise_id=int(getattr(fr, "franchise_id", 0)),
            code=getattr(fr, "code", None),
            ordinal=getattr(fr, "ordinal", None),
            name_ru=getattr(fr, "name_ru", None),
            name_en=getattr(fr, "name_en", None),
            name_alternative=getattr(fr, "name_alternative", None),
            franchise_name=None,
        )

    def _team_rel_to_dto(self, rel) -> TeamMemberDTO:
        m = getattr(rel, "team_member", None)
        return TeamMemberDTO(
            id=int(getattr(m, "id")),
            name=str(getattr(m, "name", "")),
            role=str(getattr(m, "role", "")),
        )

    def _torrent_to_dto(self, tr, *, provider_code: str | None, stream_base: str | None) -> TorrentDTO:
        url = norm_str(getattr(tr, "url", None))
        return TorrentDTO(
            torrent_id=int(getattr(tr, "torrent_id")),
            episodes_range=getattr(tr, "episodes_range", None),
            range_first=getattr(tr, "range_first", None),
            range_last=getattr(tr, "range_last", None),
            quality=getattr(tr, "quality", None),
            quality_type=getattr(tr, "quality_type", None),
            resolution=getattr(tr, "resolution", None),
            encoder=getattr(tr, "encoder", None),
            leechers=getattr(tr, "leechers", None),
            seeders=getattr(tr, "seeders", None),
            downloads=getattr(tr, "downloads", None),
            total_size=getattr(tr, "total_size", None),
            size_string=getattr(tr, "size_string", None),
            url=abs_asset_url(provider_code, self.cfg, url, fallback_base=stream_base),
            magnet_link=getattr(tr, "magnet_link", None),
            uploaded_timestamp=getattr(tr, "uploaded_timestamp", None),
            api_updated_at=getattr(tr, "api_updated_at", None),
            label=getattr(tr, "label", None),
            filename=getattr(tr, "filename", None),
            hash=getattr(tr, "hash", None),
        )

    def _provider_link_to_dto(self, pl) -> ProviderLinkDTO:
        p = getattr(pl, "provider", None)
        return ProviderLinkDTO(
            id=int(getattr(pl, "id")),
            provider_id=int(getattr(pl, "provider_id")),
            provider_code=getattr(p, "code", None) if p else None,
            provider_name=getattr(p, "name", None) if p else None,
            external_title_id=str(getattr(pl, "external_title_id")),
        )

    def _production_studio_to_dto(self, ps) -> ProductionStudioDTO:
        return ProductionStudioDTO(
            id=int(getattr(ps, "id")),
            name=str(getattr(ps, "name", "")),
        )

    def _rating_to_dto(self, r) -> RatingDTO:
        return RatingDTO(
            rating_id=int(getattr(r, "rating_id")),
            rating_name=str(getattr(r, "rating_name", "")),
            rating_value=int(getattr(r, "rating_value", 0)),
            name_external=getattr(r, "name_external", None),
            score_external=getattr(r, "score_external", None),
            last_updated=getattr(r, "last_updated", None),
        )

    def _history_to_dto(self, h) -> HistoryDTO:
        return HistoryDTO(
            id=int(getattr(h, "id")),
            user_id=int(getattr(h, "user_id")),
            title_id=int(getattr(h, "title_id")),
            episode_id=getattr(h, "episode_id", None),
            torrent_id=getattr(h, "torrent_id", None),
            is_watched=bool(getattr(h, "is_watched", False)),
            last_watched_at=getattr(h, "last_watched_at", None),
            previous_watched_at=getattr(h, "previous_watched_at", None),
            watch_change_count=getattr(h, "watch_change_count", None),
            is_download=bool(getattr(h, "is_download", False)),
            last_download_at=getattr(h, "last_download_at", None),
            previous_download_at=getattr(h, "previous_download_at", None),
            download_change_count=getattr(h, "download_change_count", None),
        )

    def _episode_to_dto(self, e, *, provider_code: str | None, stream_base: str | None) -> EpisodeDTO:
        sd = norm_str(getattr(e, "hls_sd", None))
        hd = norm_str(getattr(e, "hls_hd", None))
        fhd = norm_str(getattr(e, "hls_fhd", None))
        preview_path = norm_str(getattr(e, "preview_path", None))

        return EpisodeDTO(
            episode_id=int(getattr(e, "episode_id")),
            episode_number=int(getattr(e, "episode_number")),
            name=norm_str(getattr(e, "name", None)),
            hls_sd=sd,
            hls_hd=hd,
            hls_fhd=fhd,
            hls_sd_abs=abs_url(stream_base, sd),
            hls_hd_abs=abs_url(stream_base, hd),
            hls_fhd_abs=abs_url(stream_base, fhd),
            preview_path=preview_path,
            preview_abs=abs_asset_url(provider_code, self.cfg, preview_path, fallback_base=stream_base),
            skips_opening=norm_str(getattr(e, "skips_opening", None)),
            skips_ending=norm_str(getattr(e, "skips_ending", None)),
        )

    def _titles_return_card(self, titles) -> list[TitleCardDTO]:
        """Title → TitleCardDTO (lightweight, для list/search view)."""
        out: list[TitleCardDTO] = []
        for t in (titles or []):
            host = norm_str(getattr(t, "host_for_player", None))
            stream_base = make_base_url(host)
            provider_raw = getattr(t, "_pref_provider", None)
            provider_code = normalize_provider_code(provider_raw)

            genre_rels = getattr(t, "genres", []) or []
            genres = [self._genre_rel_to_dto(rel) for rel in genre_rels]

            provider_links = [
                ProviderLinkDTO(
                    id=int(d["id"]),
                    provider_id=int(d["provider_id"]),
                    provider_code=d.get("provider_code"),
                    provider_name=d.get("provider_name"),
                    external_title_id=str(d.get("external_title_id")),
                )
                for d in (getattr(t, "_pref_provider_links", []) or [])
            ]

            pref_rt = getattr(t, "_pref_ratings", []) or []
            ratings = [self._rating_to_dto(r) for r in pref_rt]

            pref_ps = getattr(t, "_pref_production_studio_obj", None)
            production_studio: ProductionStudioDTO | None = (
                ProductionStudioDTO(id=int(pref_ps["id"]), name=str(pref_ps["name"]))
                if pref_ps else None
            )

            out.append(TitleCardDTO(
                title_id=int(getattr(t, "title_id")),
                code=getattr(t, "code", None),
                name_ru=getattr(t, "name_ru", None),
                name_en=getattr(t, "name_en", None),
                alternative_name=getattr(t, "alternative_name", None),

                status_string=getattr(t, "status_string", None),
                status_code=getattr(t, "status_code", None),

                type_string=getattr(t, "type_string", None),
                type_code=getattr(t, "type_code", None),
                type_episodes=getattr(t, "type_episodes", None),
                type_length=getattr(t, "type_length", None),

                season_year=getattr(t, "season_year", None),
                season_string=getattr(t, "season_string", None),
                season_code=getattr(t, "season_code", None),

                day_of_week=getattr(t, "day_of_week", None),
                day_name=getattr(t, "day_name", None),

                host_for_player=host,

                poster_path_small=abs_asset_url(
                    provider_code, self.cfg, norm_str(getattr(t, "poster_path_small", None)), fallback_base=stream_base
                ),
                poster_path_medium=abs_asset_url(
                    provider_code, self.cfg, norm_str(getattr(t, "poster_path_medium", None)), fallback_base=stream_base
                ),
                poster_path_original=abs_asset_url(
                    provider_code, self.cfg, norm_str(getattr(t, "poster_path_original", None)), fallback_base=stream_base
                ),

                genres=genres,
                provider_links=provider_links,
                production_studio=production_studio,
                ratings=ratings,
                episodes_count=len(getattr(t, "episodes", []) or []) or None,

                provider=getattr(t, "_pref_provider", None),
                studio=getattr(t, "_pref_studio", None),
                team=getattr(t, "_pref_team", None),
                rating_name=getattr(t, "_pref_rating_name", None),
                rating_value=getattr(t, "_pref_rating_value", None),

                need_to_see=bool(getattr(t, "_pref_need_to_see", False)),
                title_watched=bool(getattr(t, "_pref_title_watched", False)),
                all_episodes_watched=bool(getattr(t, "_pref_all_episodes_watched", False)),

                enriched=bool(getattr(t, "_pref_enriched", False)),
                missing=list(getattr(t, "_pref_missing", []) or []),
            ))
        return out

    def _titles_return(self, titles) -> list[TitleDetailsDTO]:
        """
        Title -> TitleDetailsDTO.

        Правила:
        - Не читаем ленивые relationship'ы, которые НЕ joinedload'ятся get_titles_from_db(),
          потому что Title detached (session уже закрыта).
        - Всё, что даёт title_enricher.py, берём из _pref_*.
        - То, чего сейчас нет в безопасном виде — возвращаем пустые значения.
        """
        out: list[TitleDetailsDTO] = []

        for t in (titles or []):
            # stream host (hls) from DB field host_for_player
            host = norm_str(getattr(t, "host_for_player", None))
            stream_base = make_base_url(host)

            # provider code for assets host (config)
            provider_raw = getattr(t, "_pref_provider", None)
            provider_code = normalize_provider_code(provider_raw)

            # episodes (у тебя joinedload(Title.episodes))
            eps = getattr(t, "episodes", []) or []
            episodes = [self._episode_to_dto(e, provider_code=provider_code, stream_base=stream_base) for e in eps]

            # genres (joinedload(Title.genres).joinedload(genre))
            genre_rels = getattr(t, "genres", []) or []
            genres = [self._genre_rel_to_dto(rel) for rel in genre_rels]

            # schedules (joinedload(Title.schedules).joinedload(day))
            schedules_src = getattr(t, "schedules", []) or []
            schedules = [self._schedule_to_dto(sc) for sc in schedules_src]

            # -----------------------
            # enrichment (safe)
            # -----------------------
            provider = getattr(t, "_pref_provider", None)
            studio = getattr(t, "_pref_studio", None)
            team = getattr(t, "_pref_team", None)
            rating_name = getattr(t, "_pref_rating_name", None)
            rating_value = getattr(t, "_pref_rating_value", None)

            need_to_see = bool(getattr(t, "_pref_need_to_see", False))
            title_watched = bool(getattr(t, "_pref_title_watched", False))
            all_episodes_watched = bool(getattr(t, "_pref_all_episodes_watched", False))

            watched_episode_ids = sorted(
                [int(x) for x in (getattr(t, "_pref_watched_episodes", set()) or set())]
            )
            downloaded_torrent_ids = sorted(
                [int(x) for x in (getattr(t, "_pref_downloaded_torrents", set()) or set())]
            )

            enriched = bool(getattr(t, "_pref_enriched", False))
            missing = list(getattr(t, "_pref_missing", []) or [])

            # списки из enricher (они безопасны: enricher делает отдельные запросы и кладёт результат в атрибут)
            pref_fr = getattr(t, "_pref_franchises", []) or []
            pref_tor = getattr(t, "_pref_torrents", []) or []
            franchises = [self._franchise_to_dto(fr) for fr in pref_fr]
            torrents = [self._torrent_to_dto(tr, provider_code=provider_code, stream_base=stream_base) for tr in pref_tor]

            # team_members (via enricher)
            pref_tm = getattr(t, "_pref_team_members", []) or []
            team_members = [
                TeamMemberDTO(id=int(m["id"]), name=str(m["name"]), role=str(m["role"]))
                for m in pref_tm
            ]

            provider_links = []
            for d in (getattr(t, "_pref_provider_links", []) or []):
                provider_links.append(
                    ProviderLinkDTO(
                        id=int(d["id"]),
                        provider_id=int(d["provider_id"]),
                        provider_code=d.get("provider_code"),
                        provider_name=d.get("provider_name"),
                        external_title_id=str(d.get("external_title_id")),
                    )
                )

            # ratings (via enricher)
            pref_rt = getattr(t, "_pref_ratings", []) or []
            ratings = [self._rating_to_dto(r) for r in pref_rt]

            # history records (via enricher)
            pref_hr = getattr(t, "_pref_history_records", []) or []
            history = [self._history_to_dto(h) for h in pref_hr]

            # production_studio (via enricher)
            pref_ps = getattr(t, "_pref_production_studio_obj", None)
            production_studio: ProductionStudioDTO | None = (
                ProductionStudioDTO(id=int(pref_ps["id"]), name=str(pref_ps["name"]))
                if pref_ps else None
            )

            out.append(
                TitleDetailsDTO(
                    title_id=int(getattr(t, "title_id")),
                    code=getattr(t, "code", None),
                    name_ru=getattr(t, "name_ru", None),
                    name_en=getattr(t, "name_en", None),
                    alternative_name=getattr(t, "alternative_name", None),

                    status_string=getattr(t, "status_string", None),
                    status_code=getattr(t, "status_code", None),

                    type_full_string=getattr(t, "type_full_string", None),
                    type_string=getattr(t, "type_string", None),
                    type_code=getattr(t, "type_code", None),
                    type_episodes=getattr(t, "type_episodes", None),
                    type_length=getattr(t, "type_length", None),

                    season_year=getattr(t, "season_year", None),
                    season_string=getattr(t, "season_string", None),
                    season_code=getattr(t, "season_code", None),

                    description=getattr(t, "description", None),

                    day_of_week=getattr(t, "day_of_week", None),
                    day_name=getattr(t, "day_name", None),

                    host_for_player=host,

                    poster_path_small=abs_asset_url(
                        provider_code, self.cfg, norm_str(getattr(t, "poster_path_small", None)), fallback_base=stream_base
                    ),
                    poster_path_medium=abs_asset_url(
                        provider_code, self.cfg, norm_str(getattr(t, "poster_path_medium", None)), fallback_base=stream_base
                    ),
                    poster_path_original=abs_asset_url(
                        provider_code, self.cfg, norm_str(getattr(t, "poster_path_original", None)), fallback_base=stream_base
                    ),

                    genres=genres,
                    episodes=episodes,
                    schedules=schedules,

                    franchises=franchises,
                    team_members=team_members,
                    torrents=torrents,
                    provider_links=provider_links,
                    production_studio=production_studio,
                    ratings=ratings,
                    history=history,

                    provider=provider,
                    studio=studio,
                    team=team,
                    rating_name=rating_name,
                    rating_value=rating_value,

                    need_to_see=need_to_see,
                    title_watched=title_watched,
                    all_episodes_watched=all_episodes_watched,
                    watched_episode_ids=watched_episode_ids,
                    downloaded_torrent_ids=downloaded_torrent_ids,

                    enriched=enriched,
                    missing=missing,
                )
            )

        return out

