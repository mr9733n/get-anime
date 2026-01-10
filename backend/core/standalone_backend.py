from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

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
from backend.bootstrap.providers_factory import ProvidersFactory

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
            logger=None,
            cache_dir: str | Path | None = None,
    ) -> None:
        self._db = db
        self._playlists_dir = Path(playlists_dir)
        self._progress = progress_repo

        cfg = ConfigManager(str(config_file))
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
        # write-path
        write_port = StorageProcessWritePort(storage=self._db)
        uc = ApplyProviderPayloadUseCase(write_port=write_port)
        self.process = ProcessController(use_case=uc)

        # providers wiring
        self._logger = logging.getLogger("backend")
        self.provider_boot_errors: list[str] = []
        self._cache_dir = Path("temp")
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        cfg = ConfigManager(str(config_file))

        if not providers:
            providers = ProvidersFactory(logger=self._logger).build(
                cfg=cfg,
                cache_dir=self._cache_dir,
                boot_errors=self.provider_boot_errors,
            )

        self.provider_resolver = DictProviderResolver(providers=providers)
        self.pipeline = ProviderPipeline(resolver=self.provider_resolver, process=self.process)
        self.sync_search_and_process_uc = SyncSearchAndProcessUseCase(pipeline=self.pipeline)

        self.sync = SyncController(
            provider_resolver=self.provider_resolver,
            pipeline=self.pipeline,
            search_and_process_uc=self.sync_search_and_process_uc,
        )
        self.titles_update = TitlesUpdateController(titles=self.titles, sync=self.sync)

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
