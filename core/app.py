# app.py
import logging
import logging.config
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
        self.torrent_manager = TorrentManager(
            torrent_save_path=self.torrent_save_path,
            torrent_client_path=self.torrent_client_path
        )
        self.pre = "https://"
        self.logger.debug(f"Video Player Path: {self.video_player_path}")
        self.logger.debug(f"Torrent Client Path: {self.torrent_client_path}")
        self.ui_manager = FrontManager(self)
        self.api_client = APIClient(self.base_url, self.api_version)
        self.poster_manager = PosterManager()
        self.playlist_manager = PlaylistManager()
        self.poster_manager = PosterManager(display_callback=self.ui_manager.display_poster)

    def load_config(self):
        self.stream_video_url = self.config_manager.get_setting('Settings', 'stream_video_url')
        self.base_url = self.config_manager.get_setting('Settings', 'base_url')
        self.api_version = self.config_manager.get_setting('Settings', 'api_version')
        self.video_player_path = self.config_manager.get_setting('Settings', 'video_player_path')
        self.torrent_client_path = self.config_manager.get_setting('Settings', 'torrent_client_path')
        self.torrent_save_path = "torrents/"

    def init_variables(self):
        self.discovered_links = []
        self.current_link = None

    def get_poster(self, title_data):
        try:
            # Construct the poster URL
            poster_url = self.pre + self.base_url + title_data["posters"]["small"]["url"]

            # Standardize the poster URL
            standardized_url = self.standardize_url(poster_url)

            # Check if the standardized URL is already in the cached poster links
            if standardized_url in map(self.standardize_url, self.poster_manager.poster_links):
                self.logger.debug(f"Poster URL already cached: {standardized_url}. Skipping fetch.")
                return

            # Clear the current poster and add the new poster link to the cache
            self.ui_manager.clear_poster()
            self.poster_manager.write_poster_links([standardized_url])

        except Exception as e:
            error_message = f"An error occurred while getting the poster: {str(e)}"
            self.logger.error(error_message)

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

    def standardize_url(self, url):
        """
        Standardizes the URL for consistent comparison.
        Strips spaces, removes query parameters if necessary, or any other needed cleaning.
        """
        # Basic URL standardization example: stripping spaces and removing query parameters
        return url.strip().split('?')[0]

    pass