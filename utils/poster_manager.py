# utils/poster_manager.py
import os
import threading
import time
import requests
from PIL import Image, UnidentifiedImageError
import io
import logging

class PosterManager:
    def __init__(self, display_callback=None):
        self.cache_file_path = "utils/poster_cache.txt"
        self.utils_json = "utils/response.json"
        self.poster_links = []
        self.poster_images = []
        self.current_poster_index = 0
        self.logger = logging.getLogger(__name__)
        self.display_callback = display_callback

    def write_poster_links(self, links):
        """
        Add poster URLs to the list and start downloading in the background.
        """
        # Add new links to the existing list, avoiding duplicates
        self.clear_cache_and_memory()
        self.poster_links.extend([link for link in links if link not in self.poster_links])
        self.logger.debug(f"Added {len(links)} new poster links. Total: {len(self.poster_links)}")
        self.start_background_download()

    def start_background_download(self):
        """
        Start the poster downloading process in a background thread.
        """
        download_thread = threading.Thread(target=self.download_posters_in_background)
        download_thread.start()

    def download_posters_in_background(self):
        """
        Download posters asynchronously and store them in memory.
        """
        for link in self.poster_links:
            try:
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36'
                }
                params = {'no_cache': 'true', 'timestamp': time.time()}
                start_time = time.time()
                response = requests.get(link, headers=headers, stream=True, params=params)
                response.raise_for_status()
                end_time = time.time()

                # Check if the content is an image
                if 'image' not in response.headers.get('Content-Type', ''):
                    self.logger.error(f"The URL did not return an image: {link}")
                    continue

                # Open and process the image
                link_io = io.BytesIO(response.content)
                poster_image = Image.open(link_io)
                self.poster_images.append(poster_image)
                self.display_callback(poster_image)
                num_kilobytes = len(response.content) / 1024
                self.logger.debug(f"Successfully downloaded poster. URL: '{link}', "
                                  f"Time taken: {end_time - start_time:.2f} seconds, "
                                  f"Image size: {num_kilobytes:.2f} Kb.")
            except UnidentifiedImageError:
                self.logger.error(f"Failed to identify and process the image data from: {link}")
            except Exception as e:
                self.logger.error(f"An error occurred while downloading the poster from {link}: {str(e)}")


    def get_next_poster(self):
        if not self.poster_images:
            self.logger.warning("No posters available to show.")
            return None
        self.current_poster_index = (self.current_poster_index + 1) % len(self.poster_images)
        return self.poster_images[self.current_poster_index]

    def clear_cache_and_memory(self):
        """
        Clears the cache file and memory to prepare for new poster data.
        """
        # Clear images in memory
        self.poster_links.clear()
        self.poster_images.clear()
        self.logger.debug("Poster images cleared from memory.")
