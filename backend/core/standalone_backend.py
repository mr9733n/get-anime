from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from backend.core.context import BackendContext
from backend.core.controllers.titles_controller import TitlesController
from backend.core.controllers.streams_controller import StreamsController
from backend.core.controllers.playlists_controller import PlaylistsController
from backend.core.controllers.process_controller import ProcessController
from backend.core.ports.playlists import IPlaylistStorage, IPlaylistComposer
from backend.core.ports.provider_payload_source import IProviderPayloadSource
from backend.core.use_cases.playlist_composer import PlaylistComposer
from backend.core.use_cases.apply_provider_payload import ApplyProviderPayloadUseCase
from backend.core.workers.provider_pipeline import ProviderPipeline
from backend.infra.providers.dict_provider_resolver import DictProviderResolver
from backend.infra.playlists.playlist_storage import PlaylistManagerStorage
from backend.infra.db.titles_port_sqlalchemy import SqlAlchemyTitlesPort
from backend.infra.db.titles_enricher_sqlalchemy import SqlAlchemyTitlesEnricherPort
from backend.infra.db.process_write_port_storage import StorageProcessWritePort
from backend.core.use_cases.sync_search_and_process import SyncSearchAndProcessUseCase
from backend.core.controllers.sync_controller import SyncController
from backend.core.controllers.titles_update_controller import TitlesUpdateController
from backend.core.controllers.history_controller import HistoryController
from backend.core.controllers.schedule_controller import ScheduleController
from backend.infra.db.history_write_sqlalchemy import SqlAlchemyHistoryWritePort
from backend.infra.db.schedule_sqlalchemy import (
    SqlAlchemyScheduleReadPort,
    SqlAlchemyScheduleWritePort,
)
from backend.bootstrap.providers_factory import ProvidersFactory
from backend.core.ports.schedule_port import IProviderScheduleSource

from utils.config.config_manager import ConfigManager
from utils.net.net_client import NetClient


