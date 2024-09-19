# app.py
import logging
import logging.config
import platform
import re

from managers.config_manager import ConfigManager
from api.api_client import APIClient
from managers.poster_manager import PosterManager
from managers.playlist_manager import PlaylistManager
from managers.torrent_manager import TorrentManager
from ui.ui import FrontManager

class AnimePlayerApp:
    def __init__(self, window):
        self.logger = logging.getLogger(__name__)
        self.current_data = None
        self.sanitized_titles = []
        self.logger.debug("Initializing AnimePlayerApp")
        self.config_manager = ConfigManager('config.ini')
        self.title_names = []
        self.init_variables()
        self.load_config()
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

        return video_player_path, torrent_client_path

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

    def get_items_data(self, data):
        """
        Returns a list of valid items based on the structure of the input data.
        Handles both general title data and schedule data.
        """
        items = []  # Initialize an empty list for items
        day_enum = []  # Initialize a list for days (used for schedule data)
        
        try:
            # Check if data is structured as general title data (dictionary with "list" key)
            if isinstance(data, dict) and "list" in data:
                title_list = data["list"]
                for i, item in enumerate(title_list):
                    items.append(item)  # Add index and item

                return None, items

            # Handle the case where data is a single title (a dictionary, not a list)
            elif isinstance(data, dict):
                title_list = [data]  # Wrap the single title in a list
                for item in title_list:
                    if isinstance(item, dict) and "id" in item:
                        items.append(item)
                return None, items

            # Check if data is structured as schedule data (a list of day_info)
            elif isinstance(data, list):
                for day_info in data:
                    day = day_info.get("day")
                    title_list = day_info.get("list")
                    for i, item in enumerate(title_list):
                        items.append(item)  # Add index and item
                    day_enum.append(day)
                return day_enum, items

        except Exception as e:
            error_message = f"An error occurred while processing item data: {str(e)}"
            self.logger.error(error_message)
            return None, None
        
    def get_links_data(self, title, selected_quality):
        """
        Returns a list of links based on the structure of the title data.
        Handles all links: poster, playlist, torrent.
        """
        try:
            print(title)
            # Handle torrent links
            print("total episodes counted:", len(title['player']['list']))
            print(selected_quality)
            if "torrents" in title and isinstance(title["torrents"].get("list"), list):
                for torrent in title["torrents"]["list"]:
                    url = torrent.get("url")
                    quality = torrent.get("quality", {}).get("string", "Качество не указано")
                    torrent_id = torrent.get("torrent_id")
                    if url and torrent_id:
                        print("torrents:", url, torrent_id)
                        return url, quality, torrent_id

            # Handle HLS (video) links
            if "player" in title and isinstance(title["player"].get("list"), dict):
                for episode in title["player"]["list"].values():

                    if "hls" in episode:
                        hls = episode["hls"]
                        print(hls, episode)
                        if selected_quality in hls:
                            url = hls[selected_quality]
                            if url:
                                print(url)
                                return url, episode

            # If no links found, return None
            self.logger.error("No valid links found in the provided data.")
            return None, None, None

        except Exception as e:
            error_message = f"An error occurred while processing link data: {str(e)}"
            self.logger.error(error_message)
            return None, None, None

    def get_schedule(self, day):
        data = self.api_client.get_schedule(day)
        if 'error' in data:
            self.logger.error(data['error'])
            return
        self.get_poster(data)
        self.ui_manager.display_schedule(data)
        self.current_data = data

    def get_search_by_title(self):
        search_text = self.ui_manager.title_search_entry.get()
        if search_text:
            data = self.api_client.get_search_by_title(search_text)
            if 'error' in data:
                self.logger.error(data['error'])
                return
            self.get_poster(data)
            self.ui_manager.display_info(data)
            self.current_data = data
        else:
            self.logger.error("Search text is empty.")

    def get_random_title(self):
        data = self.api_client.get_random_title()
        if 'error' in data:
            self.logger.error(data['error'])
            return
        self.get_poster(data)
        self.ui_manager.display_info(data)
        self.current_data = data

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