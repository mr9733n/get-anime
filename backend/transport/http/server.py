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


def _poster(d: dict) -> str | None:
    return d.get("poster_path_medium") or d.get("poster_path_small")


def _normalize_episode(ep: dict, title_id: int, watched_ids: set) -> dict:
    return {
        "episode_id":     ep.get("episode_id"),
        "episode_number": ep.get("episode_number"),
        "title":          ep.get("name"),          # Python uses "name", Kotlin "title"
        "title_id":       title_id,                # not in EpisodeDTO — injected from parent
        "hls_sd":         ep.get("hls_sd_abs") or ep.get("hls_sd"),
        "hls_hd":         ep.get("hls_hd_abs") or ep.get("hls_hd"),
        "hls_fhd":        ep.get("hls_fhd_abs") or ep.get("hls_fhd"),
        "preview_abs":    ep.get("preview_abs"),
        "is_watched":     ep.get("episode_id") in watched_ids,
    }


def _normalize_title_card(d: dict) -> dict:
    return {
        "title_id":   d.get("title_id"),
        "name_ru":    d.get("name_ru"),
        "name_en":    d.get("name_en"),
        "poster_url": _poster(d),
        "year":       d.get("season_year"),
        "type":       d.get("type_string"),
        "status":     d.get("status_string"),
        "genres":     _genres(d.get("genres", [])),
        "is_watched": d.get("title_watched"),
        "need_to_see": d.get("need_to_see"),
    }


def _normalize_title_details(d: dict) -> dict:
    title_id = d.get("title_id")
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
        "poster_url":  _poster(d),
        "year":        d.get("season_year"),
        "type":        d.get("type_string"),
        "status":      d.get("status_string"),
        "genres":      _genres(d.get("genres", [])),
        "episodes": [
            _normalize_episode(ep, title_id, watched_ids)
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
