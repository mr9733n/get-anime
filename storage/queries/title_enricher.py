# core/queries/title_enricher.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Any

@dataclass(slots=True)
class TitleEnrichment:
    provider: str | None = None
    studio: str | None = None
    team: str | None = None
    rating_name: str | None = None
    rating_value: int | None = None
    franchises: list[Any] | None = None
    torrents: list[Any] | None = None

def enrich_titles_for_render(db_manager, user_id: int, titles: list[Any]) -> Any:
    """
    Mutates ORM Title objects: adds prefetched attrs used by UI renderer.
    No Qt imports. UI layer decides when to call it.
    """
    if not titles:
        return titles

    for t in titles:
        provider = None
        studio = None
        team = None
        rating_name = None
        rating_value = None
        franchises = []
        torrents = []
        need_to_see = False
        title_watched = False
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
            franchises = db_manager.get_franchises_from_db(title_id=t.title_id) or []
        except Exception:
            franchises = []

        try:
            torrents = db_manager.get_torrents_from_db(t.title_id) or []
        except Exception:
            torrents = []

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

        try:
            # torrents уже есть (список объектов, у них torrent_id)
            if torrents:
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
        setattr(t, "_pref_need_to_see", need_to_see)
        setattr(t, "_pref_title_watched", title_watched)
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