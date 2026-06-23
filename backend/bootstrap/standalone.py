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


def _validate_runtime(db_path: str, logger: logging.Logger) -> None:
    """
    Fail-fast checks before the backend is fully initialized.

    Raises RuntimeError for hard failures (missing DB directory).
    Logs warnings for soft issues (missing config, missing runtime package dirs).
    """
    cwd = Path.cwd()

    # ── Hard check: DB parent directory must exist ───────────────────────────
    db_parent = Path(db_path).parent
    if not db_parent.exists():
        raise RuntimeError(
            f"DB directory does not exist: {db_parent}  "
            f"(working directory: {cwd})"
        )

    # ── Soft checks: runtime package directories ─────────────────────────────
    # When running as a frozen binary or from the wrong CWD the packages are
    # still importable (bundled by PyInstaller), but when running from source
    # the CWD must be the project root.  We detect both cases and warn once.
    for pkg in ("storage", "utils", "providers"):
        try:
            __import__(pkg)
        except ImportError:
            logger.warning(
                "Runtime package '%s' is not importable from CWD=%s. "
                "Make sure WorkingDirectory points to the project root "
                "(not the backend/ subdirectory).",
                pkg, cwd,
            )


def build_backend(
        *,
        db_path: str,
        playlists_dir: str | Path = "playlists",
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

    # Fail-fast: check runtime prerequisites before touching the DB
    _validate_runtime(db_path, logger)

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
