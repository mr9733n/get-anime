import re
import subprocess
import os
import logging
from config_manager import ConfigManager



class PlaylistManager:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.playlist_path = "playlists/"  # Directory where playlists are saved
        os.makedirs(self.playlist_path, exist_ok=True)  # Ensure the directory exists

    @staticmethod
    def sanitize_filename(name):
        """
        Sanitize the filename by removing special characters that are not allowed in filenames.
        """
        # Replace special characters with an underscore
        return re.sub(r'[<>:"/\\|?*]', '_', name)

    def save_playlist(self, title_names, links, stream_video_url):
        """
        Save the playlist of links to an M3U file with a name based on title names.
        :param stream_video_url: Base URL for constructing the full links.
        :param title_names: List of title names that will be used in the filename.
        :param links: List of links to be included in the playlist.
        """
        # Generate a sanitized filename based on the title names
        sanitized_titles = [self.sanitize_filename(name) for name in title_names]
        file_name = "_".join(sanitized_titles)[:100] + ".m3u"  # Limit the length to avoid file name issues
        file_path = os.path.join(self.playlist_path, file_name)

        # Check if the file already exists
        if os.path.exists(file_path):
            print(f"Плейлист '{file_name}' уже существует. Файл не был сохранен.")
            self.logger.warning(f"Playlist '{file_name}' already exists. Skipping save.")
            return  # Skip saving to avoid overwriting

        try:
            with open(file_path, 'w', encoding='utf-8') as file:
                file.write("#EXTM3U\n")  # M3U file header
                # Filter links that end with .m3u8 and write them to the file
                filtered_links = [link for link in links if link.endswith('.m3u8')]
                for link in filtered_links:
                    full_url = f"https://{stream_video_url}{link}"  # Construct the full URL
                    file.write(full_url + '\n')

            self.logger.debug(f"Playlist saved successfully with {len(filtered_links)} links at {file_path}.")
        except Exception as e:
            error_message = f"Failed to save playlist: {str(e)}"
            self.logger.error(error_message)

    def play_playlist(self, file_name, video_player_path):
        """
        Open the saved M3U playlist in the default media player.
        :type video_player_path: object
        :param file_name: The name of the playlist file to be played.
        """
        file_path = os.path.join(self.playlist_path, file_name)

        try:
            if os.path.exists(file_path):
                media_player_command = [video_player_path, file_path]
                subprocess.Popen(media_player_command)
                self.logger.debug(f"Playing playlist: {file_path}.")
            else:
                print("Playlist file not found.")
        except Exception as e:
            error_message = f"Failed to play playlist: {str(e)}"
            self.logger.error(error_message)

