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
except Exception:  # pragma: no cover
    AniLibertyProvider = None  # type: ignore
    AniLibertyPayloadSource = None  # type: ignore


def build_backend(
        *,
        db_path: str,
        playlists_dir: str | Path = "...ts",
        logger: logging.Logger | None = None,
        providers: dict[str, Any] | None = None,
        aniliberty_api_adapter: Any | None = None,
) -> StandaloneBackend:
    """Создать standalone backend (без UI).

    providers: mapping provider_code -> IProviderPayloadSource
    aniliberty_api_adapter: если передан, зарегистрируем 'aniliberty' автоматически
    """
    logger = logger or logging.getLogger("standalone-backend")

    db = DatabaseManager(db_path)
    try:
        db.initialize_tables()
    except Exception:
        logger.exception("DB initialize_tables() failed (continuing)")

    progress_repo = SqlAlchemyProgressRepo(db.Session)

    providers_map: dict[str, Any] = dict(providers or {})

    if aniliberty_api_adapter is not None and AniLibertyProviderAdapter and AniLibertyPayloadSource:
        try:
            providers_map.setdefault("aniliberty", AniLibertyPayloadSource(AniLibertyProviderAdapter(aniliberty_api_adapter)))
        except Exception:
            logger.exception("Failed to init AniLiberty provider (continuing)")

    return StandaloneBackend(db=db, playlists_dir=playlists_dir, progress_repo=progress_repo, providers=providers_map)

