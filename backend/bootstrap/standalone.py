from __future__ import annotations

import logging
from pathlib import Path

from storage.database_manager import DatabaseManager
from backend.core.standalone_backend import StandaloneBackend
from backend.infra.db.progress_repo import SqlAlchemyProgressRepo


def build_backend(*, db_path: str, playlists_dir: str | Path = "playlists", logger: logging.Logger | None = None) -> StandaloneBackend:
    logger = logger or logging.getLogger("standalone-backend")

    db = DatabaseManager(db_path)
    try:
        db.initialize_tables()
    except Exception:
        logger.exception("DB initialize_tables() failed (continuing)")

    progress_repo = SqlAlchemyProgressRepo(db.Session)

    return StandaloneBackend(db=db, playlists_dir=playlists_dir, progress_repo=progress_repo)
