from __future__ import annotations

import os
from pathlib import Path

from backend.core.ports.playlists import IPlaylistStorage
from utils.playlists.playlist_manager import PlaylistManager  # :contentReference[oaicite:1]{index=1}


class PlaylistManagerStorage(IPlaylistStorage):
    """
    Адаптер IPlaylistStorage вокруг utils.playlists.PlaylistManager.
    """
    def __init__(self, playlists_dir: str | Path = "playlists"):
        self._pm = PlaylistManager()
        # Always use an absolute path so that the .m3u8 file path returned to
        # the Desktop UI is openable from any working directory.
        abs_dir = str(Path(playlists_dir).resolve())
        self._pm.playlist_path = abs_dir
        os.makedirs(abs_dir, exist_ok=True)

    def save_bundle(
        self,
        *,
        sanitized_titles: list[str],
        links: list[str],
        host: str | None,
    ) -> tuple[str, str, str, str, int, int]:
        bundle = self._pm.save_playlist_bundle(
            sanitized_titles=sanitized_titles,
            links=links,
            stream_video_url=host or "",
        )
        return (
            bundle.m3u_name,
            bundle.m3u_path,
            bundle.web_name,
            bundle.web_path,
            int(bundle.streams_count),
            int(bundle.web_count),
        )
