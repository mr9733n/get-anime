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
RETRY_DELAY = 10  # seconds
MAX_IMAGE_SIZE_KB = 5000

class PosterManager:
    def __init__(self, save_callback=None, net_client=None):
        self.logger = logging.getLogger(__name__)
        self.poster_links = []
        self.save_callback = save_callback
        self.net_client = net_client
        self.save_queue = queue.Queue()
        self._save_thread = None
        self._download_thread = None
        self._thread_complete_event = threading.Event()
        self._thread_complete_event.set()

    def write_poster_links(self, links):
        """
        Add poster URLs (with title_id) to the list and start downloading in the background.
        """
        for title_id, link in links:
            if link not in map(lambda x: x[1], self.poster_links):
                self.poster_links.append((title_id, link))
                self.logger.debug(f"Added poster link for title ID {title_id}: {link[-41:]}")

        self.start_background_download()

    def start_background_download(self):
        """
        Start the poster downloading process in a background thread.
        """
        if self._download_thread is None or not self._download_thread.is_alive():
            self.logger.info("[!] Starting poster download thread")
            self._download_thread = threading.Thread(
                target=self.download_posters_in_background,
            )
            self._download_thread.start()

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
                        'User-Agent': (
                            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                            'AppleWebKit/537.36 (KHTML, like Gecko) '
                            'Chrome/128.0.0.0 Safari/537.36'
                        )
                    }
                    params = {'no_cache': 'true', 'timestamp': time.time()}
                    start_time = time.time()
                    self.logger.info(f"Запрос к URL: {link}")
                    response = self.net_client.get(link, headers=headers, stream=True, params=params)
                    self.logger.info(f"Статус ответа: {response.status_code}")
                    response.raise_for_status()
                    end_time = time.time()
                    content_type = response.headers.get('Content-Type', '')
                    self.logger.info(f"Content-Type: {content_type}")

                    # ⛔ НЕ картинка — бессмысленно ретраиться
                    if 'image' not in content_type.lower():
                        self.logger.error(
                            f"The URL did not return an image for title_id {title_id}: {link}"
                        )
                        # не ретраим, просто пропускаем этот постер
                        break

                    content = response.content
                    hash_value = hashlib.md5(content).hexdigest()

                    link_io = io.BytesIO(content)
                    img = Image.open(link_io)
                    img.load()
                    width, height = img.size
                    img_format = img.format
                    num_kilobytes = len(content) / 1024

                    # ⛔ Некорректные размеры — тоже не надо долбить этот же URL
                    if width < 10 or height < 10 or width > 10000 or height > 10000:
                        self.logger.error(
                            f"Invalid image dimensions: {width}x{height} for title_id {title_id}"
                        )
                        break  # без ретраев

                    # ⛔ Неподдерживаемый формат
                    if img_format not in ["JPEG", "PNG", "GIF", "WEBP"]:
                        self.logger.error(
                            f"Unsupported image format: {img_format} for title_id {title_id}"
                        )
                        break  # без ретраев

                    # ⛔ Слишком большой файл
                    if num_kilobytes > MAX_IMAGE_SIZE_KB:
                        self.logger.error(
                            f"Image too large ({num_kilobytes:.2f}KB > {MAX_IMAGE_SIZE_KB}KB) "
                            f"for title_id {title_id}"
                        )
                        break  # без ретраев

                    # ✅ Всё ок — сохраняем
                    self.logger.info(f"Successfully downloaded poster for title_id {title_id}")
                    self.logger.debug(
                        f"Poster details - URL: '{link[-41:]}', Format: {img_format}"
                    )
                    self.logger.debug(
                        f"Poster metrics - Dimensions: {width}x{height}, "
                        f"Size: {num_kilobytes:.2f} KB"
                    )
                    self.logger.debug(
                        f"Performance - Time: {end_time - start_time:.2f}s, "
                        f"Hash: {hash_value}..."
                    )

                    self.save_queue.put((title_id, content, hash_value))
                    items_queued = True
                    self.logger.debug(f"Queued poster save for title_id: {title_id}")
                    break

                except (UnidentifiedImageError, IOError, OSError) as img_err:
                    # сюда имеет смысл дать несколько ретраев (битый поток и т.п.)
                    retries += 1
                    self.logger.error(
                        f"Failed to identify and process the image data from: {link}: {img_err}"
                    )
                except Exception as e:
                    retries += 1
                    self.logger.error(
                        f"An error occurred while downloading the poster from {link}: {str(e)}"
                    )

                if retries < MAX_RETRIES:
                    self.logger.info(f"Retrying in {RETRY_DELAY} seconds...")
                    time.sleep(RETRY_DELAY)
                else:
                    self.logger.error(
                        "Maximum number of retries reached. Unable to download posters "
                        f"for title_id {title_id}, URL: {link}"
                    )

        if items_queued:
            self.logger.info(f"[+] Starting save thread to process {self.save_queue.qsize()} posters")
            self._ensure_save_thread_running()