class StandaloneBackend:
    """Композиция контроллеров/портов для standalone backend (без UI)."""
    def __init__(
            self,
            *,
            db,
            playlists_dir: str | Path,
            progress_repo=None,
            config_file: str | Path = "config/config.ini",
            providers: dict[str, IProviderPayloadSource] | None = None,
            schedule_sources: dict[str, IProviderScheduleSource] | None = None,
            logger=None,
            cache_dir: str | Path | None = None,
    ) -> None:
        self._db = db
        self._playlists_dir = Path(playlists_dir)
        self._progress = progress_repo

        cfg = ConfigManager(str(config_file))
        self.ctx = BackendContext.from_config(cfg)
        titles_port = SqlAlchemyTitlesPort(self._db)
        enricher = SqlAlchemyTitlesEnricherPort(self._db)
        self.titles = TitlesController(titles_port, enricher, config_manager=cfg)
        self.streams = StreamsController(self._db)
        storage: IPlaylistStorage = PlaylistManagerStorage(playlists_dir=playlists_dir)
        composer: IPlaylistComposer = PlaylistComposer()

        self.playlists = PlaylistsController(
            get_titles=self.titles.titles_get,
            storage=storage,
            composer=composer,
            progress_repo=progress_repo,
        )
        # ── Poster ingestion (background, optional) ──────────────────────────
        self._poster_job = None
        try:
            from utils.net.net_client import NetClient
            from backend.infra.poster.poster_job_adapter import PosterJobAdapter
            _net_cfg = getattr(cfg, "network", None)
            if _net_cfg is not None:
                self._poster_job = PosterJobAdapter(db=self._db, net_client=NetClient(_net_cfg))
        except Exception as _poster_err:
            # Poster ingestion is optional — backend works fine without it
            logging.getLogger("backend").debug("Poster ingestion not available: %s", _poster_err)

        # write-path (poster_job may be None → posters simply not queued)
        write_port = StorageProcessWritePort(storage=self._db, poster_job=self._poster_job)
        uc = ApplyProviderPayloadUseCase(write_port=write_port)
        self.process = ProcessController(use_case=uc)

        # providers wiring
        self._logger = logging.getLogger("backend")
        self.provider_boot_errors: list[str] = []
        self._cache_dir = Path("temp")
        self._cache_dir.mkdir(parents=True, exist_ok=True)

        if not providers:
            built = ProvidersFactory(logger=self._logger).build_all(
                cfg=cfg,
                cache_dir=self._cache_dir,
            )
            self.provider_boot_errors.extend(built.boot_errors)
            providers = built.payload_sources
            if schedule_sources is None:
                schedule_sources = built.schedule_sources

        self.provider_resolver = DictProviderResolver(providers=providers)
        self.pipeline = ProviderPipeline(resolver=self.provider_resolver, process=self.process)
        self.sync_search_and_process_uc = SyncSearchAndProcessUseCase(pipeline=self.pipeline)

        self.sync = SyncController(
            provider_resolver=self.provider_resolver,
            pipeline=self.pipeline,
            search_and_process_uc=self.sync_search_and_process_uc,
        )
        self.titles_update = TitlesUpdateController(titles=self.titles, sync=self.sync)

        # history writes
        self.history = HistoryController(
            write_port=SqlAlchemyHistoryWritePort(self._db)
        )

        # schedule — fetch_title_fn bridges pipeline into schedule controller
        from backend.transport.json_tool.async_runner import run as _run_async

        def _fetch_title(provider_code: str, external_id: str) -> bool:
            """Fetch a missing title from a provider and save it to DB."""
            try:
                result = _run_async(
                    self.pipeline.fetch_and_process(
                        provider_code=provider_code,
                        external_id=external_id,
                        mode="title",
                    )
                )
                return result.ok
            except Exception:
                return False

        schedule_read = SqlAlchemyScheduleReadPort(self._db)
        schedule_write = SqlAlchemyScheduleWritePort(self._db)
        self.schedule = ScheduleController(
            read_port=schedule_read,
            write_port=schedule_write,
            sources=schedule_sources or {},
            fetch_title_fn=_fetch_title,
        )

    # --- titles ---
    def titles_ids_search(self, query: str, provider: str | None = None):
        return self.titles.titles_ids_search(query=query, provider=provider)

    def titles_search(self, query: str, user_id: int = 42, enrich: bool = True):
        return self.titles.titles_search(query=query, user_id=user_id, enrich=enrich)

    def titles_get(self, *, title_ids: list[int]):
        return self.titles.titles_get(title_ids=title_ids)

    def title_get(self, title_id: int):
        return self.titles.title_get(title_id=title_id)

    def titles_list_episodes(self, *, title_ids: list[int]):
        return self.titles.titles_list_episodes(title_ids=title_ids)

    def title_list_episodes(self, title_id: int):
        return self.titles.title_list_episodes(title_id=title_id)

    # --- streams ---
    def streams_get(self, *, title_id: int, episode_number: int):
        return self.streams.streams_get(title_id=title_id, episode_number=episode_number)

    # --- playlists ---
    def playlist_compose(self, *, title_id: int, quality: str = "best") -> str:
        bundle = self.playlists.compose_multi(
            title_ids=[int(title_id)],
            quality=quality,
            mode="by_title",
            user_id=42,
            preview_count=1,
            name=None,
            make_key=False,
        )
        return bundle.m3u_path

    def playlist_compose_multi(
        self,
        *,
        title_ids: list[int],
        quality: str = "best",
        mode: str = "by_title",
        user_id: int = 42,
        preview_count: int = 1,
        name: str | None = None,
    ) -> str:
        bundle = self.playlists.compose_multi(
            title_ids=title_ids,
            quality=quality,
            mode=mode,
            user_id=user_id,
            preview_count=preview_count,
            name=name,
            make_key=False,
        )
        return bundle.m3u_path

    # --- sync ---
    async def sync_search_and_process(self, *a, **kw):
        return await self.sync.search_and_process(*a, **kw)

    async def sync_fetch_and_process(self, *a, **kw):
        return await self.sync.fetch_and_process(*a, **kw)

    async def sync_search_external_ids(self, *a, **kw):
        return await self.sync.search_external_ids(*a, **kw)

    async def sync_fetch_payload(self, *a, **kw):
        return await self.sync.fetch_payload(*a, **kw)
