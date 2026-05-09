"""
Thin HTTP wrapper around the JSON-tool handlers.
Used by Android TV / Desktop app to talk to the backend over the local network.

Usage:
    python -m backend.transport.http.server --db db/anime_player.db --port 8765

Endpoint:
    POST /api
    Body:  {"op": "titles.search", "params": {"query": "naruto"}}
    Reply: {"ok": true, "result": {...}, "error": null}
"""
# NOTE: do NOT add `from __future__ import annotations` here.
# FastAPI resolves parameter types via typing.get_type_hints() against module globals.
# If annotations are lazy strings (PEP 563), ApiRequest can't be resolved and FastAPI
# silently falls back to treating `req` as a query parameter → 422 on every request.

import argparse
import logging
from typing import Any

from backend.transport.json_tool.handlers import HANDLERS
from backend.transport.json_tool.protocol import fail as err


log = logging.getLogger("anime.http")


# ---------------------------------------------------------------------------
# Request model — defined at module level so FastAPI's type-hint resolution works.
# ---------------------------------------------------------------------------
try:
    from pydantic import BaseModel as _BaseModel

    class ApiRequest(_BaseModel):
        op: str
        params: dict[str, Any] = {}

except ImportError:  # pragma: no cover — fastapi/pydantic not installed
    ApiRequest = None  # type: ignore[assignment,misc]


# ---------------------------------------------------------------------------
# UI normalisation — transforms raw Python DTOs (via to_jsonable) into the
# clean, flat JSON the Kotlin client expects.  Only applied by the HTTP server;
# the JSON-tool / CLI protocol is unchanged.
# ---------------------------------------------------------------------------

def _genres(raw: list) -> list[str]:
    """list[GenreDTO-dict] → list[str] (names only)."""
    return [g["name"] for g in (raw or []) if g.get("name")]


def _ratings(raw: list) -> list[dict]:
    """Keep only the rating fields the UI can render."""
    return [
        {
            "rating_name": r.get("rating_name"),
            "rating_value": r.get("rating_value"),
            "name_external": r.get("name_external"),
            "score_external": r.get("score_external"),
        }
        for r in (raw or [])
        if r.get("rating_value") is not None or r.get("score_external") is not None
    ]


def _franchises(raw: list) -> list[dict]:
    """Flatten FranchiseDTO-dicts for the Kotlin UI."""
    return [
        {
            "franchise_id": fr.get("franchise_id"),
            "franchise_name": fr.get("franchise_name"),
            "code": fr.get("code"),
            "ordinal": fr.get("ordinal"),
            "name_ru": fr.get("name_ru"),
            "name_en": fr.get("name_en"),
            "name_alternative": fr.get("name_alternative"),
            "related_title_id": fr.get("related_title_id"),
            "related_title_name_ru": fr.get("related_title_name_ru"),
            "related_title_name_en": fr.get("related_title_name_en"),
        }
        for fr in (raw or [])
    ]

def _team_members(raw: list) -> list[dict]:
    return [
        {
            "id": m.get("id"),
            "name": m.get("name"),
            "role": m.get("role") or "",
        }
        for m in (raw or [])
        if m.get("name")
    ]


def _torrents(raw: list) -> list[dict]:
    return [
        {
            "torrent_id": tr.get("torrent_id"),
            "episodes_range": tr.get("episodes_range"),
            "range_first": tr.get("range_first"),
            "range_last": tr.get("range_last"),
            "quality": tr.get("quality"),
            "quality_type": tr.get("quality_type"),
            "resolution": tr.get("resolution"),
            "encoder": tr.get("encoder"),
            "leechers": tr.get("leechers"),
            "seeders": tr.get("seeders"),
            "downloads": tr.get("downloads"),
            "total_size": tr.get("total_size"),
            "size_string": tr.get("size_string"),
            "url": tr.get("url"),
            "magnet_link": tr.get("magnet_link"),
            "label": tr.get("label"),
            "filename": tr.get("filename"),
            "hash": tr.get("hash"),
        }
        for tr in (raw or [])
        if tr.get("torrent_id") is not None
    ]


def _poster_cdn(d: dict) -> str | None:
    """Return a CDN poster URL from the title dict, checking all stored sizes.

    AniMedia (and similar providers) only populates poster_path_original;
    medium/small are stored as empty strings.  Check all three so any provider
    that supplies at least one size gets a working poster URL.
    """
    return (
        d.get("poster_path_medium")
        or d.get("poster_path_small")
        or d.get("poster_path_original")
    )


