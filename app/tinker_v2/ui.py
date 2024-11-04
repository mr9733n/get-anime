# ui.py
import asyncio
import json
from datetime import datetime
import re
import subprocess
import logging
import logging.config
from io import BytesIO

from PIL import ImageTk, Image
import tkinter as tk
from tkinter import ttk
from tkinter.ttk import Combobox
import threading
from queue import Queue

from PyQt5.QtCore import QTimer


class FrontManager:
    def __init__(self, app):
        self.next_poster_button = None
        self.poster_label = None
        self.text = None
        self.refresh_button = None
        self.play_button = None
        self.random_button = None
        self.save_button = None
        self.title_search_entry = None
        self.display_button = None
        self.title_search_label = None
        self.pre = "https://"
        self.days_of_week = None
        self.day_buttons = None
        self.logger = logging.getLogger(__name__)
        self.app = app
        self.init_ui()

    def init_ui(self):
        self.app.window.title("Anime Player v2")
        self.app.window.geometry("1120x760")
        self.app.window.grid_rowconfigure(2, weight=1)
        self.app.window.grid_columnconfigure(0, weight=1)
        self.setup_widgets()

    def setup_widgets(self):
        # Создание кнопок дней недели
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
            button = ttk.Button(self.app.window, text=day, command=lambda i=i: self.get_schedule(i + 1))
            button.grid(row=1, column=3 + i, sticky="ew")
            self.day_buttons.append(button)

        # Поле для поиска по названию
        self.title_search_label = ttk.Label(self.app.window, text="Поиск по названию:")
        self.title_search_label.grid(row=0, column=0, columnspan=3)
        self.title_search_entry = ttk.Entry(self.app.window)
        self.title_search_entry.grid(row=0, column=3, columnspan=7, sticky="ew")

        # Кнопки управления
        self.display_button = ttk.Button(self.app.window, text="Отобразить информацию", command=self.get_search_by_title)
        self.display_button.grid(row=1, column=0, sticky="ew")
        self.random_button = ttk.Button(self.app.window, text="Random", command=self.get_random_title)
        self.random_button.grid(row=1, column=1, sticky="ew")
        self.save_button = ttk.Button(self.app.window, text="Сохранить плейлист", command=self.app.save_playlist_wrapper)
        self.save_button.grid(row=4, column=0, columnspan=3, sticky="ew")
        self.play_button = ttk.Button(self.app.window, text="Воспроизвести плейлист", command=self.app.play_playlist_wrapper)
        self.play_button.grid(row=5, column=0, columnspan=3, sticky="ew")

        # Выбор качества видео
        self.quality_label = ttk.Label(self.app.window, text="Качество:")
        self.quality_label.grid(row=3, column=8)
        self.quality_var = tk.StringVar()
        self.quality_var.set("fhd")
        quality_options = ["fhd", "hd", "sd"]
        self.quality_dropdown = Combobox(self.app.window, textvariable=self.quality_var, values=quality_options)
        self.quality_dropdown.grid(row=3, column=9)
        self.quality_dropdown.state(['readonly'])
        self.refresh_button = ttk.Button(self.app.window, text="Обновить", command=self.update_quality_and_refresh)
        self.refresh_button.grid(row=4, column=9, sticky="ew")

        # Настройка столбцов
        self.app.window.grid_columnconfigure(1, weight=3)

        # Поле для отображения информации
        self.text = tk.Text(self.app.window, wrap=tk.WORD, cursor="hand2")
        self.text.grid(row=2, column=3, columnspan=7, sticky="nsew")
        self.text.tag_configure("hyperlink", foreground="blue")

        # Метка для постера
        self.poster_label = tk.Label(self.app.window)
        self.poster_label.grid(row=2, column=0, columnspan=3)
        self.next_poster_button = ttk.Button(self.app.window, text="Следующий постер", command=self.change_poster)
        self.next_poster_button.grid(row=3, column=0, columnspan=3, sticky="ew")

    def on_link_click(self, event, title_name=None, torrent_id=None):
        try:
            tag_names = event.widget.tag_names(tk.CURRENT)
            match = re.search(r'(\d+)', tag_names[0])
            if not match:
                self.logger.error(f"Could not extract index from tag: {tag_names[0]}")
                return

            link_index = int(match.group(1))
            if link_index < 0 or link_index >= len(self.app.discovered_links):
                self.logger.error(f"Link index {link_index} out of range.")
                return

            link = self.app.discovered_links[link_index]
            if link.endswith('.m3u8'):
                video_plyer_path = self.app.video_player_path
                open_link = self.pre + self.app.stream_video_url + link
                media_player_command = [video_plyer_path, open_link]
                subprocess.Popen(media_player_command)
                self.logger.info(f"Playing video link: {open_link}")
            elif '/torrent/download.php' in link:
                self.app.save_torrent_wrapper(link, title_name, torrent_id)
            else:
                self.logger.error(f"Unknown link type: {link}")

        except Exception as e:
            error_message = f"An error occurred while processing the link: {str(e)}"
            self.logger.error(error_message)

    def get_schedule(self, day):
        day -= 1
        data = self.app.api_client.get_schedule(day)
        if 'error' in data:
            self.logger.error(data['error'])
            return
        self.app.poster_manager.clear_cache_and_memory()
        self.display_schedule(data)
        self.app.current_data = data

    def display_poster(self, poster_image, title_id=None):
        try:
            self.app.window.after(20000, self._display_poster_in_ui, poster_image)
        except Exception as e:
            self.logger.error(f"An error occurred while displaying the poster: {e}")

    def _display_poster_in_ui(self, poster_image):
        try:
            # Ваш код для отображения постера
            self.poster_label.config(image=poster_image)
            self.poster_label.image = poster_image
        except Exception as e:
            self.logger.error(f"An error occurred while displaying the poster in UI: {e}")

    def clear_poster(self):
        self.poster_label.configure(image='')
        self.poster_label.image = None

    def change_poster(self):
        next_poster = self.app.poster_manager.next_poster()
        if next_poster:
            poster_image, title_id = next_poster
            self.display_poster(poster_image, title_id)
        else:
            self.logger.warning("No more posters to display.")

    def get_search_by_title(self):
        search_text = self.title_search_entry.get()
        if search_text:
            data = self.app.api_client.get_search_by_title(search_text)
            if 'error' in data:
                self.logger.error(data['error'])
                return
            self.app.poster_manager.clear_cache_and_memory()
            self.display_info(data)
            self.app.current_data = data
        else:
            self.logger.error("Search text is empty.")

    def get_random_title(self):
        data = self.app.api_client.get_random_title()
        if 'error' in data:
            self.logger.error(data['error'])
            return
        self.app.poster_manager.clear_cache_and_memory()
        self.display_info(data)
        self.app.current_data = data

    def get_poster(self, title_data):
        try:
            # Construct the poster URL
            poster_url = self.pre + self.app.base_url + title_data["posters"]["small"]["url"]

            # Standardize the poster URL
            standardized_url = self.app.standardize_url(poster_url)
            self.logger.debug(f"Standardize the poster URL: {standardized_url}")

            # Check if the standardized URL is already in the cached poster links
            if standardized_url in map(self.app.standardize_url, self.app.poster_manager.poster_links):
                self.logger.debug(f"Poster URL already cached: {standardized_url}. Skipping fetch.")
                return None


            return standardized_url

        except Exception as e:
            error_message = f"An error occurred while getting the poster: {str(e)}"
            self.logger.error(error_message)
            return None

    def display_title_info(self, title, index, show_description=True):
        """
        Вспомогательная функция для отображения информации о тайтле.
        """
        # Проверка типа title
        if not isinstance(title, dict):
            self.logger.error(f"Invalid type for title. Expected dict, got {type(title)}")
            return

        names = title.get("names", {})
        if not isinstance(names, dict):
            names = {}

        self.text.insert(tk.END, "---\n\n")
        ru_name = names.get("ru", "Название отсутствует")
        en_name = names.get("en", "Название отсутствует")
        announce = str(title.get("announce", "Состояние отсутствует"))

        type_info = title.get('type', {})
        if not isinstance(type_info, dict):
            type_info = {}
        type_full_string = type_info.get('full_string', "Тип отсутствует")

        status = title["status"].get("string", "Статус отсутствует")
        description = title.get("description", "Описание отсутствует")
        genres = ", ".join(title.get("genres", ["Жанры отсутствуют"]))
        season_info = title.get("season", {})
        year_str = str(season_info.get("year", "Год отсутствует"))

        self.text.insert(tk.END, "Название: " + ru_name + "\n")
        self.text.insert(tk.END, "Название: " + en_name + "\n\n")
        self.app.title_names.append(en_name)
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

        poster_links = []
        if "posters" in title and title.get("posters", {}).get("small"):
            poster_url = self.get_poster(title)
            if poster_url:
                poster_links.append((title['id'], poster_url))
                self.logger.debug(f"Poster url: {poster_url}")

        if poster_links:


        # Add all collected poster links at once
            self.app.poster_manager.write_poster_links(poster_links)

        episodes_found = False
        selected_quality = self.quality_var.get()
        for index, episode in enumerate(title["player"]["list"].values()):
            if not isinstance(episode, dict):
                self.logger.error(f"Invalid type for episode. Expected dict, got {type(episode)}")
                continue

            if "hls" in episode:
                hls = episode["hls"]
                if selected_quality in hls:
                    url = hls[selected_quality]
                    if url is not None:
                        self.text.insert(tk.END, f"Серия {episode['episode']}: ")
                        hyperlink_start = self.text.index(tk.END)
                        tag_name = f"hyperlink_episodes_{len(self.app.discovered_links)}"
                        self.text.insert(hyperlink_start, "Смотреть", (tag_name,))
                        hyperlink_end = self.text.index(tk.END)
                        self.text.insert(hyperlink_end, "\n")
                        self.text.tag_bind(tag_name, "<Button-1>", self.on_link_click)
                        self.app.discovered_links.append(url)
                        self.text.tag_add(tag_name, hyperlink_start, hyperlink_end)
                        self.text.tag_config(tag_name, foreground="blue")
                        episodes_found = True
                        # Сохранение данных в базу данных через DatabaseManager
                        try:
                                if isinstance(episode, dict):
                                    episode_data = {
                                        'episode_id': episode.get('id'),
                                        'title_id': title.get('id'),
                                        'episode_number': episode.get('episode'),
                                        'name': episode.get('name', f'Серия {episode.get("episode")}'),
                                        'uuid': episode.get('uuid'),
                                        'created_timestamp': episode.get('created_timestamp'),
                                        'hls_fhd': episode.get('hls', {}).get('fhd'),
                                        'hls_hd': episode.get('hls', {}).get('hd'),
                                        'hls_sd': episode.get('hls', {}).get('sd'),
                                        'preview_path': episode.get('preview'),
                                        'skips_opening': json.dumps(episode.get('skips', {}).get('opening', [])),
                                        'skips_ending': json.dumps(episode.get('skips', {}).get('ending', []))
                                    }
                                    self.app.db_manager.save_episode(episode_data)

                        except Exception as e:
                            self.logger.error(f"Failed to save episode to database: {e}")
        if not episodes_found:
            self.text.insert(tk.END, "\nСерии не найдены! Выберите другое качество или исправьте запрос поиска.\n")
        self.text.insert(tk.END, "\n")

        torrents_found = False
        if "torrents" in title and "list" in title["torrents"]:
            for torrent in title["torrents"]["list"]:
                url = torrent.get("url")
                quality = torrent["quality"].get("string", "Качество не указано")
                torrent_id = torrent.get("torrent_id")
                if url:
                    hyperlink_start = self.text.index(tk.END)
                    link_index = len(self.app.discovered_links)
                    self.text.insert(tk.END, f"Скачать ({quality})", (f"hyperlink_torrents_{link_index}",))
                    hyperlink_end = self.text.index(tk.END)
                    self.text.insert(hyperlink_end, "\n")
                    self.app.discovered_links.append(url)

                    self.text.tag_bind(f"hyperlink_torrents_{link_index}", "<Button-1>",
                                       lambda e, tn=en_name, tid=torrent_id: self.on_link_click(e, tn, tid))
                    self.text.tag_add(f"hyperlink_torrents_{link_index}", hyperlink_start, hyperlink_end)
                    self.text.tag_config(f"hyperlink_torrents_{link_index}", foreground="blue")
                    torrents_found = True

                    # Сохранение данных о торренте в базу данных через DatabaseManager
                    try:
                        torrent_data = {
                            'torrent_id': torrent.get('torrent_id'),
                            'title_id': title.get('id'),
                            'episodes_range': torrent.get('episodes', {}).get('string', 'Неизвестный диапазон'),
                            'quality': torrent.get('quality', {}).get('string', 'Качество не указано'),
                            'quality_type': torrent.get('quality', {}).get('type'),
                            'resolution': torrent.get('quality', {}).get('resolution'),
                            'encoder': torrent.get('quality', {}).get('encoder'),
                            'leechers': torrent.get('leechers'),
                            'seeders': torrent.get('seeders'),
                            'downloads': torrent.get('downloads'),
                            'total_size': torrent.get('total_size'),
                            'size_string': torrent.get('size_string'),
                            'url': torrent.get('url'),
                            'magnet_link': torrent.get('magnet'),
                            'uploaded_timestamp': torrent.get('uploaded_timestamp'),
                            'hash': torrent.get('hash'),
                            'torrent_metadata': torrent.get('metadata'),
                            'raw_base64_file': torrent.get('raw_base64_file')
                        }
                        self.app.db_manager.save_torrent(torrent_data)
                    except Exception as e:
                        self.logger.error(f"Ошибка при сохранении торрента в базе данных: {e}")

        if not torrents_found:
            self.text.insert(tk.END, "\nТорренты не найдены\n")
        self.text.insert(tk.END, "\n")
        # self.app.get_poster(title)

        # Сохранение данных в базу данных через DatabaseManager
        try:
            # Сохранение тайтла
            if isinstance(title, dict):
                title_data = {
                    'title_id': title.get('id'),
                    'code': title.get('code'),
                    'name_ru': title.get('names', {}).get('ru'),
                    'name_en': title.get('names', {}).get('en'),
                    'alternative_name': title.get('names', {}).get('alternative'),
                    'franchises': json.dumps(title.get('franchises', [])),
                    'announce': title.get('announce'),
                    'status_string': title.get('status', {}).get('string'),
                    'status_code': title.get('status', {}).get('code'),
                    'poster_path_small': title.get('posters', {}).get('small', {}).get('url'),
                    'poster_path_medium': title.get('posters', {}).get('medium', {}).get('url'),
                    'poster_path_original': title.get('posters', {}).get('original', {}).get('url'),
                    'updated': title.get('updated'),
                    'last_change': title.get('last_change'),
                    'type_full_string': title.get('type', {}).get('full_string'),
                    'type_code': title.get('type', {}).get('code'),
                    'type_string': title.get('type', {}).get('string'),
                    'type_episodes': title.get('type', {}).get('episodes'),
                    'type_length': title.get('type', {}).get('length'),
                    'genres': json.dumps(title.get('genres', [])),
                    'team_voice': json.dumps(title.get('team', {}).get('voice', [])),
                    'team_translator': json.dumps(title.get('team', {}).get('translator', [])),
                    'team_timing': json.dumps(title.get('team', {}).get('timing', [])),
                    'season_string': title.get('season', {}).get('string'),
                    'season_code': title.get('season', {}).get('code'),
                    'season_year': title.get('season', {}).get('year'),
                    'season_week_day': title.get('season', {}).get('week_day'),
                    'description': title.get('description'),
                    'in_favorites': title.get('in_favorites'),
                    'blocked_copyrights': title.get('blocked', {}).get('copyrights'),
                    'blocked_geoip': title.get('blocked', {}).get('geoip'),
                    'blocked_geoip_list': json.dumps(title.get('blocked', {}).get('geoip_list', [])),
                    'last_updated': datetime.utcnow()  # Использование метода utcnow()
                }

                self.app.db_manager.save_title(title_data)
        except Exception as e:
            self.logger.error(f"Failed to save title to database: {e}")

    def display_schedule(self, data):
        try:
            self.text.delete("1.0", tk.END)
            if data is not None:
                for day_info in data:
                    day = day_info.get("day")
                    title_list = day_info.get("list")
                    for title in title_list:
                        title_id = title.get('id')
                        if title_id:
                            self.app.db_manager.save_schedule(day, title_id)
                    day_word = self.days_of_week[day]
                    self.text.insert(tk.END, f"День недели: {day_word}\n\n")
                    for i, title in enumerate(title_list):
                        self.display_title_info(title, i, show_description=False)
        except Exception as e:
            error_message = f"An error occurred while displaying the schedule: {str(e)}"
            self.logger.error(error_message)
            self.text.delete("1.0", tk.END)
            self.text.insert(tk.END, error_message)

    def display_info(self, data):
        try:
            self.title_search_entry.delete(0, tk.END)
            self.text.delete("1.0", tk.END)
            if data is not None:
                self.app.discovered_links = []
                if "list" in data and isinstance(data["list"], list):
                    titles = data["list"]
                else:
                    titles = [data] if isinstance(data, dict) else []
                for i, item in enumerate(titles):
                    self.display_title_info(item, i)
        except Exception as e:
            error_message = f"An error occurred while displaying information: {str(e)}"
            self.logger.error(error_message)

    def update_quality_and_refresh(self, event=None):
        selected_quality = self.quality_var.get()
        data = self.app.current_data

        if not data:
            error_message = "No data available. Please fetch data first."
            self.logger.error(error_message)
            return

        # Handling multiple potential data structures
        if isinstance(data, dict):
            # Check if it's a schedule data structure
            if "day" in data and "list" in data and isinstance(data["list"], list):
                self.logger.debug("Detected schedule data structure.")
                self.display_schedule([data])  # Wrap in a list to match expected input

            # Check if it's the general information structure
            elif "list" in data and isinstance(data["list"], list):
                self.logger.debug("Using cached general information data.")
                self.display_info(data)

            else:
                error_message = "No valid data format detected. Please fetch data again."
                self.logger.error(error_message)
        elif isinstance(data, list):
            # Assume list structure corresponds to schedule data
            self.logger.debug("Detected list-based schedule data structure.")
            self.display_schedule(data)
        else:
            error_message = "Unsupported data format. Please fetch data first."
            self.logger.error(error_message)

    def on_title_click(self, event, en_name):
        try:
            self.title_search_entry.delete(0, tk.END)
            self.title_search_entry.insert(0, en_name)
            self.get_search_by_title()
        except Exception as e:
            error_message = f"An error occurred while clicking on title: {str(e)}"
            self.logger.error(error_message)
