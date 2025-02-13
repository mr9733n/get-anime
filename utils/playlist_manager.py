import re
import subprocess
import os
import logging


class PlaylistManager:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.playlist_path = "playlists/"
        os.makedirs(self.playlist_path, exist_ok=True)
        self.pre = "https://"

    @staticmethod
    def sanitize_filename(name):
        """
        Sanitize the filename by removing special characters that are not allowed in filenames.
        """
        return re.sub(r'[<>:"/\\|?*]', '_', name)

    def save_playlist(self, sanitized_titles, links, stream_video_url):
        """
        Save the playlist of links to an M3U file with a name based on title names.
        :param sanitized_titles: List of title names that will be used in the filename.
        :param stream_video_url: Base URL for constructing the full links.
        :param links: List of links to be included in the playlist.
        """
        file_name = "".join(sanitized_titles)[:100] + ".m3u"  # Limit the length to avoid file name issues
        file_path = os.path.join(self.playlist_path, file_name)

        filtered_links = [link for link in links if link.endswith('.m3u8')]

        if os.path.exists(file_path):
            try:
                with open(file_path, 'r', encoding='utf-8') as file:
                    existing_content = file.read()
                    new_content = "#EXTM3U\n" + "\n".join(
                        [f"{self.pre}{stream_video_url}{link}" for link in filtered_links]) + "\n"

                    if existing_content == new_content:
                        self.logger.info(f"Playlist '{file_name}' is up-to-date. No changes needed.")
                        return file_name
                    else:
                        self.logger.info(f"Playlist '{file_name}' differs from the new data. Updating...")
            except Exception as e:
                self.logger.error(f"Failed to read existing playlist: {str(e)}")

        try:
            with open(file_path, 'w', encoding='utf-8') as file:
                file.write("#EXTM3U\n")
                for link in filtered_links:
                    full_url = f"{self.pre}{stream_video_url}{link}"
                    file.write(full_url + '\n')

            self.logger.debug(f"Playlist saved successfully with {len(filtered_links)} links at {file_path}.")
        except Exception as e:
            error_message = f"Failed to save playlist: {str(e)}"
            self.logger.error(error_message)

        return file_name

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

