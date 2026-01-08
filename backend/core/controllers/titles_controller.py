from __future__ import annotations

from backend.core.dto.titles import TitleDetailsDTO, EpisodeDTO, GenreDTO
from backend.core.dto.search import TitlesSearchResult
from backend.core.utils.urls import make_base_url, abs_url, norm_str


class TitlesController:
    def __init__(self, db):
        self._db = db

    # -----------------------
    # titles.search (DB-only)
    # -----------------------
    def titles_search(self, query: str, provider: str | None = None) -> TitlesSearchResult:
        query = (query or "").strip()
        if not query:
            return TitlesSearchResult(title_ids=[], providers=[])

        title_ids, providers = self._db.get_titles_by_keywords(query)
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

    # -----------------------
    # titles.get (DB-only)
    # -----------------------
    def titles_get(self, title_ids: list[int]) -> list[TitleDetailsDTO]:
        title_ids = [int(x) for x in (title_ids or [])]
        if not title_ids:
            return []

        titles = self._db.get_titles_from_db(title_ids=title_ids)  # или как у тебя реально называется
        if not titles:
            return []

        out = self._titles_return(titles)

        # фикс порядка входных id
        index = {tid: i for i, tid in enumerate(title_ids)}
        out.sort(key=lambda dto: index.get(int(dto.title_id), 10**9))  # <-- фикс твоего бага
        return out

    def title_get(self, title_id: int) -> TitleDetailsDTO:
        title = self._db.get_titles_from_db(title_id=title_id)
        if not title:
            raise ValueError(f"title_id not found: {title_id}")

        out = self._titles_return(title)

        return out[0]

    # -----------------------
    # episodes.list (DB-only)
    # -----------------------
    def titles_list_episodes(self, title_ids: list[int]) -> dict[int, list[EpisodeDTO]]:
        title_ids = [int(x) for x in (title_ids or [])]
        titles = self._db.get_titles_from_db(title_ids=title_ids)
        if not titles:
            return {}

        episodes_by_title: dict[int, list[EpisodeDTO]] = {}
        for t in titles:
            tid = int(getattr(t, "title_id"))
            eps = getattr(t, "episodes", []) or []
            items: list[EpisodeDTO] = []
            host = norm_str(getattr(t, "host_for_player", None))
            base = make_base_url(host)
            for e in eps:
                items.append(self._episode_to_dto(e, base))
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
    def _episode_to_dto(self, e, base: str | None) -> EpisodeDTO:
        sd = norm_str(getattr(e, "hls_sd", None))
        hd = norm_str(getattr(e, "hls_hd", None))
        fhd = norm_str(getattr(e, "hls_fhd", None))

        return EpisodeDTO(
            episode_id=int(getattr(e, "episode_id")),
            episode_number=int(getattr(e, "episode_number")),
            name=norm_str(getattr(e, "name", None)),
            hls_sd=sd,
            hls_hd=hd,
            hls_fhd=fhd,
            hls_sd_abs=abs_url(base, sd),
            hls_hd_abs=abs_url(base, hd),
            hls_fhd_abs=abs_url(base, fhd),
            preview_path=norm_str(getattr(e, "preview_path", None)),
            skips_opening=norm_str(getattr(e, "skips_opening", None)),
            skips_ending=norm_str(getattr(e, "skips_ending", None)),
        )

    def _titles_return(self, titles) -> list[TitleDetailsDTO]:
        """
        Тут вставь твою текущую логику маппинга Title -> TitleDetailsDTO,
        которая у тебя уже есть в titles_controller.py
        """
        out: list[TitleDetailsDTO] = []

        for t in titles:
            # host/base если нужно:
            host = norm_str(getattr(t, "host_for_player", None))
            base = make_base_url(host)

            # episodes
            eps = getattr(t, "episodes", []) or []
            episodes: list[EpisodeDTO] = []
            for e in eps:
                episodes.append(self._episode_to_dto(e, base))

            # genres
            genre_names = getattr(t, "genre_names", []) or []
            genre_ids = getattr(t, "genre_ids", []) or []
            genres: list[GenreDTO] = []
            if isinstance(genre_names, (list, tuple)) and isinstance(genre_ids, (list, tuple)) and len(genre_names) == len(genre_ids):
                genres = [GenreDTO(genre_id=int(gid), name=str(gname)) for gname, gid in zip(genre_names, genre_ids)]

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
                    genres=genres,
                    host_for_player=host,
                    episodes=episodes,
                )
            )

        return out
