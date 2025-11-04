import io
import os
import time
import json
import atexit
import logging
import urllib
import warnings
import datetime
import platform
import webbrowser

import requests
import subprocess
import configparser
import tkinter as tk

from tkinter import ttk
from PIL import Image, ImageTk
from tkinter.ttk import Combobox
from urllib.parse import urlparse, urlsplit, urlunsplit
from logging.handlers import TimedRotatingFileHandler

# Suppress urllib3 NotOpenSSLWarning
warnings.filterwarnings("ignore", category=UserWarning, module='urllib3')

# Suppress Tkinter deprecation warning
os.environ['TK_SILENCE_DEPRECATION'] = '1'

APP_MINOR_VERSION = '0.3.8'
APP_MAJOR_VERSION = '0.3'


class ConfigManager:
    def __init__(self, config_file):
        self.config = configparser.ConfigParser()
        self.config.read(config_file)

    def get_setting(self, section, setting, default=None):
        return self.config[section].get(setting, default)

    def get_torrent_client_path(self, platform_name):
        if platform_name == "Windows":
            return self.get_setting('Settings', 'win_torrent_client_path')
        elif platform_name == "Darwin":  # macOS
            return self.get_setting('Settings', 'mac_torrent_client_path')
        else:
            return None

    def get_video_player_path(self, platform_name):
        if platform_name == "Windows":
            return self.get_setting('Settings', 'win_video_player_path')
        elif platform_name == "Darwin":  # macOS
            return self.get_setting('Settings', 'mac_video_player_path')
        else:
            return None  # Handle other platforms if needed


class CustomTimedRotatingFileHandler(TimedRotatingFileHandler):
    def __init__(self, log_dir, log_filename, *args, **kwargs):
        super(CustomTimedRotatingFileHandler, self).__init__(*args, **kwargs)
        self.log_dir = log_dir
        self.log_filename = log_filename

    def getLogFileName(self, current_date):
        base_filename, file_extension = os.path.splitext(self.baseFilename)
        return f"{base_filename}_{current_date}.{file_extension}"