def _poster_url(d: dict) -> str | None:
    """
    Return a poster URL for the title.
    - If titles table has a CDN URL → return it directly.
    - Otherwise → return a relative path to the /poster/<id> endpoint
      (the Kotlin client prepends backendUrl for relative paths).
    """
    cdn = _poster_cdn(d)
    if cdn:
        return cdn
    title_id = d.get("title_id")
    if title_id is not None:
        return f"/poster/{title_id}"
    return None


def _optional_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _make_abs_stream(url: str | None, host_for_player: str | None) -> str | None:
    """
    #1 fix: AniMedia stores host_for_player in the titles table but hls_*_abs
    can still be None if the enricher ran without a stream_base.  Fall back to
    assembling the URL from host_for_player + relative path ourselves.
    """
    if not url:
        return None
    if url.startswith("http://") or url.startswith("https://"):
        return url
    if host_for_player and url.startswith("/"):
        h = host_for_player.strip()
        if not h.startswith("http"):
            h = f"https://{h}"
        return h.rstrip("/") + url
    return url   # return as-is (relative); client may handle it


def _normalize_episode(ep: dict, title_id: int, watched_ids: set,
                        host_for_player: str | None = None) -> dict:
    def _s(key_abs: str, key_rel: str) -> str | None:
        return _make_abs_stream(ep.get(key_abs) or ep.get(key_rel), host_for_player)

    return {
        "episode_id":     ep.get("episode_id"),
        "episode_number": ep.get("episode_number"),
        "title":          ep.get("name"),          # Python uses "name", Kotlin "title"
        "title_id":       title_id,                # not in EpisodeDTO — injected from parent
        "hls_sd":         _s("hls_sd_abs",  "hls_sd"),
        "hls_hd":         _s("hls_hd_abs",  "hls_hd"),
        "hls_fhd":        _s("hls_fhd_abs", "hls_fhd"),
        "preview_abs":    ep.get("preview_abs"),
        "is_watched":     ep.get("episode_id") in watched_ids,
        "skips_opening":  ep.get("skips_opening"),
        "skips_ending":   ep.get("skips_ending"),
    }


def _normalize_title_card(d: dict) -> dict:
    return {
        "title_id":   d.get("title_id"),
        "name_ru":    d.get("name_ru"),
        "name_en":    d.get("name_en"),
        "poster_url": _poster_url(d),
        "year":       d.get("season_year"),
        "type":       d.get("type_string"),
        "status":     d.get("status_string"),
        "day_of_week": d.get("day_of_week"),
        "day_name":   d.get("day_name"),
        "episodes_count": _optional_int(d.get("episodes_count")) or _optional_int(d.get("type_episodes")),
        "provider":   d.get("provider"),
        "genres":     _genres(d.get("genres", [])),
        "rating_name": d.get("rating_name"),
        "rating_value": d.get("rating_value"),
        "ratings":    _ratings(d.get("ratings", [])),
        "is_watched": d.get("title_watched"),
        "all_episodes_watched": d.get("all_episodes_watched"),
        "need_to_see": d.get("need_to_see"),
    }


def _normalize_title_details(d: dict) -> dict:
    title_id = d.get("title_id")
    host_for_player = d.get("host_for_player")   # #1 fix: pass to episode normalizer
    # Build watched-episode set from embedded history
    watched_ids = {
        h["episode_id"]
        for h in d.get("history", [])
        if h.get("is_watched") and h.get("episode_id") is not None
    }
    return {
        "title_id":    title_id,
        "name_ru":     d.get("name_ru"),
        "name_en":     d.get("name_en"),
        "description": d.get("description"),
        "poster_url":  _poster_url(d),
        "year":        d.get("season_year"),
        "type":        d.get("type_string"),
        "status":      d.get("status_string"),
        "genres":      _genres(d.get("genres", [])),
        "ratings":     _ratings(d.get("ratings", [])),
        "franchises":  _franchises(d.get("franchises", [])),
        "team_members": _team_members(d.get("team_members", [])),
        "torrents":    _torrents(d.get("torrents", [])),
        "episodes": [
            _normalize_episode(ep, title_id, watched_ids, host_for_player=host_for_player)
            for ep in d.get("episodes", [])
        ],
        "provider_links": [
            {
                "provider_code":    pl.get("provider_code") or "",
                "external_title_id": pl.get("external_title_id", ""),
                "provider_name":    pl.get("provider_name"),
            }
            for pl in d.get("provider_links", [])
        ],
        "is_watched":  d.get("title_watched"),
        "all_episodes_watched": d.get("all_episodes_watched"),
        "watched_episode_count": len(watched_ids),
        "need_to_see": d.get("need_to_see"),
        "history_records": [
            {
                "episode_id": h.get("episode_id"),
                "is_watched": h.get("is_watched", False),
                "watched_at": h.get("last_watched_at"),
            }
            for h in d.get("history", [])
        ],
    }


