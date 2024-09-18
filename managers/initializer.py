import logging
from managers.torrent_manager import TorrentManager
from api.api_client import APIClient
from managers.poster_manager import PosterManager
from managers.playlist_manager import PlaylistManager


class Initializer:
    def __init__(self, config_manager):
        self.config_manager = config_manager
        self.logger = logging.getLogger(__name__)

    def setup_paths(self):
        """Sets up paths required for video player and torrent client."""
        video_player_path = self.config_manager.get_setting('Paths', 'video_player_path')
        torrent_client_path = self.config_manager.get_setting('Paths', 'torrent_client_path')
        torrent_save_path = "torrents/"  # Could be configurable
        self.logger.debug(f"Video Player Path: {video_player_path}")
        self.logger.debug(f"Torrent Client Path: {torrent_client_path}")
        return video_player_path, torrent_client_path, torrent_save_path

    def init_torrent_manager(self, torrent_save_path, torrent_client_path):
        """Initializes the TorrentManager."""
        return TorrentManager(torrent_save_path=torrent_save_path, torrent_client_path=torrent_client_path)

    def init_api_client(self):
        """Initializes the APIClient."""
        base_url = self.config_manager.get_setting('Settings', 'base_url')
        api_version = self.config_manager.get_setting('Settings', 'api_version')
        return APIClient(base_url, api_version)

    def init_poster_manager(self, display_callback):
        """Initializes the PosterManager with a display callback."""
        return PosterManager(display_callback=display_callback)

    def init_playlist_manager(self):
        """Initializes the PlaylistManager."""
        return PlaylistManager()
