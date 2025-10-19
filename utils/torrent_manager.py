import os
import requests
import subprocess
import logging

class TorrentManager:
    def __init__(self, torrent_save_path="torrents/", torrent_client_path=None):
        self.logger = logging.getLogger(__name__)
        self.torrent_save_path = torrent_save_path
        self.torrent_client_path = torrent_client_path
        self.pre = "https://"
        os.makedirs(self.torrent_save_path, exist_ok=True)

    def save_torrent_file(self, link, file_name):
        """
        Download and save the torrent file from the given URL.
        :type link: object
        :param link: URL of the torrent file.
        :param file_name: The name to save the torrent file as.
        """
        file_path = os.path.abspath(os.path.join(self.torrent_save_path, file_name))
        url = f"{self.pre}anilibria.tv" + link

        try:
            response = requests.get(url, stream=True)
            response.raise_for_status()  # Raise an exception for HTTP errors

            # Save the torrent file
            with open(file_path, 'wb') as file:
                for chunk in response.iter_content(chunk_size=8192):
                    file.write(chunk)

            self.logger.debug(f"Torrent file saved successfully at {file_path}.")
            self.open_torrent_client(file_path)

        except Exception as e:
            error_message = f"Failed to save or open torrent file: {str(e)}"
            self.logger.error(error_message)

    def open_torrent_client(self, file_path):
        """
        Opens the saved torrent file using the configured torrent client.
        :param file_path: The path to the saved torrent file.
        """
        try:
            if not self.torrent_client_path:
                raise ValueError("Torrent client path is not set in the configuration.")

            self.logger.debug(f"Using torrent client path: {self.torrent_client_path}")

            if not os.path.exists(self.torrent_client_path):
                raise FileNotFoundError(f"Torrent client not found at path: {self.torrent_client_path}")

            if not os.path.exists(file_path):
                raise FileNotFoundError(f"Torrent file not found: {file_path}")

            subprocess.Popen([self.torrent_client_path, file_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            self.logger.debug(f"Torrent file opened in the client: {file_path}.")

        except Exception as e:
            error_message = f"Error opening torrent client: {str(e)}"
            self.logger.error(error_message)