def _normalize_for_ui(op: str, response: dict) -> dict:
    """
    Post-process the handler's response dict for UI clients.
    Only transforms ops whose output structure the Kotlin client depends on.
    All other ops are passed through unchanged.
    """
    if not response.get("ok") or not response.get("result"):
        return response

    result = response["result"]

    if op == "titles.search":
        return {**response, "result": {
            **result,
            "titles": [_normalize_title_card(t) for t in result.get("titles", [])],
        }}

    if op == "titles.get":
        view = result.get("view", "full")
        if view == "card":
            titles = [_normalize_title_card(t) for t in result.get("titles", [])]
        else:
            titles = [_normalize_title_details(t) for t in result.get("titles", [])]
        return {**response, "result": {**result, "titles": titles}}

    return response


# ---------------------------------------------------------------------------
# FastAPI app factory
# ---------------------------------------------------------------------------

def build_app(backend):
    from fastapi import FastAPI, HTTPException
    from fastapi.middleware.cors import CORSMiddleware

    app = FastAPI(title="Anime Player Backend", version="1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["POST", "GET"],
        allow_headers=["*"],
    )

    @app.get("/health")
    def health():
        return {"ok": True, "version": "1.0"}

    @app.get("/status")
    def status():
        """Extended status — used by UI to show connection info."""
        return {
            "ok": True,
            "version": "1.0",
            "ops": len(HANDLERS),
            "ops_list": list(HANDLERS.keys()),
        }

    @app.get("/poster/{title_id}")
    def poster(title_id: int):
        """
        Serve poster blob stored in the `posters` table.

        Concurrency fix: uses a *request-local* SQLAlchemy session instead of
        the shared DatabaseManager.Session to avoid identity-map corruption
        when multiple requests are in-flight simultaneously.
        """
        from fastapi.responses import Response as FastResponse
        from sqlalchemy.orm import sessionmaker as _sm
        from storage.tables import Poster
        from storage.types import POSTER_FIELDS
        try:
            _SessionLocal = _sm(bind=backend._db.engine, autocommit=False, autoflush=False)
            with _SessionLocal() as session:
                p = session.query(Poster).filter_by(title_id=title_id).first()
                if p:
                    for size_key in ("medium", "small"):
                        raw = getattr(p, POSTER_FIELDS[size_key].blob, None)
                        if raw:
                            return FastResponse(content=bytes(raw), media_type="image/jpeg")
        except Exception as exc:
            log.debug("poster fetch failed for title_id=%s: %s", title_id, exc)
        raise HTTPException(status_code=404, detail="Poster not found")

    @app.post("/api")
    def api(req: ApiRequest):
        handler = HANDLERS.get(req.op)
        if handler is None:
            raise HTTPException(status_code=404, detail=f"Unknown op: {req.op!r}")
        try:
            result = handler(backend, req.params)
            return _normalize_for_ui(req.op, result)
        except (ValueError, KeyError, TypeError) as exc:
            return err(str(exc))
        except Exception as exc:
            log.exception("Unexpected error in op=%s", req.op)
            return err(f"Internal error: {exc}")

    return app


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Anime Player HTTP server")
    parser.add_argument("--db", required=True, help="Path to anime_player.db")
    parser.add_argument("--port", type=int, default=8765, help="HTTP port (default: 8765)")
    parser.add_argument("--host", default="0.0.0.0", help="Bind host (default: 0.0.0.0)")
    parser.add_argument("--playlists-dir", default="playlists")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    from backend.bootstrap.standalone import build_backend

    log.info("Starting HTTP server on %s:%d", args.host, args.port)
    log.info("DB: %s", args.db)

    backend = build_backend(
        db_path=args.db,
        playlists_dir=args.playlists_dir,
    )

    import uvicorn
    app = build_app(backend)
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
