# utils/poster_manager.py
import os
import queue
import threading
import time
import requests
from PIL import Image, UnidentifiedImageError
import io
import logging

MAX_RETRIES = 3
RETRY_DELAY = 5  # Задержка в секундах между повторными попытками

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
                self.logger.debug(f"Added poster link for title ID {title_id}: {link[-41:]}")

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
        if download_thread is False:
            download_thread.start()

    def download_posters_in_background(self):
        """
        Download posters asynchronously and store them in memory.
        """
        retries = 0
        while self.poster_links:
            title_id, link = self.poster_links.pop(0)
            while retries < MAX_RETRIES:
                try:
                    headers = {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36'
                    }
                    params = {'no_cache': 'true', 'timestamp': time.time()}
                    start_time = time.time()
                    response = requests.get(link, headers=headers, stream=True, params=params)
                    response.raise_for_status()
                    end_time = time.time()
                    if 'image' not in response.headers.get('Content-Type', ''):
                        self.logger.error(f"The URL did not return an image: {link}")
                        continue

                    # Open and process the image
                    link_io = io.BytesIO(response.content)
                    poster_image = Image.open(link_io)
                    self.poster_images.append(poster_image)

                    # self.display_callback(poster_image)
                    num_kilobytes = len(response.content) / 1024
                    self.logger.debug(f"Successfully downloaded poster. URL: '{link[-41:]}', "
                                      f"Time taken: {end_time - start_time:.2f} seconds, "
                                      f"Image size: {num_kilobytes:.2f} Kb.")

                    # Display and save poster
                    if self.display_callback:
                        self.display_callback(poster_image, title_id)
                        self.logger.warning(f"!!!Display callback")

                    if self.save_callback:
                        self.save_callback(title_id, response.content)
                        self.logger.warning(f"!!!Save callback")

                    self.poster_images.append((poster_image, title_id))

                    break
                except UnidentifiedImageError:
                    retries += 1
                    self.logger.error(f"Failed to identify and process the image data from: {link}")
                except Exception as e:
                    retries += 1
                    self.logger.error(f"An error occurred while downloading the poster from {link}: {str(e)}")
                if retries < MAX_RETRIES:
                    self.logger.info(f"Retrying in {RETRY_DELAY} seconds...")
                    time.sleep(RETRY_DELAY)
                else:
                    self.logger.error("Maximum number of retries reached. Unable to download posters.")

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


