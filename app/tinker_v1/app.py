import io
import tkinter as tk
from tkinter import ttk
import json
import subprocess
import os
import configparser
import requests
import atexit
from PIL import Image, ImageTk
import time
import logging
from logging.handlers import TimedRotatingFileHandler
import datetime
from tkinter.ttk import Combobox
import warnings

# Suppress urllib3 NotOpenSSLWarning
warnings.filterwarnings("ignore", category=UserWarning, module='urllib3')

# Suppress Tkinter deprecation warning
os.environ['TK_SILENCE_DEPRECATION'] = '1'


class ConfigManager:
    def __init__(self, config_file):
        self.config = configparser.ConfigParser()
        self.config.read(config_file)

    def get_setting(self, section, setting, default=None):
        return self.config[section].get(setting, default)


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
        self.window.title("Anime Player v1")
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
        self.stream_video_url = self.config_manager.get_setting('Settings', 'stream_video_url')
        self.base_url = self.config_manager.get_setting('Settings', 'base_url')
        self.api_version = self.config_manager.get_setting('Settings', 'api_version')
        self.video_player_path = self.config_manager.get_setting('Settings', 'video_player_path')
        self.torrent_client_path = self.config_manager.get_setting('Settings', 'torrent_client_path')

    def init_ui(self):
        self.days_of_week = [
            "Понедельник",
            "Вторник",
            "Среда",
            "Четверг",
            "Пятница",
            "Суббота",
            "Воскресенье"
        ]
        self.day_buttons = []
        for i, day in enumerate(self.days_of_week):
            button = ttk.Button(self.window, text=day, command=lambda i=i: self.get_schedule(i + 1))
            button.grid(row=1, column=3 + i, sticky="ew")
            self.day_buttons.append(button)
        # Create a label and entry for title search
        self.title_search_label = ttk.Label(self.window, text="Поиск по названию:")
        self.title_search_label.grid(row=0, column=0, columnspan=3)
        self.title_search_entry = ttk.Entry(self.window)
        self.title_search_entry.grid(row=0, column=3, columnspan=7, sticky="ew")
        # Create a button for displaying information1
        self.display_button = ttk.Button(self.window, text="Отобразить информацию", command=self.search_by_title)
        self.display_button.grid(row=1, column=0, sticky="ew")
        self.display_button = ttk.Button(self.window, text="Random", command=self.random_title)
        self.display_button.grid(row=1, column=1, sticky="ew")
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
            if not os.path.exists(utils_folder):
                os.makedirs(utils_folder)
                self.log_message(f"Created 'utils' folder.")
            utils_json = os.path.join(utils_folder, 'response.json')
            self.log_message(f"Attempting to read {utils_json}.")
            with open(utils_json, 'r', encoding='utf-8') as file:
                data = json.load(file)
            self.log_message(f"Successfully read data from {utils_json}.")
            return data
        except FileNotFoundError:
            self.log_message(f"File {utils_json} not found.")
            return None
        except json.JSONDecodeError as e:
            error_message = f"Error decoding JSON data from {utils_json}: {str(e)}"
            self.log_message(error_message)
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
        if data is not None:
            if "list" in data and isinstance(data["list"], list) and len(data["list"]) > 0:
                playlists_folder = 'playlists'
                if not os.path.exists(playlists_folder):
                    os.makedirs(playlists_folder)
                    self.log_message(f"Created 'playlists' folder.")
                self.playlist_name = os.path.join(playlists_folder, f"{data['list'][0]['code']}.m3u")
                self.log_message(f"Saving playlist to {self.playlist_name}.")
                try:
                    if self.playlist_name is not None:
                        with open(self.playlist_name, 'w') as file:
                            for url in self.discovered_links:
                                full_url = "https://" + self.stream_video_url + url
                                file.write(f"#EXTINF:-1,{url}\n{full_url}\n")
                        self.log_message(f"Playlist {self.playlist_name} saved successfully.")
                    else:
                        error_message = "Playlist name is not set."
                        self.log_message(error_message)
                        print(error_message)
                        return None
                    return self.playlist_name
                except Exception as e:
                    error_message = f"An error occurred while saving the playlist: {str(e)}"
                    self.log_message(error_message)
                    print(error_message)
                    return None
            else:
                error_message = "No valid data available. Please fetch data first."
                self.log_message(error_message)
                print(error_message)
        else:
            error_message = "No data available. Please fetch data first."
            self.log_message(error_message)
            print(error_message)

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
            # Получаем индекс ссылки, которая была кликнута
            link_index = int(event.widget.tag_names(tk.CURRENT)[1])
            link = self.discovered_links[link_index]

            # Проверяем тип ссылки и выполняем соответствующие действия
            if link.endswith('.m3u8'):
                # Если это видео-ссылка, воспроизводим через VLC
                vlc_path = self.video_player_path
                open_link = "https://" + self.stream_video_url + link
                media_player_command = [vlc_path, open_link]
                subprocess.Popen(media_player_command)
                self.log_message(f"Playing video link: {open_link}")
            elif '/torrent/download.php' in link:
                # Обработка торрент-ссылок
                self.handle_torrent_link(link)
            else:
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
                link = "https://anilibria.tv" + link

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
            response = requests.get(url)
            response.raise_for_status()  # Проверка на ошибки при скачивании
            torrent_path = os.path.join(save_path, os.path.basename(url))
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

            poster_url = "https://" + self.base_url + title_data["posters"]["small"]["url"]
            self.write_poster_links([poster_url])
            title_name = {title_data['names']['en']}
            self.show_poster(poster_url)
            self.logger.debug(f"Successfully GET poster for title '{title_name}'. URL: '{poster_url}' ")

        except requests.exceptions.RequestException as e:
            error_message = f"An error occurred while GET downloading the poster: {str(e)}"
            self.log_message(error_message)
            print(error_message)
        except Exception as e:
            error_message = f"An error occurred while GET processing the poster: {str(e)}"
            self.log_message(error_message)
            print(error_message)

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

    def get_schedule(self, day):
        day -= 1
        api_url = f"https://api.{self.base_url}/{self.api_version}/title/schedule?days={day}"
        start_time = time.time()
        response = requests.get(api_url)
        end_time = time.time()
        utils_folder = 'temp'
        if not os.path.exists(utils_folder):
            os.makedirs(utils_folder)
            self.log_message(f"Created '{utils_folder}' folder.")
        utils_json = os.path.join(utils_folder, 'response.json')
        if response.status_code == 200:
            with open(utils_json, 'w', encoding='utf-8') as file:
                file.write(response.text)
            self.display_schedule()
            num_items = len(response.text) if response.text else 0
            self.logger.debug(f"Successfully fetched schedule for day {day}. URL: {api_url}, "
                              f"Time taken: {end_time - start_time:.2f} seconds.")
        else:
            error_message = f"Error {response.status_code}: Unable to fetch schedule data from the API."
            if response.text:
                try:
                    error_data = json.loads(response.text)
                    if "error" in error_data:
                        error_message += f" Error message: {error_data['error']['message']}"
                except json.JSONDecodeError:
                    pass
            self.log_message(error_message)
            print(error_message)

    def search_by_title(self):
        search_text = self.title_search_entry.get()
        if search_text:
            api_url = f"https://api.{self.base_url}/{self.api_version}/title/search?search={search_text}"
            start_time = time.time()
            response = requests.get(api_url)
            end_time = time.time()
            utils_folder = 'temp'
            if not os.path.exists(utils_folder):
                os.makedirs(utils_folder)
                self.log_message(f"Created 'utils_folder' folder.")
            utils_json = os.path.join(utils_folder, 'response.json')
            if response.status_code == 200:
                with open(utils_json, 'w', encoding='utf-8') as file:
                    file.write(response.text)
                self.display_info()
                num_items = len(response.text) if response.text else 0
                self.logger.debug(f"Successfully fetched search results for '{search_text}'. URL: {api_url}, "
                                  f"Time taken: {end_time - start_time:.2f} seconds, "
                                  f"Response size: {num_items} bytes.")
            else:
                error_message = f"Error {response.status_code}: Unable to fetch data from the API."
                if response.text:
                    try:
                        error_data = json.loads(response.text)
                        if "error" in error_data:
                            error_message += f" Error message: {error_data['error']['message']}"
                    except json.JSONDecodeError:
                        pass
                self.log_message(error_message)
                print(error_message)
        else:
            print("Search text is empty.")

    def random_title(self):
        api_url = f"https://api.{self.base_url}/{self.api_version}/title/random"
        start_time = time.time()
        response = requests.get(api_url)
        end_time = time.time()
        utils_folder = 'temp'
        if not os.path.exists(utils_folder):
            os.makedirs(utils_folder)
            self.log_message(f"Created 'uutils_folder' folder.")
        utils_json = os.path.join(utils_folder, 'response.json')
        if response.status_code == 200:
            with open(utils_json, 'w', encoding='utf-8') as file:
                file.write(response.text)
            with open(utils_json, 'r', encoding='utf-8') as file:
                existing_data = json.load(file)
            new_data = {
                "list": [
                    existing_data
                ],
                "pagination": {
                    "pages": 6,
                    "current_page": 1,
                    "items_per_page": 5,
                    "total_items": 26
                }
            }
            with open(utils_json, 'w', encoding='utf-8') as file:
                json.dump(new_data, file, ensure_ascii=False, indent=4)
            self.display_info()
            num_items = len(response.text) if response.text else 0
            self.logger.debug(f"Successfully fetched random title. URL: {api_url}, "
                              f"Time taken: {end_time - start_time:.2f} seconds, "
                              f"Response size: {num_items} bytes.")
        else:
            error_message = f"Error {response.status_code}: Unable to fetch data from the API."
            if response.text:
                try:
                    error_data = json.loads(response.text)
                    if "error" in error_data:
                        error_message += f" Error message: {error_data['error']['message']}"
                except json.JSONDecodeError:
                    pass
            self.log_message(error_message)
            print(error_message)

    def display_title_info(self, title, index, show_description=True):
        """
        Вспомогательная функция для отображения информации о тайтле.
        """
        self.text.insert(tk.END, "---\n\n")
        ru_name = title["names"].get("ru", "Название отсутствует")
        en_name = title["names"].get("en", "Название отсутствует")
        announce = str(title.get("announce", "Состояние отсутствует"))
        type_full_string = str(title["type"].get("full_string", {}))
        status = title["status"].get("string", "Статус отсутствует")
        description = title.get("description", "Описание отсутствует")
        genres = ", ".join(title.get("genres", ["Жанры отсутствуют"]))
        season_info = title.get("season", {})
        year_str = str(season_info.get("year", "Год отсутствует"))

        self.text.insert(tk.END, "Название: " + ru_name + "\n")
        self.text.insert(tk.END, "Название: " + en_name + "\n\n")
        self.text.insert(tk.END, "Анонс: " + announce + "\n")
        self.text.insert(tk.END, type_full_string + "\n")
        self.text.insert(tk.END, "Статус: " + (status if status else "Статус отсутствует") + "\n")
        if show_description and description:
            self.text.insert(tk.END, "Описание: " + description + "\n")
        self.text.insert(tk.END, "Жанры: " + (genres if genres else "Жанры отсутствуют") + "\n")
        self.text.insert(tk.END, "Год: " + (year_str if year_str else "Год отсутствует") + "\n")
        self.text.insert(tk.END, "---\n\n")

        link_id = f"title_link_{index}"
        self.text.insert(tk.END, "Открыть страницу тайтла", (f"hyperlink_title_{link_id}", en_name))
        self.text.insert(tk.END, "\n\n")
        self.text.tag_bind(f"hyperlink_title_{link_id}", "<Button-1>",
                           lambda event, en=en_name: self.on_title_click(event, en))

        self.get_poster(title)

        # Обработка серий
        episodes_found = False
        selected_quality = self.quality_var.get()
        for episode in title["player"]["list"].values():
            if "hls" in episode:
                hls = episode["hls"]
                if selected_quality in hls:
                    url = hls[selected_quality]
                    if url is not None:
                        self.text.insert(tk.END, f"Серия {episode['episode']}: ")
                        hyperlink_start = self.text.index(tk.END)
                        self.text.insert(hyperlink_start, "Смотреть",
                                         ("hyperlink_episodes", len(self.discovered_links)))
                        hyperlink_end = self.text.index(tk.END)
                        self.text.insert(hyperlink_end, "\n")
                        self.text.tag_bind("hyperlink_episodes", "<Button-1>", self.on_link_click)
                        self.discovered_links.append(url)
                        self.text.tag_add("hyperlink_episodes", hyperlink_start, hyperlink_end)
                        self.text.tag_config("hyperlink_episodes", foreground="blue")
                        episodes_found = True
        if not episodes_found:
            self.text.insert(tk.END, "\nСерии не найдены! Выберите другое качество или исправьте запрос поиска.\n")
        self.text.insert(tk.END, "\n")

        # Обработка торрентов
        torrents_found = False
        if "torrents" in title and "list" in title["torrents"]:
            for torrent in title["torrents"]["list"]:
                url = torrent.get("url")
                quality = torrent["quality"].get("string", "Качество не указано")
                if url:
                    hyperlink_start = self.text.index(tk.END)
                    self.text.insert(tk.END, f"Скачать ({quality})", ("hyperlink_torrents", len(self.discovered_links)))
                    hyperlink_end = self.text.index(tk.END)
                    self.text.insert(hyperlink_end, "\n")
                    self.text.tag_bind("hyperlink_torrents", "<Button-1>", self.on_link_click)
                    self.discovered_links.append(url)
                    self.text.tag_add("hyperlink_torrents", hyperlink_start, hyperlink_end)
                    self.text.tag_config("hyperlink_torrents", foreground="blue")
                    torrents_found = True

        if not torrents_found:
            self.text.insert(tk.END, "\nТорренты не найдены\n")
        self.text.insert(tk.END, "\n")

    def display_schedule(self):
        try:
            self.clear_cache_file()
            data = self.read_json_data()
            self.text.delete("1.0", tk.END)
            self.clear_poster()
            if data is not None:
                for day_info in data:
                    day = day_info.get("day")
                    title_list = day_info.get("list")
                    day_word = self.days_of_week[day]
                    self.text.insert(tk.END, f"День недели: {day_word}\n\n")
                    for i, title in enumerate(title_list):
                        self.display_title_info(title, i, show_description=False)
        except Exception as e:
            error_message = f"An error occurred while displaying the schedule: {str(e)}"
            self.log_message(error_message)
            print(error_message)
            self.text.delete("1.0", tk.END)
            self.text.insert(tk.END, error_message)

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