class AnimePlayerAppVer1:
    def __init__(self, window):
        self.logger = logging.getLogger(__name__)
        self.cache_file_path = "poster_cache.txt"
        self.poster_links = []
        self.config_manager = ConfigManager('config/config.ini')
        log_level = self.config_manager.get_setting('Logging', 'log_level', 'INFO')
        self.log_filename = "debug_log"
        self.window = window
        self.window.title("Anime Player Lite")
        self.window.geometry("1110x760")
        self.init_ui()
        self.init_logger(log_level)
        self.load_config()
        self.window.grid_rowconfigure(2, weight=1)
        self.window.grid_columnconfigure(0, weight=1)
        self.discovered_links = []
        self.current_link = None
        self.poster_data = []
        self.current_poster_index = 0
        self.clear_cache_file()

        atexit.register(self.delete_response_json)

    def load_config(self):
        # Get configuration values
        self.stream_video_url = self.config_manager.get_setting('Settings', 'stream_video_url')
        self.base_url = self.config_manager.get_setting('Settings', 'base_url')
        self.api_version = self.config_manager.get_setting('Settings', 'api_version')
        self.video_player_path, self.torrent_client_path = self.setup_paths()

    def setup_paths(self):
        """Sets up paths based on the current platform and returns them for use."""
        current_platform = platform.system()
        video_player_path = self.config_manager.get_video_player_path(current_platform)
        torrent_client_path = self.config_manager.get_torrent_client_path(current_platform)

        # Return paths to be used in the class
        return video_player_path, torrent_client_path

    def init_ui(self):
        self.btn_now = ttk.Button(self.window, text="Now", command=self.get_schedule_now)
        self.btn_now.grid(row=0, column=8, sticky="ew")
        self.btn_week = ttk.Button(self.window, text="Week", command=self.get_schedule_week)
        self.btn_week.grid(row=0, column=9, sticky="ew")
        # Create a label and entry for title search
        self.title_search_label = ttk.Label(self.window, text="Поиск по названию:")
        self.title_search_label.grid(row=0, column=0)
        self.title_search_entry = ttk.Entry(self.window)
        self.title_search_entry.grid(row=0, column=1, columnspan=5, sticky="ew")
        # Create a button for displaying information1
        self.display_button = ttk.Button(self.window, text="Отобразить информацию", command=self.search_by_title)
        self.display_button.grid(row=0, column=6, sticky="ew")
        self.display_button = ttk.Button(self.window, text="Random", command=self.random_title)
        self.display_button.grid(row=0, column=7, sticky="ew")
        # Create a "Сохранить плейлист" button and bind it to the save_playlist function
        self.save_button = ttk.Button(self.window, text="Сохранить плейлист", command=self.save_playlist)
        self.save_button.grid(row=4, column=0, columnspan=3, sticky="ew")
        # Create a "Сохранить плейлист" button and bind it to the save_playlist function
        self.play_button = ttk.Button(self.window, text="Воспроизвести плейлист", command=self.all_links_play)
        self.play_button.grid(row=5, column=0, columnspan=3, sticky="ew")
        # Create a dropdown menu for selecting quality using Combobox
        self.quality_label = ttk.Label(self.window, text="Качество:")
        self.quality_label.grid(row=3, column=8)
        self.quality_var = tk.StringVar()
        self.quality_var.set("fhd")
        quality_options = ["fhd", "hd", "sd"]
        self.quality_dropdown = Combobox(self.window, textvariable=self.quality_var, values=quality_options)
        self.quality_dropdown.grid(row=3, column=9)
        self.quality_dropdown.state(['readonly'])
        self.refresh_button = ttk.Button(self.window, text="Обновить", command=self.update_quality_and_refresh)
        self.refresh_button.grid(row=4, column=9, sticky="ew")
        self.window.grid_columnconfigure(1, weight=3)
        # Create a text field for displaying information
        self.text = tk.Text(self.window, wrap=tk.WORD, cursor="hand2")
        self.text.grid(row=2, column=3, columnspan=7, sticky="nsew")
        self.text.tag_configure("hyperlink", foreground="blue")
        self.poster_label = tk.Label(self.window)  # Создайте атрибут poster_label
        self.poster_label.grid(row=2, column=0, columnspan=3)
        self.next_poster_button = ttk.Button(self.window, text="Следующий постер", command=self.change_poster)
        self.next_poster_button.grid(row=3, column=0, columnspan=3, sticky="ew")

    def log_message(self, message):
        self.logger.debug(message)

    def init_logger(self, log_level):
        # Create logger
        self.logger = logging.getLogger("AnimePlayerAppVer1")
        self.logger.setLevel(log_level)
        log_folder = 'logs'
        if not os.path.exists(log_folder):
            os.makedirs(log_folder)
        # Define log file path with current date
        current_date = datetime.datetime.now().strftime("%Y-%m-%d")
        log_file = os.path.join(log_folder, f"{self.log_filename}.txt")
        print(f"Log file path: {log_file}")
        handler = CustomTimedRotatingFileHandler(log_folder, self.log_filename, log_file, when="midnight", interval=1,
                                                 encoding='utf-8')
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        self.log_message("Start application...")

    def read_json_data(self):
        try:
            utils_folder = 'temp'
            os.makedirs(utils_folder, exist_ok=True)
            utils_json = os.path.join(utils_folder, 'response.json')
            self.log_message(f"Attempting to read {utils_json}.")
            with open(utils_json, 'r', encoding='utf-8') as file:
                raw = json.load(file)
            self.log_message(f"Successfully read data from {utils_json}.")
            # Адаптируем под единый вид
            return self._adapt_payload_for_display_list(raw)
        except FileNotFoundError:
            self.log_message(f"File {utils_json} not found.")
            return None
        except json.JSONDecodeError as e:
            self.log_message(f"Error decoding JSON data from {utils_json}: {str(e)}")
            return None

    def delete_response_json(self):
        try:
            utils_folder = 'temp'
            utils_json = os.path.join(utils_folder, 'response.json')
            if os.path.exists(utils_json):
                self.log_message(f"Attempting to delete {utils_json}.")
                os.remove(utils_json)
                self.log_message(f"Successfully deleted {utils_json}.")
            else:
                self.log_message(f"File {utils_json} does not exist. No need to delete.")
        except OSError as e:
            error_message = f"An error occurred while deleting {utils_json}: {str(e)}"
            self.log_message(error_message)

    def save_playlist(self):
        self.log_message("Starting to save playlist.")
        data = self.read_json_data()
        if not (data and "list" in data and isinstance(data["list"], list) and data["list"]):
            msg = "No valid data available. Please fetch data first."
            self.log_message(msg)
            print(msg)
            return

        # если ссылок ещё нет – попробуем собрать их из видимых тайтлов
        if not self.discovered_links:
            q = self.quality_var.get()
            for title in data["list"]:
                # 1) берём уже префетченные эпизоды из now, если есть
                episodes = (title.get("_prefetched_episodes") or [])
                # 2) если их нет — дотягиваем один раз релиз и берём episodes
                if not episodes:
                    rid = self._release_identity(title)
                    if rid:
                        url = f"https://{self.base_url}/api/{self.api_version}/anime/releases/{urllib.parse.quote(rid)}"
                        rel = self._get_json(url) or {}
                        episodes = rel.get("episodes") or rel.get("data", {}).get("episodes") or []

                # 3) для каждого эпизода дотягиваем hls и кладём в discovered_links
                for ep in episodes:
                    eid = ep.get("id") or ep.get("releaseEpisodeId") or ep.get("episodeId")
                    if not eid:
                        continue
                    detail = self._get_json(
                        f"https://{self.base_url}/api/{self.api_version}/anime/releases/episodes/{eid}")
                    if not detail:
                        continue
                    hls = self._flatten_hls(detail)
                    # имя качества в ответе может быть fhd/hd/sd или hls_1080/hls_720/hls_480
                    m3u8 = (
                        hls.get(q) or
                        hls.get("hls_1080") if q == "fhd" else (hls.get("hls_720") if q == "hd" else hls.get("hls_480"))
                    )
                    if not m3u8:
                        # fallback – любой найденный поток
                        m3u8 = hls.get("hls_1080") or hls.get("hls_720") or hls.get("hls_480") or hls.get(
                            "fhd") or hls.get("hd") or hls.get("sd")
                    if not m3u8:
                        continue
                    if not (m3u8.startswith("http://") or m3u8.startswith("https://")):
                        m3u8 = "https://" + self.stream_video_url + m3u8
                    m3u8 = self._normalize_stream_url(m3u8)
                    if m3u8 not in self.discovered_links:
                        self.discovered_links.append(m3u8)

        # дальше — как было, только с фиксом абсолютных URL
        playlists_folder = 'playlists'
        os.makedirs(playlists_folder, exist_ok=True)
        name_part = data['list'][0].get('code') or data['list'][0].get('id') or "playlist"
        self.playlist_name = os.path.join(playlists_folder, f"{name_part}.m3u")

        self.log_message(f"Saving playlist to {self.playlist_name}.")

        if not self.discovered_links:
            msg = "Nothing to save: no episode streams found."
            self.log_message(msg)
            print(msg)
            return

        try:
            with open(self.playlist_name, 'w', encoding='utf-8') as file:
                for url in self.discovered_links:
                    if url.startswith("http://") or url.startswith("https://") or url.startswith("magnet:?"):
                        full_url = url
                    else:
                        full_url = "https://" + self.stream_video_url + url
                    file.write(f"#EXTINF:-1,{os.path.basename(full_url)}\n{full_url}\n")
            self.log_message(f"Playlist {self.playlist_name} saved successfully.")
            return self.playlist_name
        except Exception as e:
            msg = f"An error occurred while saving the playlist: {str(e)}"
            self.log_message(msg)
            print(msg)
            return

    def all_links_play(self):
        self.log_message("Attempting to play all links.")
        try:
            vlc_path = self.video_player_path
            playlists_folder = 'playlists'
            if not os.path.exists(playlists_folder):
                os.makedirs(playlists_folder)
                self.log_message(f"Created 'playlists' folder.")
            if hasattr(self, 'playlist_name') and self.playlist_name is not None:
                playlist_path = os.path.join(playlists_folder, os.path.basename(self.playlist_name))
                self.log_message(f"Attempting to play playlist from {playlist_path}.")
                if os.path.exists(playlist_path):
                    media_player_command = [vlc_path, playlist_path]
                    subprocess.Popen(media_player_command)
                    self.log_message(f"Playing playlist {playlist_path}.")
                else:
                    error_message = "Playlist file not found in playlists folder."
                    self.log_message(error_message)
                    print(error_message)
            else:
                error_message = "Please save the playlist first."
                self.log_message(error_message)
                print(error_message)
        except Exception as e:
            error_message = f"An error occurred while playing the video: {str(e)}"
            self.log_message(error_message)
            print(error_message)

    # Обновленная функция для обработки кликов по ссылкам
    def on_link_click(self, event):
        try:
            link_index = int(event.widget.tag_names(tk.CURRENT)[1])
            link = self.discovered_links[link_index]

            # 1) magnet-ссылки — сразу в торрент-клиент
            if link.startswith('magnet:?'):
                torrent_client_path = self.torrent_client_path
                subprocess.Popen([torrent_client_path, link])
                self.log_message(f"Opened magnet in client: {link}")
                return

            # 2) прямой API-URL на .torrent: /api/v1/anime/torrents/{hashOrId}/file
            if '/api/' in link and '/anime/torrents/' in link and link.endswith('/file'):
                torrent_save_path = 'torrents'
                os.makedirs(torrent_save_path, exist_ok=True)
                torrent_path = self.download_torrent(link, torrent_save_path)
                if torrent_path:
                    subprocess.Popen([self.torrent_client_path, torrent_path])
                    self.log_message(f"Torrent saved and opened: {torrent_path}")
                else:
                    self.log_message("Failed to download or open torrent.")
                return

            self.log_message(f"Unknown link type: {link}")
        except Exception as e:
            error_message = f"An error occurred while processing the link: {str(e)}"
            self.log_message(error_message)
            print(error_message)

    # Универсальная функция для обработки торрентов и магнитных ссылок
    def handle_torrent_link(self, link):
        try:
            torrent_client_path = self.torrent_client_path

            # Если ссылка — это торрент URL, корректируем и скачиваем его
            torrent_save_path = 'torrents'
            if not os.path.exists(torrent_save_path):
                os.makedirs(torrent_save_path)

            # Исправляем URL для скачивания
            if not link.startswith("https://"):
                link = "https://anilibria.top" + link

            torrent_path = self.download_torrent(link, torrent_save_path)
            if torrent_path:
                subprocess.run([torrent_client_path, torrent_path], check=True)
                self.log_message(f"Torrent saved and opened: {torrent_path}")
            else:
                self.log_message("Failed to download or open torrent.")

        except Exception as e:
            error_message = f"Error handling torrent link: {str(e)}"
            self.log_message(error_message)
            print(error_message)

    # Функция для скачивания торрента
    def download_torrent(self, url, save_path):
        try:
            parsed_url = urlparse(url)
            filename = os.path.basename(parsed_url.path)
            response = requests.get(url)
            response.raise_for_status()  # Проверка на ошибки при скачивании
            if not filename:
                filename = "torrent"  # Если путь пустой, зададим имя по умолчанию
            torrent_path = os.path.join(save_path, filename)
            with open(torrent_path, 'wb') as file:
                file.write(response.content)
            self.log_message(f"Torrent downloaded: {torrent_path}")
            return torrent_path
        except Exception as e:
            error_message = f"An error occurred while downloading the torrent: {str(e)}"
            self.log_message(error_message)
            print(error_message)
            return None

    def play_playlist(self):
        self.log_message("Attempting to play specific playlist.")
        try:
            vlc_path = self.video_player_path
            playlists_folder = 'playlists'
            if hasattr(self, 'playlist_name') and self.playlist_name:
                playlist_path = os.path.join(playlists_folder, self.playlist_name)
                self.log_message(f"Attempting to play playlist from {playlist_path}.")
                if os.path.exists(playlist_path):
                    media_player_command = [vlc_path, playlist_path]
                    subprocess.Popen(media_player_command)
                    self.log_message(f"Playing playlist {playlist_path}.")
                else:
                    error_message = "Playlist file not found in playlists folder."
                    self.log_message(error_message)
                    print(error_message)
            else:
                error_message = "Playlist name is not set."
                self.log_message(error_message)
                print(error_message)
        except Exception as e:
            error_message = f"An error occurred while trying to play the playlist: {str(e)}"
            self.log_message(error_message)
            print(error_message)

    def get_poster(self, title_data):
        try:
            self.clear_poster()

            poster_url = None
            # новый v1
            if "posters" in title_data and "small" in title_data["posters"]:
                poster_url = title_data["posters"]["small"].get("url")
            # если адаптер не заполнил (или пришло старое) — попробуем прямое поле
            if not poster_url and "poster" in title_data:
                p = title_data["poster"] or {}
                poster_url = p.get("optimized", {}).get("preview") or p.get("preview") or p.get("src")

            if poster_url and not poster_url.startswith("http"):
                poster_url = "https://" + self.base_url + poster_url

            if poster_url:
                self.write_poster_links([poster_url])
                # названия — через безопасные ключи
                name_ru = (title_data.get("names") or {}).get("ru") or ""
                self.show_poster(poster_url)
                self.logger.debug(f"Successfully GET poster for title '{name_ru}'. URL: '{poster_url}' ")
            else:
                self.logger.debug("No poster url found for title")

        except Exception as e:
            self.log_message(f"An error occurred while GET processing the poster: {str(e)}")
            print(f"An error occurred while GET processing the poster: {str(e)}")

    def show_poster(self, poster_url):
        try:
            self.clear_poster()
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.5845.660 YaBrowser/23.9.5.660 Yowser/2.5 Safari/537.36'}
            params = {'no_cache': 'true', 'timestamp': time.time()}
            start_time = time.time()
            response = requests.get(poster_url, headers=headers, stream=True, params=params)
            end_time = time.time()
            response.raise_for_status()
            poster_image = Image.open(io.BytesIO(response.content))
            poster_photo = ImageTk.PhotoImage(poster_image)
            self.poster_label = tk.Label(self.window, image=poster_photo)
            self.poster_label.grid(row=2, column=0, columnspan=3)
            self.poster_label.image = poster_photo
            response.raise_for_status()
            num_bytes = len(response.content) if response.content else 0
            num_kilobytes = num_bytes / 1024
            self.logger.debug(f"Successfully SHOW poster. URL: '{poster_url}', "
                              f"Time taken: {end_time - start_time:.2f} seconds, "
                              f"Image size: {num_kilobytes} Kb.")

        except requests.exceptions.RequestException as e:
            error_message = f"An error occurred while SHOW downloading the poster: {str(e)}"
            self.log_message(error_message)
            print(error_message)
        except Exception as e:
            error_message = f"An error occurred while SHOW processing the poster: {str(e)}"
            self.log_message(error_message)
            print(error_message)

    def clear_cache_file(self):
        try:
            utils_folder = 'temp'
            if not os.path.exists(utils_folder):
                os.makedirs(utils_folder)
                self.log_message(f"Created 'temp' folder.")
            cache_file = os.path.join(utils_folder, self.cache_file_path)
            if os.path.exists(cache_file):
                os.remove(cache_file)
                self.logger.debug("Cache file cleared successfully.")
        except Exception as e:
            error_message = f"An error occurred while clearing the cache file: {str(e)}"
            self.log_message(error_message)
            print(error_message)

    def read_poster_links(self):
        poster_links = []
        try:
            utils_folder = 'temp'
            if not os.path.exists(utils_folder):
                os.makedirs(utils_folder)
                self.log_message(f"Created 'temp' folder.")
            cache_file = os.path.join(utils_folder, self.cache_file_path)
            if os.path.exists(cache_file):
                with open(cache_file, "r") as file:
                    for line in file:
                        poster_links.append(line.strip())
                self.logger.debug("Cache file read successfully. ")
        except Exception as e:
            error_message = f"An error occurred while reading the cache file: {str(e)}"
            self.log_message(error_message)
            print(error_message)
        return poster_links

    def write_poster_links(self, poster_links):
        try:
            utils_folder = 'temp'
            if not os.path.exists(utils_folder):
                os.makedirs(utils_folder)
                self.log_message(f"Created 'temp' folder.")
            cache_file = os.path.join(utils_folder, self.cache_file_path)
            with open(cache_file, "a") as file:
                for link in poster_links:
                    file.write(link + "\n")
            self.logger.debug("Cache file writen successfully.")
        except Exception as e:
            error_message = f"An error occurred while writing to the cache file: {str(e)}"
            self.log_message(error_message)
            print(error_message)

    def change_poster(self):
        try:
            poster_links = self.read_poster_links()
            # print(f"{[poster_links]}")
            if poster_links:
                self.clear_poster()
                self.current_poster_index = (self.current_poster_index + 1) % len(poster_links)
                # print(self.current_poster_index)
                current_poster_url = poster_links[self.current_poster_index]
                # print(current_poster_url)
                # print(current_poster_filename)
                self.show_poster(current_poster_url)
                self.logger.debug(f"Successfully CHANGE poster. URL: '{current_poster_url}' ")
        except requests.exceptions.RequestException as e:
            error_message = f"An error occurred while CHANGE downloading the poster: {str(e)}"
            self.log_message(error_message)
            print(error_message)
        except Exception as e:
            error_message = f"An error occurred while CHANGE processing the poster: {str(e)}"
            self.log_message(error_message)
            print(error_message)

    def clear_poster(self):
        try:
            if hasattr(self, 'poster_label'):
                self.poster_label.destroy()
        except Exception as e:
            error_message = f"An error occurred while clearing the poster: {str(e)}"
            self.log_message(error_message)
            print(error_message)

    # === ADAPTERS FOR NEW V1 API ===

    def _adapt_release(self, r: dict) -> dict:
        """Приводим релиз v1 к 'почти-старому' виду, чтобы display_* не падали."""
        if not isinstance(r, dict):
            return {}

        title_id = r.get("id")
        # name(s)
        name = r.get("name", {}) or {}
        names = {
            "ru": name.get("main") or "",
            "en": name.get("english") or "",
            "alternative": name.get("alternative") or ""
        }

        # type
        t = r.get("type", {}) or {}
        type_full = t.get("description") or t.get("value") or ""
        _type = {"full_string": type_full}

        # status (в v1 статуса-строки нет — соберём сами)
        is_ongoing = bool(r.get("is_ongoing"))
        status_string = "Онгоинг" if is_ongoing else "Завершён"
        status = {"string": status_string}

        # genres (в v1 это массив объектов c name)
        genres_raw = r.get("genres") or []
        genres = [g.get("name") for g in genres_raw if isinstance(g, dict) and g.get("name")]

        # year / season совместим под старое поле "season.year"
        season = {"year": r.get("year")}

        # poster (в v1 поле poster.*)
        poster = r.get("poster") or {}
        poster_url = poster.get("optimized", {}).get("preview") or poster.get("preview") or poster.get("src")
        if poster_url and not poster_url.startswith("http"):
            poster_url = "https://" + self.base_url + poster_url

        posters = {"small": {"url": poster_url}} if poster_url else {}

        # торренты (v1): есть magnet, filename и самое главное — hash/id -> /anime/torrents/{hashOrId}/file
        torrents_list = []
        for t in r.get("torrents") or []:
            q = t.get("quality")
            quality_string = (
                q if isinstance(q, str)
                else (q.get("label") if isinstance(q, dict) else None)
            )

            hash_or_id = t.get("hash") or t.get("id")
            file_url = (
                f"https://{self.base_url}/api/{self.api_version}/anime/torrents/{hash_or_id}/file"
                if hash_or_id else None
            )

            torrents_list.append({
                # теперь всегда правильная ссылка на .torrent файл через API
                "url": file_url,
                "magnet": t.get("magnet"),
                "quality": {"string": quality_string or "—"},
                # полезно сохранить исходные поля на всякий случай
                "_filename": t.get("filename"),
                "_hash": t.get("hash"),
                "_id": t.get("id"),
            })
        torrents = {"list": torrents_list} if torrents_list else {}

        # ссылка на страницу релиза (для клика в тексте)
        alias = r.get("alias")
        page_url = f"https://{self.base_url}/release/{alias}" if alias else None

        return {
            "id": title_id,
            "names": names,
            "type": _type,
            "status": status,
            "description": r.get("description") or "",
            "genres": genres,
            "season": season,
            "posters": posters,
            "torrents": torrents,
            "code": alias,
            "_page_url": page_url,  # вспомогательное для клика
            # player / episodes намеренно не мапплю: в v1 прямых hls-ссылок нет
        }

    def _adapt_payload_for_display_list(self, payload):
        """
        Приводим разные ответы к единому формату {"list":[releases...]} где releases уже адаптированы.
        Поддерживаем:
          - /anime/releases/random -> array[release]
          - /anime/releases/{id} -> object release
          - /anime/release/list -> {"data":[release,...]}
          - /anime/schedule/now -> {"today":[{release:...}, ...], "tomorrow":[...], "yesterday":[...]}
          - /anime/schedule/week -> {"data":[{release:...}, ...]}
        """
        if payload is None:
            return {"list": []}

        # если это уже старый формат
        if isinstance(payload, dict) and "list" in payload and isinstance(payload["list"], list):
            # предполагаем, что элементы уже приведены
            return payload

        # schedule.now
        if isinstance(payload, dict) and any(k in payload for k in ("today", "tomorrow", "yesterday")):
            items = []
            for key in ("today", "tomorrow", "yesterday"):
                for it in payload.get(key, []) or []:
                    rel = (it or {}).get("release") or {}
                    adapted = self._adapt_release(rel)
                    # пронесём эпизоды, если API их вложил рядом
                    pref_eps = (it or {}).get("episodes") or []
                    if pref_eps:
                        adapted["_prefetched_episodes"] = pref_eps
                    items.append(adapted)
            return {"list": items}

        # schedule.week
        # /anime/releases/list -> {"data":[...]} (общий случай уже покрыт выше)
        # /anime/releases/random -> array
        if isinstance(payload, list):
            items = []
            for it in payload:
                rel = (it or {}).get("release") or it  # вдруг пришло просто release
                items.append(self._adapt_release(rel))
            return {"list": items}

        # /anime/releases/{id} -> object
        if isinstance(payload, dict):
            # это одиночный релиз
            return {"list": [self._adapt_release(payload)]}

        return {"list": []}

    # === EPISODES (v1) ===

    def _release_identity(self, title: dict) -> str:
        """Возвращает то, чем можно запросить релиз: alias (code) или id."""
        return (title.get("code") or title.get("id") or "").strip()

    def _ensure_temp(self):
        utils_folder = 'temp'
        os.makedirs(utils_folder, exist_ok=True)
        return os.path.join(utils_folder, 'response.json')

    def _fetch_to_temp_and_render(self, url: str, render_fn):
        start = time.time()
        try:
            r = requests.get(url, timeout=15)
            text = r.text or ""
            if r.status_code == 200:
                utils_json = self._ensure_temp()
                with open(utils_json, 'w', encoding='utf-8') as f:
                    f.write(text)
                render_fn()
                self.logger.debug(
                    f"GET OK: {url}, time={time.time() - start:.2f}s, size={len(text)}"
                )
            else:
                msg = f"Error {r.status_code}: Unable to fetch data from the API."
                try:
                    err = r.json()
                    if isinstance(err, dict) and "error" in err:
                        msg += f" Error message: {err['error'].get('message', '')}"
                except Exception:
                    pass
                self.log_message(msg)
                print(msg)
        except Exception as e:
            self.log_message(f"Request failed {url}: {e}")
            print(f"Request failed {url}: {e}")

    def _get_json(self, url: str):
        try:
            r = requests.get(url, timeout=15)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            self.log_message(f"GET {url} failed: {e}")
            return None

    def _flatten_hls(self, obj):
        """
        Ищем словарь с ключами (fhd/hd/sd) где угодно в ответе.
        Возвращаем {'fhd': '/hls/...m3u8', ...} или {}.
        """
        if isinstance(obj, dict):
            keys = set(obj.keys())
            if {'hls_1080', 'hls_720', 'hls_480'} & keys:
                return {
                    k: v for k, v in obj.items()
                    if k in ('hls_1080', 'hls_720', 'hls_480') and isinstance(v, str)
                }
            for v in obj.values():
                found = self._flatten_hls(v)
                if found:
                    return found
        elif isinstance(obj, list):
            for v in obj:
                found = self._flatten_hls(v)
                if found:
                    return found
        return {}

    def _render_episodes_list(self, release_identity: str, title: dict = None):
        """
        Тянем /anime/releases/{id_or_alias} и показываем список серий.
        """
        if not release_identity:
            self.text.insert(tk.END, "\nЭпизоды: неизвестен идентификатор релиза\n")
            return

        if title and isinstance(title.get("_prefetched_episodes"), list) and title["_prefetched_episodes"]:
            episodes = title["_prefetched_episodes"]
            self.text.insert(tk.END, "\nЭпизоды:\n")
            for ep in episodes:
                eid = ep.get("id") or ep.get("releaseEpisodeId") or ep.get("episodeId")
                num = int(ep.get("ordinal") or 0)
                nm = ep.get("name") or ep.get("title") or ""
                line = f"• Серия {num}"
                if nm:
                    line += f": {nm}"
                line += " — "
                tag = f"hyperlink_play_ep_{eid or num}"
                self.text.insert(tk.END, line)
                self.text.insert(tk.END, "Смотреть", (tag,))
                self.text.insert(tk.END, "\n")
                if eid:
                    self.text.tag_bind(tag, "<Button-1>", lambda e, _eid=eid: self.play_episode_by_id(_eid))
                    self.text.tag_config(tag, foreground="blue")
                else:
                    self.text.tag_config(tag, foreground="gray")
            return

        url = f"https://{self.base_url}/api/{self.api_version}/anime/releases/{urllib.parse.quote(release_identity)}"
        data = self._get_json(url)
        if not data:
            self.text.insert(tk.END, "\nЭпизоды: не удалось получить данные\n")
            return

        # ожидаем массив эпизодов в одном из полей
        episodes = data.get("episodes") or data.get("data", {}).get("episodes") or []
        if not isinstance(episodes, list) or not episodes:
            # fallback на старое поле player.list (если вдруг отдадут старую схему)
            player_list = (data.get("player") or {}).get("list") or {}
            if isinstance(player_list, dict):
                episodes = []
                for ep in player_list.values():
                    # создадим «псевдоэпизод» без id, но с номером
                    episodes.append({
                        "id": ep.get("id") or ep.get("episodeId"),
                        "number": int(ep.get("ordinal") or 0),
                        "name": ep.get("name") or ""
                    })

        if not episodes:
            self.text.insert(tk.END, "\nЭпизоды: не найдены\n")
            return

        self.text.insert(tk.END, "\nЭпизоды:\n")
        for ep in episodes:
            eid = ep.get("id") or ep.get("episodeId") or ep.get("releaseEpisodeId")
            num = int(ep.get("ordinal") or 0)
            nm = ep.get("name") or ep.get("title") or ""
            line = f"• Серия {num}"
            if nm:
                line += f": {nm}"
            line += " — "

            # добавляем кликабельный «Смотреть»
            tag = f"hyperlink_play_ep_{eid or num}"
            start = self.text.index(tk.END)
            self.text.insert(tk.END, line)
            self.text.insert(tk.END, "Смотреть", (tag,))
            self.text.insert(tk.END, "\n")
            if eid:
                # биндим прямой вызов play_episode_by_id, без discovered_links
                self.text.tag_bind(tag, "<Button-1>", lambda e, _eid=eid: self.play_episode_by_id(_eid))
                self.text.tag_config(tag, foreground="blue")
            else:
                # нет episodeId — нечего дергать
                self.text.tag_config(tag, foreground="gray")

    def _fetch_and_render_torrents(self, release_identity: str):
        """Догружаем /anime/releases/{id|alias}, рисуем торрент-ссылки под текущим курсором."""
        url = f"https://{self.base_url}/api/{self.api_version}/anime/releases/{urllib.parse.quote(release_identity)}"
        data = self._get_json(url)
        if not data:
            self.text.insert(tk.END, " (ошибка загрузки)\n")
            return
        a = self._adapt_release(data)
        torrents = (a.get("torrents") or {}).get("list") or []
        if not torrents:
            self.text.insert(tk.END, " (торрентов нет)\n")
            return
        self.text.insert(tk.END, "\n")
        for torrent in torrents:
            url = torrent.get("url") or torrent.get("magnet")
            quality = (torrent.get("quality") or {}).get("string") or "Качество не указано"
            if url:
                start = self.text.index(tk.END)
                self.text.insert(tk.END, f"Скачать ({quality})", ("hyperlink_torrents", len(self.discovered_links)))
                end = self.text.index(tk.END)
                self.text.insert(end, "\n")
                self.text.tag_bind("hyperlink_torrents", "<Button-1>", self.on_link_click)
                self.discovered_links.append(url)
                self.text.tag_add("hyperlink_torrents", start, end)
                self.text.tag_config("hyperlink_torrents", foreground="blue")

    def _normalize_stream_url(self, url: str) -> str:
        """
        Режем параметры у http(s)-ссылок: убираем ?query и #fragment.
        magnet и локальные пути не трогаем.
        """
        if not url or url.startswith("magnet:?"):
            return url
        if url.startswith("http://") or url.startswith("https://"):
            s = urlsplit(url)
            return urlunsplit((s.scheme, s.netloc, s.path, "", ""))  # без query и fragment
        return url

    def play_episode_by_id(self, episode_id: str):
        """
        Тянем /anime/releases/episodes/{id}, выбираем hls по качеству и сразу запускаем плеер.
        """
        try:
            url = f"https://{self.base_url}/api/{self.api_version}/anime/releases/episodes/{episode_id}"
            payload = self._get_json(url)
            if not payload:
                self.log_message(f"Episode {episode_id}: empty payload")
                return

            hls = self._flatten_hls(payload)
            if not hls:
                self.log_message(f"Episode {episode_id}: HLS not found")
                print("HLS не найдено в ответе эпизода")
                return

            q = self.quality_var.get()
            m3u8 = hls.get(q) or hls.get("hls_1080") or hls.get("hls_720") or hls.get("hls_480")
            if not m3u8:
                print("Для эпизода не нашлось подходящего качества")
                return

            if not (m3u8.startswith("http://") or m3u8.startswith("https://")):
                m3u8 = "https://" + self.stream_video_url + m3u8

            m3u8 = self._normalize_stream_url(m3u8)

            try:
                if m3u8 not in self.discovered_links:
                    self.discovered_links.append(m3u8)
            except Exception:
                pass

            vlc_path = self.video_player_path
            subprocess.Popen([vlc_path, m3u8])
            self.log_message(f"Play episode {episode_id} -> {m3u8}")
        except Exception as e:
            self.log_message(f"play_episode_by_id error: {e}")
            print(f"Ошибка воспроизведения эпизода: {e}")

    def get_schedule_now(self):
        url = f"https://{self.base_url}/api/{self.api_version}/anime/schedule/now"
        self._fetch_to_temp_and_render(url, self.display_schedule_now)

    def get_schedule_week(self):
        url = f"https://{self.base_url}/api/{self.api_version}/anime/schedule/week"
        self._fetch_to_temp_and_render(url, self.display_schedule_week)

    def _fetch_and_show_schedule(self, api_url: str, mode: str):
        start_time = time.time()
        response = requests.get(api_url)
        end_time = time.time()
        utils_folder = 'temp'
        os.makedirs(utils_folder, exist_ok=True)
        utils_json = os.path.join(utils_folder, 'response.json')

        if response.status_code == 200:
            with open(utils_json, 'w', encoding='utf-8') as file:
                file.write(response.text)
            # разный рендер в зависимости от структуры
            if mode == "now":
                self.display_schedule_now()
            else:
                self.display_schedule_week()
            self.logger.debug(f"Fetched schedule ({mode}). URL: {api_url}, "
                              f"Time: {end_time - start_time:.2f}s, Size: {len(response.text)}")
        else:
            error_message = f"Error {response.status_code}: Unable to fetch schedule"
            self.log_message(error_message)
            print(error_message)

    def search_by_title(self):
        search_text = self.title_search_entry.get()
        if not search_text:
            print("Search text is empty.")
            return
        url = f"https://{self.base_url}/api/{self.api_version}/anime/releases/{urllib.parse.quote(search_text)}"
        self._fetch_to_temp_and_render(url, self.display_info)

    def random_title(self):
        url = f"https://{self.base_url}/api/{self.api_version}/anime/releases/random?limit=1"
        self._fetch_to_temp_and_render(url, self.display_info)

    def display_title_info(self, title, index, show_description=True):
        self.text.insert(tk.END, "---\n\n")

        # имена (старое и новое)
        names = title.get("names") or {}
        ru_name = names.get("ru") or "Название отсутствует"
        en_name = names.get("en") or names.get("alternative") or ""

        type_full_string = (title.get("type") or {}).get("full_string") or ""
        status = (title.get("status") or {}).get("string") or "Статус отсутствует"
        description = title.get("description") or ""
        genres = ", ".join(title.get("genres") or []) or "Жанры отсутствуют"
        year_str = str((title.get("season") or {}).get("year") or "" or "Год отсутствует")
        title_id = title.get("title_id") or ""
        code = title.get("code") or ""

        self.text.insert(tk.END, f"Название: {ru_name}\n")
        if en_name:
            self.text.insert(tk.END, f"Название: {en_name}\n\n")
        else:
            self.text.insert(tk.END, "\n")
        if type_full_string:
            self.text.insert(tk.END, type_full_string + "\n")
        self.text.insert(tk.END, f"Статус: {status}\n")
        if show_description and description:
            self.text.insert(tk.END, f"Описание: {description}\n")
        self.text.insert(tk.END, f"Жанры: {genres}\n")
        if year_str:
            self.text.insert(tk.END, f"Год: {year_str}\n")
        self.text.insert(tk.END, "---\n\n")

        # кликабельная ссылка на страницу релиза (если адаптер её вложил)
        page_url = title.get("_page_url")
        if page_url:
            link_id = f"title_link_{index}"
            self.text.insert(tk.END, "Открыть страницу тайтла", (f"hyperlink_title_{link_id}", page_url))
            self.text.insert(tk.END, "\n\n")
            self.text.tag_bind(f"hyperlink_title_{link_id}", "<Button-1>",
                               lambda event, en=code: self.on_title_click(event, en))

        self.get_poster(title)

        # Серии: в v1 прямых hls нет — не валимся, просто ничего не рисуем, если старого поля нет
        release_identity = self._release_identity(title)
        self._render_episodes_list(release_identity, title=title)

        self.text.insert(tk.END, "\n")

        # Ленивая подгрузка: для now/week/random где торрентов нет в ответе
        torrents_found = False
        if not torrents_found:
            release_identity = self._release_identity(title)  # alias или id
            if release_identity:
                tag = f"hyperlink_fetch_torrents_{release_identity}"
                self.text.insert(tk.END, "\nТорренты не найдены. ")
                self.text.insert(tk.END, "Загрузить торренты", (tag,))
                self.text.insert(tk.END, "\n\n")

                def _cb(ev, rid=release_identity):
                    self._fetch_and_render_torrents(rid)

                self.text.tag_bind(tag, "<Button-1>", _cb)
                self.text.tag_config(tag, foreground="blue")
            else:
                self.text.insert(tk.END, "\nТорренты не найдены\n")
        self.text.insert(tk.END, "\n")

    def display_schedule_now(self):
        try:
            self.clear_cache_file()
            data = self.read_json_data()  # уже {"list":[...]} благодаря адаптеру
            self.text.delete("1.0", tk.END)
            self.clear_poster()
            items = (data or {}).get("list") or []
            self.text.insert(tk.END, "Расписание на сегодня/завтра/вчера:\n\n")
            for i, title in enumerate(items):
                self.display_title_info(title, i, show_description=False)
        except Exception as e:
            msg = f"An error occurred while displaying NOW schedule: {e}"
            self.log_message(msg)
            self.text.delete("1.0", tk.END)
            self.text.insert(tk.END, msg)

    def display_schedule_week(self):
        try:
            self.clear_cache_file()
            data = self.read_json_data()  # уже {"list":[...]}
            self.text.delete("1.0", tk.END)
            self.clear_poster()
            items = (data or {}).get("list") or []
            if not items:
                self.text.insert(tk.END, "Пусто")
                return
            self.text.insert(tk.END, "Расписание на неделю:\n\n")
            for i, title in enumerate(items):
                self.display_title_info(title, i, show_description=False)
        except Exception as e:
            msg = f"An error occurred while displaying WEEK schedule: {e}"
            self.log_message(msg)
            self.text.delete("1.0", tk.END)
            self.text.insert(tk.END, msg)

    def display_info(self):
        try:
            self.clear_cache_file()
            self.title_search_entry.delete(0, tk.END)
            data = self.read_json_data()
            self.text.delete("1.0", tk.END)
            if data is not None:
                selected_quality = self.quality_var.get()
                self.discovered_links = []

                for i, item in enumerate(data["list"]):
                    self.display_title_info(item, i)
        except Exception as e:
            error_message = f"An error occurred while displaying information: {str(e)}"
            self.log_message(error_message)
            print(error_message)

    def update_quality_and_refresh(self, event=None):
        selected_quality = self.quality_var.get()
        data = self.read_json_data()
        if data:
            if "list" in data and isinstance(data["list"], list) and len(data["list"]) > 0:
                self.display_info()
            else:
                error_message = "No valid data available. Please fetch data first."
                self.log_message(error_message)
                print(error_message)
        else:
            error_message = "No data available. Please fetch data first."
            self.log_message(error_message)
            print(error_message)

    def on_title_click(self, event, en_name):
        try:
            self.title_search_entry.delete(0, tk.END)
            self.title_search_entry.insert(0, en_name)
            self.search_by_title()
        except Exception as e:
            error_message = f"An error occurred while clicking on title: {str(e)}"
            self.log_message(error_message)
            print(error_message)


if __name__ == "__main__":
    window = tk.Tk()
    app = AnimePlayerAppVer1(window)
    window.mainloop()
