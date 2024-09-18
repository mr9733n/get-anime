# app.py
import logging
import logging.config
import platform
import re

from utils.config_manager import ConfigManager
from utils.api_client import APIClient
from utils.poster_manager import PosterManager
from utils.playlist_manager import PlaylistManager
from utils.torrent_manager import TorrentManager
from core.ui import FrontManager

class AnimePlayerApp:
    def __init__(self, window):
        self.sanitized_titles = []
        self.logger = logging.getLogger(__name__)
        self.logger.debug("Initializing AnimePlayerApp")
        self.window = window
        self.cache_file_path = "poster_cache.txt"
        self.config_manager = ConfigManager('config.ini')
        self.title_names = []
        self.init_variables()
        self.load_config()
        self.video_player_path, self.torrent_client_path = self.setup_paths()

        # Initialize TorrentManager with the correct paths
        self.torrent_manager = TorrentManager(
            torrent_save_path=self.torrent_save_path,
            torrent_client_path=self.torrent_client_path
        )

        # Corrected debug logging of paths using setup values
        self.logger.debug(f"Video Player Path: {self.video_player_path}")
        self.logger.debug(f"Torrent Client Path: {self.torrent_client_path}")

        # Initialize other components
        self.ui_manager = FrontManager(self)
        self.api_client = APIClient(self.base_url, self.api_version)
        self.poster_manager = PosterManager()
        self.playlist_manager = PlaylistManager()
        self.poster_manager = PosterManager(display_callback=self.ui_manager.display_poster)

    def load_config(self):
        """Loads the configuration settings needed by the application."""
        self.stream_video_url = self.config_manager.get_setting('Settings', 'stream_video_url')
        self.base_url = self.config_manager.get_setting('Settings', 'base_url')
        self.api_version = self.config_manager.get_setting('Settings', 'api_version')
        self.torrent_save_path = "torrents/"  # Ensure this is set correctly

    def setup_paths(self):
        """Sets up paths based on the current platform and returns them for use."""
        current_platform = platform.system()
        video_player_path = self.config_manager.get_video_player_path(current_platform)
        torrent_client_path = self.config_manager.get_torrent_client_path(current_platform)

        # Return paths to be used in the class
        return video_player_path, torrent_client_path

    def init_variables(self):
        self.discovered_links = []
        self.current_link = None

    def save_playlist_wrapper(self):
        """
        Wrapper function to handle saving the playlist.
        Collects title names and links, and passes them to save_playlist.
        """
        if self.discovered_links:
            self.sanitized_titles = [self.sanitize_filename(name) for name in self.title_names]
            self.playlist_manager.save_playlist(self.sanitized_titles, self.discovered_links, self.stream_video_url)
            self.logger.debug("Links was sent for saving playlist...")
        else:
            self.logger.error("No links was found for saving playlist.")

    def play_playlist_wrapper(self):
        """
        Wrapper function to handle playing the playlist.
        Determines the file name and passes it to play_playlist.
        """
        if not self.sanitized_titles:
            self.logger.error("Playlist not found, please save playlist first.")
            return

        file_name = "_".join(self.sanitized_titles)[:100] + ".m3u"
        video_player_path = self.video_player_path
        self.playlist_manager.play_playlist(file_name, video_player_path)
        self.logger.debug("Opening video player...")

    def save_torrent_wrapper(self, link, title_name, torrent_id):
        """
        Wrapper function to handle saving the torrent.
        Collects title names and links, and passes them to save_torrent_file.
        """
        try:
            sanitized_title_name = self.sanitize_filename(title_name)
            file_name = f"{sanitized_title_name}_{torrent_id}.torrent"

            self.torrent_manager.save_torrent_file(link, file_name)
            self.logger.debug("Opening torrent client app...")
        except Exception as e:
            error_message = f"Error in save_torrent_wrapper: {str(e)}"
            self.logger.error(error_message)

    @staticmethod
    def sanitize_filename(name):
        """
        Sanitize the filename by removing special characters that are not allowed in filenames.
        """
        return re.sub(r'[<>:"/\\|?*]', '_', name)

    pass