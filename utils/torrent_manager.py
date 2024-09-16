import os
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import re

import requests
from PIL import Image, UnidentifiedImageError
import io
import logging

class TorrentManager:
    def __init__(self):
        self.cache_file_path = "utils/poster_cache.txt"
        self.utils_json = "utils/response.json"  # Path to the response JSON file
        self.poster_links = []
        self.poster_images = []
        self.current_poster_index = 0
        self.logger = logging.getLogger(__name__)

    def handle_torrent_link(self, link, title_name=None, torrent_id=None):
        try:
            torrent_client_path = self.torrent_client_path

            # Путь для сохранения торрентов
            torrent_save_path = 'torrents'
            if not os.path.exists(torrent_save_path):
                os.makedirs(torrent_save_path)

            # Исправляем URL для скачивания
            if not link.startswith("https://"):
                link = "https://anilibria.tv" + link

            # Передаем title_name и torrent_id в download_torrent
            torrent_path = self.download_torrent(link, torrent_save_path, title_name, torrent_id)
            if torrent_path:
                subprocess.run([torrent_client_path, torrent_path], check=True)
                self.logger.info(f"Torrent saved and opened: {torrent_path}")
            else:
                self.logger.error("Failed to download or open torrent.")
        except Exception as e:
            error_message = f"Error handling torrent link: {str(e)}"
            self.logger.error(error_message)
            print(error_message)

    def download_torrent(self, url, save_path, title_name=None, torrent_id=None):
        try:
            response = requests.get(url)
            response.raise_for_status()  # Проверка на ошибки при скачивании

            # Формируем безопасное название файла
            if title_name:
                # Убираем недопустимые символы из названия файла
                safe_title = re.sub(r'[<>:"/\\|?*]', '_', title_name)
            else:
                safe_title = "torrent"

            # Добавляем ID тайтла, если он есть
            filename = f"{safe_title}_{torrent_id}.torrent" if torrent_id else f"{safe_title}.torrent"

            # Путь для сохранения файла
            torrent_path = os.path.join(save_path, filename)

            with open(torrent_path, 'wb') as file:
                file.write(response.content)

            self.logger.info(f"Torrent downloaded: {torrent_path}")
            return torrent_path
        except Exception as e:
            error_message = f"An error occurred while downloading the torrent: {str(e)}"
            self.logger.error(error_message)
            print(error_message)
            return None