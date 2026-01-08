from __future__ import annotations

from pathlib import Path
from typing import Any

from backend.core.controllers.titles_controller import TitlesController
from backend.core.controllers.streams_controller import StreamsController
from backend.core.controllers.playlists_controller import PlaylistsController
from backend.core.ports.playlists import IPlaylistStorage, IPlaylistComposer
from backend.core.use_cases.playlist_composer import PlaylistComposer
from backend.infra.playlists.playlist_storage import PlaylistManagerStorage


class StandaloneBackend:
    def __init__(self, *, db: Any, playlists_dir: str | Path = "playlists", progress_repo=None):
        self._db = db
        self._playlists_dir = Path(playlists_dir)
        self._progress = progress_repo

        self.titles = TitlesController(self._db)
        self.streams = StreamsController(self._db)
        storage: IPlaylistStorage = PlaylistManagerStorage(playlists_dir=playlists_dir)
        composer: IPlaylistComposer = PlaylistComposer()

        self.playlists = PlaylistsController(
            get_titles=self.titles.titles_get,
            storage=storage,
            composer=composer,
            progress_repo=progress_repo,
        )
    # --- titles ---
    def titles_search(self, query: str, provider: str | None = None):
        return self.titles.titles_search(query=query, provider=provider)

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
