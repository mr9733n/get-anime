# utils/poster_manager.py
import io
import time
import queue
import logging
import hashlib
import requests
import threading

from PIL import Image, UnidentifiedImageError

MAX_RETRIES = 3
RETRY_DELAY = 10  # Задержка в секундах между повторными попытками
MAX_IMAGE_SIZE_KB = 5000

class PosterManager:
    def __init__(self, save_callback=None):

        self.logger = logging.getLogger(__name__)
        self.poster_links = []
        self.save_callback = save_callback
        self.save_queue = queue.Queue()
        self._save_thread = None
        self._download_thread = None
        self._thread_complete_event = threading.Event()
        self._thread_complete_event.set()

    def write_poster_links(self, links):
        """
        Add poster URLs (with title_id) to the list and start downloading in the background.
        """
        self.clear_cache_and_memory()
        for title_id, link in links:
            if link not in map(lambda x: x[1], self.poster_links):
                self.poster_links.append((title_id, link))
                self.logger.debug(f"Added poster link for title ID {title_id}: {link[-41:]}")

        self.start_background_download()

    def extract_title_id_from_link(self, link):
        """
        Extract the title ID from the poster link.
        """
        try:
            # '/storage/releases/posters/9792/...'
            title_id = int(link.split('/')[-2])
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

    def _process_save_queue(self):
        """Worker thread that processes save operations and terminates when queue is empty"""
        try:
            while True:
                try:
                    title_id, content, hash_value = self.save_queue.get(timeout=1.0)
                except queue.Empty:
                    self.logger.info("[!] Save queue is empty, terminating thread")
                    break
                try:
                    if self.save_callback:
                        self.save_callback(title_id, content, hash_value)
                        self.logger.info(f"[*] Saved poster for title_id: {title_id}")
                    time.sleep(0.5)
                except Exception as e:
                    self.logger.error(f"Error saving poster for title_id {title_id}: {e}")
                finally:
                    self.save_queue.task_done()

        except Exception as e:
            self.logger.error(f"Error in save thread: {e}")
        finally:
            self._thread_complete_event.set()
            self.logger.info("[!!!] Poster save thread terminated")

    def _ensure_save_thread_running(self):
        """Start the save thread if it's not already running"""
        if self._thread_complete_event.is_set():
            self.logger.info("[!] Starting poster save thread")
            self._thread_complete_event.clear()
            self._save_thread = threading.Thread(target=self._process_save_queue)
            self._save_thread.start()
            return True
        return False

    def download_posters_in_background(self):
        """
        Download posters asynchronously and store them in memory.
        """
        items_queued = False
        while self.poster_links:
            title_id, link = self.poster_links.pop(0)
            retries = 0
            while retries < MAX_RETRIES:
                try:
                    headers = {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36'
                    }
                    params = {'no_cache': 'true', 'timestamp': time.time()}
                    start_time = time.time()
                    self.logger.info(f"Запрос к URL: {link}")
                    response = requests.get(link, headers=headers, stream=True, params=params)
                    self.logger.info(f"Статус ответа: {response.status_code}")
                    response.raise_for_status()
                    end_time = time.time()
                    content_type = response.headers.get('Content-Type', '')
                    self.logger.info(f"Content-Type: {content_type}")
                    if 'image' not in content_type:
                        self.logger.error(f"The URL did not return an image: {link}")
                        continue

                    content = response.content
                    hash_value = hashlib.md5(content).hexdigest()

                    link_io = io.BytesIO(content)
                    img = Image.open(link_io)
                    img.load()
                    width, height = img.size
                    img_format = img.format
                    num_kilobytes = len(response.content) / 1024

                    if width < 10 or height < 10 or width > 10000 or height > 10000:
                        self.logger.error(f"Invalid image dimensions: {width}x{height} for title_id {title_id}")
                        continue

                    if img_format not in ["JPEG", "PNG", "GIF", "WEBP"]:
                        self.logger.error(f"Unsupported image format: {img_format} for title_id {title_id}")
                        continue

                    if num_kilobytes > MAX_IMAGE_SIZE_KB:
                        self.logger.error(
                            f"Image too large ({num_kilobytes:.2f}KB > {MAX_IMAGE_SIZE_KB}KB) for title_id {title_id}")
                        continue

                    self.logger.info(f"Successfully downloaded poster for title_id {title_id}")
                    self.logger.debug(f"Poster details - URL: '{link[-41:]}', Format: {img_format}")
                    self.logger.debug(f"Poster metrics - Dimensions: {width}x{height}, Size: {num_kilobytes:.2f} KB")
                    self.logger.debug(f"Performance - Time: {end_time - start_time:.2f}s, Hash: {hash_value}...")

                    self.save_queue.put((title_id, content, hash_value))
                    items_queued = True
                    self.logger.debug(f"Queued poster save for title_id: {title_id}")
                    break
                except (UnidentifiedImageError, IOError, OSError) as img_err:
                    retries += 1
                    self.logger.error(f"Failed to identify and process the image data from: {link}: {img_err}")
                except Exception as e:
                    retries += 1
                    self.logger.error(f"An error occurred while downloading the poster from {link}: {str(e)}")
                if retries < MAX_RETRIES:
                    self.logger.info(f"Retrying in {RETRY_DELAY} seconds...")
                    time.sleep(RETRY_DELAY)
                else:
                    self.logger.error("Maximum number of retries reached. Unable to download posters.")
        if items_queued:
            self.logger.info(f"[+] Starting save thread to process {self.save_queue.qsize()} posters")
            self._ensure_save_thread_running()

    def clear_cache_and_memory(self):
        """
        Clears the cache file and memory to prepare for new poster data.
        """
        self.poster_links.clear()
        self.logger.debug("[poster_links] cleared from memory.")


