# app.py
import logging
import logging.config
import platform
import re

from managers.config_manager import ConfigManager
from api.api_client import APIClient
from managers.data_manager import Poster, Torrent, Episode, Title, ScheduleParser, TitleParser, RandomTitleParser
from managers.poster_manager import PosterManager
from managers.playlist_manager import PlaylistManager
from managers.torrent_manager import TorrentManager
from ui.ui_dearpygui import FrontManager

class AnimePlayerApp:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.current_data = None
        self.sanitized_titles = []

        self.logger.debug("Initializing AnimePlayerApp")
        self.config_manager = ConfigManager('config.ini')
        self.title_names = []
        self.init_variables()
        self.stream_video_url = self.config_manager.get_setting('Settings', 'stream_video_url')
        self.base_url = self.config_manager.get_setting('Settings', 'base_url')
        self.api_version = self.config_manager.get_setting('Settings', 'api_version')
        self.torrent_save_path = "torrents/"
        self.video_player_path, self.torrent_client_path = self.setup_paths()
        self.torrent_manager = TorrentManager(
            torrent_save_path=self.torrent_save_path,
            torrent_client_path=self.torrent_client_path
        )
        self.pre = "https://"
        self.logger.debug(f"Video Player Path: {self.video_player_path}")
        self.logger.debug(f"Torrent Client Path: {self.torrent_client_path}")
        self.ui_manager = FrontManager(self)
        self.api_client = APIClient(self.base_url, self.api_version)
        self.playlist_manager = PlaylistManager()
        self.poster_manager = PosterManager(display_callback=self.ui_manager.display_poster)


    def load_config(self):
        """Loads the configuration settings needed by the application."""
# Ensure this is set correctly

    def setup_paths(self):
        """Sets up paths based on the current platform and returns them for use."""
        current_platform = platform.system()
        video_player_path = self.config_manager.get_video_player_path(current_platform)
        torrent_client_path = self.config_manager.get_torrent_client_path(current_platform)

        return video_player_path, torrent_client_path

    def init_variables(self):
        self.discovered_links = []
        self.current_link = None

    def get_poster(self, poster_data):
        try:
            # Check if poster_data is a list or dictionary and access it properly
            if isinstance(poster_data, list):
                # Assuming the poster URL is in the first item of the list
                poster_url = poster_data[0].get("url", None) if poster_data else None
            elif isinstance(poster_data, dict):
                poster_url = poster_data.get("url", None)
            else:
                self.logger.error("Unexpected poster data format")
                return

            if poster_url:
                # Process the poster URL (e.g., download, display, etc.)
                self.logger.debug(f"Poster URL: {poster_url}")
            else:
                self.logger.error("No valid poster URL found")
        except Exception as e:
            self.logger.error(f"An error occurred while getting the poster: {str(e)}")

    def get_schedule(self, day):
        try:
            data = self.api_client.get_schedule(day)
            parsed_schedule = ScheduleParser.parse_schedule(data)
            self.display_schedule(parsed_schedule)
        except Exception as e:
            self.logger.error(f"Error fetching schedule for {day}: {str(e)}")



    def get_search_by_title(self):
        """Search for a title synchronously."""
        search_text = self.ui_manager.get_search_input()

        if search_text:
            try:
                data = self.api_client.get_search_by_title(search_text)
                if 'error' in data:
                    self.logger.error(data['error'])
                    return

                # Fetch the poster and display search results
                self.get_poster(data)
                title_data = TitleParser.parse_title(data)
                self.ui_manager.display_controller.display_info(title_data)
                self.current_data = data
            except Exception as e:
                self.logger.error(f"Error searching for title '{search_text}': {str(e)}")
        else:
            self.logger.error("Search text is empty.")

    def get_random_title(self):
        """Fetches a random title from the API, retrieves its poster, and displays it."""
        try:
            # Fetch the random title data from the API
            data = self.api_client.get_random_title()
            if 'error' in data:
                self.logger.error(data['error'])
                return

            # Fetch the poster and display the title information
            self.get_poster(data)
            title_data = RandomTitleParser.parse_random_title(data)
            self.ui_manager.display_controller.display_info(title_data)
            self.current_data = data
        except Exception as e:
            self.logger.error(f"Error fetching random title: {str(e)}")

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

    def display_schedule(self, parsed_schedule):
        pass