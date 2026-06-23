from __future__ import annotations

"""
PosterJobAdapter — non-blocking background poster ingestion.

After a provider payload is written to the DB (apply_provider_payload returns
a title_id), this adapter queues the poster URLs found in the payload for
background download.  Uses utils.downloads.PosterManager which handles
HTTP fetching + format validation + save_callback in a daemon thread.

Design goals:
  - Never block / never raise in the sync path.  All errors are logged only.
  - Idempotent: PosterManager skips (title_id, size_key) pairs already queued.
  - Supports AniLiberty payload shape  (posters.{size}.url)
  - Supports AniMedia payload shape    (poster_path_medium / poster_path_small)
"""

import logging
from typing import Any

log = logging.getLogger("backend.poster")

# Size keys we care about, in priority order
_SIZES = ("medium", "small", "original")


def _extract_poster_links(
    title_id: int,
    payload: dict[str, Any],
) -> list[tuple[int, str, str]]:
    """Return [(title_id, url, size_key), ...] from a provider payload dict.

    Key design decision: always try to produce a *medium* entry.
    The /poster/{id} endpoint in server.py looks for 'medium' first, then
    'small'.  PosterManager.save_poster("original") auto-creates 'small', but
    saves nothing under 'medium'.  So we download the best available URL and
    store it as 'medium', ensuring the blob endpoint always finds it.

    AniMedia only sends posters.original.url — we map that as 'medium' here.
    AniLiberty sends all three sizes — we use each under its natural key.
    """
    links: list[tuple[int, str, str]] = []
    url_by_size: dict[str, str] = {}

    # ── Collect all available URLs from the nested posters dict ─────────────
    posters = payload.get("posters") or {}
    for size_key in _SIZES:
        entry = posters.get(size_key)
        url: str | None = None
        if isinstance(entry, dict):
            url = entry.get("url") or None
        elif isinstance(entry, str) and entry.startswith("http"):
            url = entry
        if isinstance(url, str) and url.startswith("http"):
            url_by_size[size_key] = url

    # ── Collect from flat poster_path_* fields (AniMedia legacy) ────────────
    _flat_map = [
        ("medium",   "poster_path_medium"),
        ("small",    "poster_path_small"),
        ("original", "poster_path_original"),
    ]
    for size_key, field in _flat_map:
        if size_key not in url_by_size:
            url = payload.get(field)
            if isinstance(url, str) and url.startswith("http"):
                url_by_size[size_key] = url

    if not url_by_size:
        return []

    # ── Resolve best URL for 'medium' (priority: medium > original > small) ──
    medium_url = (
        url_by_size.get("medium")
        or url_by_size.get("original")
        or url_by_size.get("small")
    )
    if medium_url:
        links.append((title_id, medium_url, "medium"))

    # ── Also queue 'small' if it has a distinct URL ───────────────────────────
    small_url = url_by_size.get("small")
    if small_url and small_url != medium_url:
        links.append((title_id, small_url, "small"))

    return links


class PosterJobAdapter:
    """
    Wraps utils.downloads.PosterManager to provide idempotent, non-blocking
    poster ingestion after provider payloads are saved.
    """

    def __init__(self, db: Any, net_client: Any) -> None:
        from utils.downloads.poster_manager import PosterManager

        self._pm = PosterManager(
            save_callback=db.save_poster,
            net_client=net_client,
        )

    def queue_posters_for_payload(
        self,
        title_id: int,
        payload: dict[str, Any],
    ) -> None:
        """
        Extract poster URLs from *payload* and queue them for background download.
        Safe to call from any thread; never raises.
        """
        if not isinstance(payload, dict):
            return
        try:
            links = _extract_poster_links(title_id, payload)
            if links:
                log.debug(
                    "Queueing %d poster link(s) for title_id=%s", len(links), title_id
                )
                self._pm.write_poster_links(links)
        except Exception as exc:
            log.warning(
                "Poster queue failed for title_id=%s: %s", title_id, exc
            )

    def stop(self) -> None:
        """Stop background threads gracefully (call on shutdown)."""
        try:
            self._pm.stop()
        except Exception:
            pass
