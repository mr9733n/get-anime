import subprocess
import os
import logging

class PlaylistManager:
    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def save_playlist(self):
        self.logger.debug("Starting to save playlist.")
        data = self.read_json_data()
        if data is not None:
            if "list" in data and isinstance(data["list"], list) and len(data["list"]) > 0:
                playlists_folder = 'playlists'
                if not os.path.exists(playlists_folder):
                    os.makedirs(playlists_folder)
                    self.logger.debug(f"Created 'playlists' folder.")
                self.playlist_name = os.path.join(playlists_folder, f"{data['list'][0]['code']}.m3u")
                self.logger.debug(f"Saving playlist to {self.playlist_name}.")
                try:
                    if self.playlist_name is not None:
                        with open(self.playlist_name, 'w') as file:
                            for url in self.discovered_links:
                                full_url = "https://" + self.stream_video_url + url
                                file.write(f"#EXTINF:-1,{url}\n{full_url}\n")
                        self.logger.debug(f"Playlist {self.playlist_name} saved successfully.")
                    else:
                        error_message = "Playlist name is not set."
                        self.logger.error(error_message)
                        print(error_message)
                        return None
                    return self.playlist_name
                except Exception as e:
                    error_message = f"An error occurred while saving the playlist: {str(e)}"
                    self.logger.error(error_message)
                    print(error_message)
                    return None
            else:
                error_message = "No valid data available. Please fetch data first."
                self.logger.error(error_message)
                print(error_message)
        else:
            error_message = "No data available. Please fetch data first."
            self.logger.error(error_message)
            print(error_message)

    def all_links_play(self):
        self.logger.debug("Attempting to play all links.")
        try:
            vlc_path = self.video_player_path
            playlists_folder = 'playlists'
            if not os.path.exists(playlists_folder):
                os.makedirs(playlists_folder)
                self.logger.debug(f"Created 'playlists' folder.")
            if hasattr(self, 'playlist_name') and self.playlist_name is not None:
                playlist_path = os.path.join(playlists_folder, os.path.basename(self.playlist_name))
                self.logger.debug(f"Attempting to play playlist from {playlist_path}.")
                if os.path.exists(playlist_path):
                    media_player_command = [vlc_path, playlist_path]
                    subprocess.Popen(media_player_command)
                    self.logger.debug(f"Playing playlist {playlist_path}.")
                else:
                    error_message = "Playlist file not found in playlists folder."
                    self.logger.error(error_message)
                    print(error_message)
            else:
                error_message = "Please save the playlist first."
                self.logger.error(error_message)
                print(error_message)
        except Exception as e:
            error_message = f"An error occurred while playing the video: {str(e)}"
            self.logger.error(error_message)
            print(error_message)

    def play_playlist(self):
        self.logger.debug("Attempting to play specific playlist.")
        try:
            vlc_path = self.video_player_path
            playlists_folder = 'playlists'
            if hasattr(self, 'playlist_name') and self.playlist_name:
                playlist_path = os.path.join(playlists_folder, self.playlist_name)
                self.logger.debug(f"Attempting to play playlist from {playlist_path}.")
                if os.path.exists(playlist_path):
                    media_player_command = [vlc_path, playlist_path]
                    subprocess.Popen(media_player_command)
                    self.logger.debug(f"Playing playlist {playlist_path}.")
                else:
                    error_message = "Playlist file not found in playlists folder."
                    self.logger.error(error_message)
                    print(error_message)
            else:
                error_message = "Playlist name is not set."
                self.logger.error(error_message)
                print(error_message)
        except Exception as e:
            error_message = f"An error occurred while trying to play the playlist: {str(e)}"
            self.logger.error(error_message)
            print(error_message)
