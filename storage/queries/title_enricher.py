# core/queries/title_enricher.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from backend.core.dto.titles import TitleViewMode

@dataclass(slots=True)
class TitleEnrichment:
    provider: str | None = None
    studio: str | None = None
    team: str | None = None
    rating_name: str | None = None
    rating_value: int | None = None
    franchises: list[Any] | None = None
    torrents: list[Any] | None = None

def enrich_titles_for_render(
    db_manager,
    user_id: int,
    titles: list[Any],
    *,
    view_mode: "TitleViewMode | None" = None,
) -> Any:
    """
    Mutates ORM Title objects: adds prefetched attrs used by UI renderer.
    No Qt imports. UI layer decides when to call it.

    view_mode=TitleViewMode.CARD — skips per-episode history loop, team_members,
                                   history_records, torrents & franchise fetch.
                                   Saves N×(episodes+torrents) queries per title.
    view_mode=TitleViewMode.FULL (default) — all fields populated.
    """
    # Late import to avoid circular dependency (storage has no hard dep on backend.core)
    from backend.core.dto.titles import TitleViewMode
    if view_mode is None:
        view_mode = TitleViewMode.FULL
    if not titles:
        return titles

    for t in titles:
        provider = None
        studio = None
        team = None
        rating_name = None
        rating_value = None
        need_to_see = False
        title_watched = False
        watched_episodes: set[int] = set()
        all_episodes_watched = False
        downloaded_torrents: set[int] = set()

        try:
            provider = db_manager.get_provider_by_title_id(t.title_id)
        except Exception:
            provider = None

        try:
            studio = db_manager.get_studio_by_title_id(t.title_id)
        except Exception:
            studio = None

        try:
            team = db_manager.get_team_from_db(t.title_id)
        except Exception:
            team = None

        try:
            r = db_manager.get_rating_from_db(t.title_id)
            if r:
                rating_name = getattr(r, "rating_name", None)
                rating_value = getattr(r, "rating_value", None)
        except Exception:
            pass

        try:
            ratings_list = db_manager.get_ratings_list_from_db(t.title_id) or []
        except Exception:
            ratings_list = []

        try:
            production_studio_obj = db_manager.get_production_studio_obj_from_db(t.title_id)
        except Exception:
            production_studio_obj = None

        try:
            need_to_see = bool(db_manager.get_need_to_see(user_id, t.title_id))
        except Exception:
            need_to_see = False

        try:
            is_watched, _ = db_manager.get_history_status(user_id, t.title_id, episode_id=None)
            title_watched = bool(is_watched)
        except Exception:
            title_watched = False

        try:
            all_episodes_watched = bool(db_manager.get_all_episodes_watched_status(user_id, t.title_id))
        except Exception:
            all_episodes_watched = False

        # --- detail-only fields (skipped in CARD mode) ---
        if view_mode == TitleViewMode.CARD:
            franchises = []
            torrents = []
            team_members = []
            history_records = []
        else:
            try:
                franchises = db_manager.get_franchises_from_db(title_id=t.title_id) or []
            except Exception:
                franchises = []

            try:
                torrents = db_manager.get_torrents_from_db(t.title_id) or []
            except Exception:
                torrents = []

            try:
                team_members = db_manager.get_team_members_from_db(t.title_id) or []
            except Exception:
                team_members = []

            try:
                history_records = db_manager.get_history_records_from_db(user_id, t.title_id) or []
            except Exception:
                history_records = []

            # per-episode watched status (N+1 — only in detail mode)
            try:
                for e in t.episodes or []:
                    is_ep_watched, _ = db_manager.get_history_status(
                        user_id, t.title_id, episode_id=e.episode_id
                    )
                    if is_ep_watched:
                        watched_episodes.add(int(e.episode_id))
            except Exception:
                watched_episodes = set()

            # per-torrent downloaded status (only in detail mode)
            try:
                for tor in torrents:
                    tid = getattr(tor, "torrent_id", None)
                    if not tid:
                        continue
                    _, is_download = db_manager.get_history_status(user_id, t.title_id, torrent_id=tid)
                    if is_download:
                        downloaded_torrents.add(int(tid))
            except Exception:
                downloaded_torrents = set()

        setattr(t, "_pref_provider", provider)
        setattr(t, "_pref_studio", studio)
        setattr(t, "_pref_team", team)
        setattr(t, "_pref_rating_name", rating_name)
        setattr(t, "_pref_rating_value", rating_value)
        setattr(t, "_pref_franchises", franchises)
        setattr(t, "_pref_torrents", torrents)
        setattr(t, "_pref_team_members", team_members)
        setattr(t, "_pref_ratings", ratings_list)
        setattr(t, "_pref_history_records", history_records)
        setattr(t, "_pref_production_studio_obj", production_studio_obj)
        setattr(t, "_pref_need_to_see", need_to_see)
        setattr(t, "_pref_title_watched", title_watched)
        setattr(t, "_pref_watched_episodes", watched_episodes)
        setattr(t, "_pref_all_episodes_watched", all_episodes_watched)
        setattr(t, "_pref_downloaded_torrents", downloaded_torrents)

        setattr(t, "_pref_enriched", True)

        missing = []
        if provider is None: missing.append("provider")
        if studio is None: missing.append("studio")
        if team is None: missing.append("team")
        if rating_name is None and rating_value is None: missing.append("rating")

        setattr(t, "_pref_missing", missing)
        if missing:
            db_manager.logger.debug("ENRICH missing title_id=%s: %s", t.title_id, ",".join(missing))

    return titles