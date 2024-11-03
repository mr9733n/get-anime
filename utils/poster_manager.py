# utils/poster_manager.py
import os
import threading
import time
import requests
from PIL import Image, UnidentifiedImageError
import io
import logging

class PosterManager:
    def __init__(self, display_callback=None, save_callback=None):
        self._download_thread = None
        self.logger = logging.getLogger(__name__)
        self.poster_blobs = None
        self.poster_links = []
        self.poster_images = []
        self.current_poster_index = 0
        self.display_callback = display_callback
        self.save_callback = save_callback


    def write_poster_links(self, links):
        """
        Add poster URLs (with title_id) to the list and start downloading in the background.
        """
        self.clear_cache_and_memory()
        for title_id, link in links:
            if link not in map(lambda x: x[1], self.poster_links):
                self.poster_links.append((title_id, link))
                self.logger.debug(f"Added poster link for title ID {title_id}: {link}")

        # Асинхронная загрузка всех постеров
        self.start_background_download()

    def extract_title_id_from_link(self, link):
        """
        Extract the title ID from the poster link.
        """
        try:
            # Предполагается, что title_id содержится в пути ссылки, например: '/storage/releases/posters/9792/...'
            title_id = int(link.split('/')[-2])  # Извлекаем ID из предпоследнего элемента пути
            return title_id, link
        except (ValueError, IndexError):
            self.logger.error(f"Unable to extract title ID from link: {link}")
            return None

    def start_background_download(self):
        """
        Start the poster downloading process in a background thread.
        """
        download_thread = threading.Thread(target=self.download_posters_in_background)
        download_thread.start()

    def download_posters_in_background(self):
        while self.poster_links:
            title_id, link = self.poster_links.pop(0)
            try:
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36'
                }
                params = {'no_cache': 'true', 'timestamp': time.time()}
                response = requests.get(link, headers=headers, stream=True, params=params)
                response.raise_for_status()

                if 'image' not in response.headers.get('Content-Type', ''):
                    self.logger.error(f"The URL did not return an image: {link}")
                    continue

                link_io = io.BytesIO(response.content)
                poster_image = Image.open(link_io)

                # Display and save poster

                if self.save_callback:
                    self.save_callback(title_id, response.content)
                if self.display_callback:
                    self.display_callback(title_id)

                self.poster_images.append((poster_image, title_id))
            except UnidentifiedImageError:
                self.logger.error(f"Failed to identify and process the image data from: {link}")
            except Exception as e:
                self.logger.error(f"An error occurred while downloading the poster from {link}: {str(e)}")

    def next_poster(self):
        if self.poster_images:
            self.current_poster_index = (self.current_poster_index + 1) % len(self.poster_images)
            return self.poster_images[self.current_poster_index]
        return None

    def clear_cache_and_memory(self):
        """
        Clears the cache file and memory to prepare for new poster data.
        """
        self.poster_links.clear()
        self.poster_images.clear()
        self.logger.debug("Poster images cleared from memory.")


