from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from storage.database_manager import DatabaseManager
from backend.core.standalone_backend import StandaloneBackend
from backend.infra.db.progress_repo import SqlAlchemyProgressRepo

# optional provider wiring (не тянет UI)
try:
    from backend.adapters.aniliberty_provider import AniLibertyProviderAdapter
    from backend.infra.providers.aniliberty_payload_source import AniLibertyPayloadSource
    from backend.infra.providers.aniliberty_schedule_source import AniLibertyScheduleSource
except Exception:  # pragma: no cover
    AniLibertyProviderAdapter = None  # type: ignore
    AniLibertyPayloadSource = None    # type: ignore
    AniLibertyScheduleSource = None   # type: ignore

try:
    from backend.adapters.animedia_provider import AniMediaProviderAdapter
    from backend.infra.providers.animedia_payload_source import AniMediaPayloadSource
    from backend.infra.providers.animedia_schedule_source import AniMediaScheduleSource
except Exception:  # pragma: no cover
    AniMediaProviderAdapter = None   # type: ignore
    AniMediaPayloadSource = None     # type: ignore
    AniMediaScheduleSource = None    # type: ignore


def build_backend(
        *,
        db_path: str,
        playlists_dir: str | Path = "...ts",
        logger: logging.Logger | None = None,
        providers: dict[str, Any] | None = None,
        schedule_sources: dict[str, Any] | None = None,
        aniliberty_api_adapter: Any | None = None,
        animedia_api_adapter: Any | None = None,
) -> StandaloneBackend:
    """Создать standalone backend (без UI).

    providers: mapping provider_code -> IProviderPayloadSource
    schedule_sources: mapping provider_code -> IProviderScheduleSource
    aniliberty_api_adapter: raw AniLiberty APIAdapter — auto-registers 'aniliberty'
    animedia_api_adapter: raw AniMedia AniMediaAdapter — auto-registers 'animedia'

    When providers/schedule_sources are None AND no api_adapters are given,
    StandaloneBackend falls back to ProvidersFactory (config-driven).
    """
    logger = logger or logging.getLogger("standalone-backend")

    db = DatabaseManager(db_path)
    try:
        db.initialize_tables()
    except Exception:
        logger.exception("DB initialize_tables() failed (continuing)")

    progress_repo = SqlAlchemyProgressRepo(db.Session)

    providers_map: dict[str, Any] = dict(providers or {})
    schedule_map: dict[str, Any] = dict(schedule_sources or {})

    # ── AniLiberty shortcut ──────────────────────────────────────────────────
    if aniliberty_api_adapter is not None and AniLibertyPayloadSource and AniLibertyScheduleSource:
        try:
            al_adapter = AniLibertyProviderAdapter(aniliberty_api_adapter)
            providers_map.setdefault("aniliberty", AniLibertyPayloadSource(api=al_adapter))
            schedule_map.setdefault("aniliberty", AniLibertyScheduleSource(api=al_adapter))
        except Exception:
            logger.exception("Failed to init AniLiberty provider (continuing)")

    # ── AniMedia shortcut ────────────────────────────────────────────────────
    if animedia_api_adapter is not None and AniMediaPayloadSource and AniMediaScheduleSource:
        try:
            am_adapter = AniMediaProviderAdapter(animedia_api_adapter)
            providers_map.setdefault("animedia", AniMediaPayloadSource(api=am_adapter))
            schedule_map.setdefault("animedia", AniMediaScheduleSource(api=am_adapter))
        except Exception:
            logger.exception("Failed to init AniMedia provider (continuing)")

    return StandaloneBackend(
        db=db,
        playlists_dir=playlists_dir,
        progress_repo=progress_repo,
        providers=providers_map or None,
        schedule_sources=schedule_map or None,
    )
