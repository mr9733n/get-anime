from __future__ import annotations

from pathlib import Path

from backend.core.ports.playlists import IPlaylistStorage
from utils.playlists.playlist_manager import PlaylistManager  # :contentReference[oaicite:1]{index=1}


class PlaylistManagerStorage(IPlaylistStorage):
    """
    Адаптер IPlaylistStorage вокруг utils.playlists.PlaylistManager.
    """
    def __init__(self, playlists_dir: str | Path = "playlists"):
        self._pm = PlaylistManager()
        self._pm.playlist_path = str(playlists_dir)

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
