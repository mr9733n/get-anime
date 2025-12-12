import re
import subprocess
import os
import logging
import sys
from pathlib import Path


class Playlist:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.playlist_path = "playlists/"
        os.makedirs(self.playlist_path, exist_ok=True)

    def save_playlist(self, sanitized_titles, links):
        """
        Save the playlist of links to an M3U file with a name based on title names.
        :param sanitized_titles: List of title names that will be used in the filename.
        :param links: List of links to be included in the playlist.
        """
        file_name = "".join(sanitized_titles)[:100] + ".txt"  # Limit the length to avoid file name issues
        file_path = os.path.join(self.playlist_path, file_name)

        filtered_links = [link for link in links if not link.endswith('.jpg')]

        if os.path.exists(file_path):
            try:
                with open(file_path, 'r', encoding='utf-8') as file:
                    existing_content = file.read()
                    new_content = "\n".join([link for link in filtered_links]) + "\n"

                    if existing_content == new_content:
                        self.logger.info(f"Playlist '{file_name}' is up-to-date. No changes needed.")
                        return file_name
                    else:
                        self.logger.info(f"Playlist '{file_name}' differs from the new data. Updating...")
            except Exception as e:
                self.logger.error(f"Failed to read existing playlist: {str(e)}")

        try:
            with open(file_path, 'w', encoding='utf-8') as file:
                file.write("\n")
                for link in filtered_links:
                    full_url = f"{link}"
                    file.write(full_url + '\n')

            self.logger.debug(f"Playlist saved successfully with {len(filtered_links)} links at {file_path}.")
        except Exception as e:
            error_message = f"Failed to save playlist: {str(e)}"
            self.logger.error(error_message)

        return file_name, filtered_links

    def play_playlist(self, file_name: str):
        try:
            file_path = Path(self.playlist_path, file_name).resolve()

            if not file_path.exists():
                self.logger.error(f"Playlist file not found: {file_path}")
                return

            # Абсолютный путь к mini_browser.py (подстрой под свой проект)
            browser_script = Path(__file__).parent / "mini_browser.py"
            browser_script = browser_script.resolve()

            if not browser_script.exists():
                self.logger.error(f"mini_browser.py not found: {browser_script}")
                return

            command = [
                sys.executable,
                str(browser_script),
                "--socks", "http://192.168.0.100:8866",
                "--file", str(file_path),
            ]

            subprocess.Popen(command, cwd=str(browser_script.parent))
            self.logger.debug(f"Open playlist: {file_path}")

        except Exception as e:
            self.logger.exception(f"Failed to open playlist: {e}")
