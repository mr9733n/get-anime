# gui/app.py
import re
import subprocess
import tkinter as tk
from tkinter import ttk
from tkinter.ttk import Combobox
import logging
import logging.config
from config_manager import ConfigManager
from api_client import APIClient
from utils.poster_manager import PosterManager
from utils.playlist_manager import PlaylistManager
from utils.torrent_manager import TorrentManager
from PIL import ImageTk


class AnimePlayerApp:
    def __init__(self, window):
        self.logger = logging.getLogger(__name__)
        self.logger.debug("Initializing AnimePlayerApp")
        self.window = window
        self.setup_window()
        self.cache_file_path = "poster_cache.txt"
        self.config_manager = ConfigManager('config.ini')
        self.load_config()
        self.torrent_manager = TorrentManager(
            torrent_save_path=self.torrent_save_path,
            torrent_client_path=self.torrent_client_path
        )

        self.logger.debug(f"Video Player Path: {self.video_player_path}")
        self.logger.debug(f"Torrent Client Path: {self.torrent_client_path}")
        self.api_client = APIClient(self.base_url, self.api_version, logger=self.logger)
        self.poster_manager = PosterManager()
        self.playlist_manager = PlaylistManager()
        self.poster_manager = PosterManager(display_callback=self.display_poster)
        self.title_names = []
        self.init_variables()
        self.init_ui()

    def load_config(self):
        self.stream_video_url = self.config_manager.get_setting('Settings', 'stream_video_url')
        self.base_url = self.config_manager.get_setting('Settings', 'base_url')
        self.api_version = self.config_manager.get_setting('Settings', 'api_version')
        self.video_player_path = self.config_manager.get_setting('Settings', 'video_player_path')
        self.torrent_client_path = self.config_manager.get_setting('Settings', 'torrent_client_path')
        self.torrent_save_path = "torrents/"

    def setup_window(self):
        self.window.title("AnimePlayerApp")
        self.window.geometry("1000x700")
        self.window.grid_rowconfigure(2, weight=1)
        self.window.grid_columnconfigure(0, weight=1)

    def init_variables(self):
        self.discovered_links = []
        self.current_link = None

    def init_ui(self):
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
            button = ttk.Button(self.window, text=day, command=lambda i=i: self.get_schedule(i + 1))
            button.grid(row=1, column=3 + i, sticky="ew")
            self.day_buttons.append(button)

        # Поле для поиска по названию
        self.title_search_label = ttk.Label(self.window, text="Поиск по названию:")
        self.title_search_label.grid(row=0, column=0, columnspan=3)
        self.title_search_entry = ttk.Entry(self.window)
        self.title_search_entry.grid(row=0, column=3, columnspan=7, sticky="ew")

        # Кнопки управления
        self.display_button = ttk.Button(self.window, text="Отобразить информацию", command=self.get_search_by_title)
        self.display_button.grid(row=1, column=0, sticky="ew")
        self.random_button = ttk.Button(self.window, text="Random", command=self.get_random_title)
        self.random_button.grid(row=1, column=1, sticky="ew")
        self.save_button = ttk.Button(self.window, text="Сохранить плейлист", command=self.save_playlist_wrapper)
        self.save_button.grid(row=4, column=0, columnspan=3, sticky="ew")
        self.play_button = ttk.Button(self.window, text="Воспроизвести плейлист", command=self.play_playlist_wrapper)
        self.play_button.grid(row=5, column=0, columnspan=3, sticky="ew")

        # Выбор качества видео
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

        # Настройка столбцов
        self.window.grid_columnconfigure(1, weight=3)

        # Поле для отображения информации
        self.text = tk.Text(self.window, wrap=tk.WORD, cursor="hand2")
        self.text.grid(row=2, column=3, columnspan=7, sticky="nsew")
        self.text.tag_configure("hyperlink", foreground="blue")

        # Метка для постера
        self.poster_label = tk.Label(self.window)
        self.poster_label.grid(row=2, column=0, columnspan=3)
        self.next_poster_button = ttk.Button(self.window, text="Следующий постер", command=self.change_poster)
        self.next_poster_button.grid(row=3, column=0, columnspan=3, sticky="ew")

    def on_link_click(self, event, title_name=None, torrent_id=None):
        try:
            tag_names = event.widget.tag_names(tk.CURRENT)
            match = re.search(r'(\d+)', tag_names[0])
            if not match:
                self.logger.error(f"Could not extract index from tag: {tag_names[0]}")
                return

            link_index = int(match.group(1))
            if link_index < 0 or link_index >= len(self.discovered_links):
                self.logger.error(f"Link index {link_index} out of range.")
                return

            link = self.discovered_links[link_index]
            if link.endswith('.m3u8'):
                video_plyer_path = self.video_player_path
                open_link = "https://" + self.stream_video_url + link
                media_player_command = [video_plyer_path, open_link]
                subprocess.Popen(media_player_command)
                self.logger.info(f"Playing video link: {open_link}")
            elif '/torrent/download.php' in link:
                self.save_torrent_wrapper(link, title_name, torrent_id)
            else:
                self.logger.error(f"Unknown link type: {link}")

        except Exception as e:
            error_message = f"An error occurred while processing the link: {str(e)}"
            self.logger.error(error_message)

    def get_schedule(self, day):
        day -= 1
        data = self.api_client.get_schedule(day)
        if 'error' in data:
            self.logger.error(data['error'])
            return
        self.poster_manager.clear_cache_and_memory()
        self.display_schedule(data)
        self.current_data = data

    def get_poster(self, title_data):
        try:
            # Clear the current poster displayed
            self.clear_poster()

            # Construct the poster URL
            poster_url = "https://" + self.base_url + title_data["posters"]["small"]["url"]

            # Save the poster link to the cache
            self.poster_manager.write_poster_links([poster_url])

        except Exception as e:
            error_message = f"An error occurred while getting the poster: {str(e)}"
            self.logger.error(error_message)
            print(error_message)

    def display_poster(self, poster_image):
        try:
            poster_photo = ImageTk.PhotoImage(poster_image)
            self.poster_label.configure(image=poster_photo)
            self.poster_label.image = poster_photo  # Сохраняем ссылку на изображение
        except Exception as e:
            error_message = f"An error occurred while displaying the poster: {str(e)}"
            self.logger.error(error_message)
            print(error_message)

    def clear_poster(self):
        self.poster_label.configure(image='')
        self.poster_label.image = None

    def change_poster(self):
        poster_image = self.poster_manager.get_next_poster()
        if poster_image:
            self.display_poster(poster_image)
        else:
            self.logger.warning("No poster to display.")

    def get_search_by_title(self):
        search_text = self.title_search_entry.get()
        if search_text:
            data = self.api_client.search_by_title(search_text)
            if 'error' in data:
                self.logger.error(data['error'])
                return
            self.poster_manager.clear_cache_and_memory()
            self.display_info(data)
            self.current_data = data  # Сохраняем данные
        else:
            self.logger.error("Search text is empty.")

    def get_random_title(self):
        data = self.api_client.get_random_title()
        if 'error' in data:
            self.logger.error(data['error'])
            return
        self.poster_manager.clear_cache_and_memory()
        self.display_info(data)
        self.current_data = data

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
        self.title_names.append(en_name)
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

        # Обработка серий
        episodes_found = False
        selected_quality = self.quality_var.get()
        for index, episode in enumerate(title["player"]["list"].values()):
            if "hls" in episode:
                hls = episode["hls"]
                if selected_quality in hls:
                    url = hls[selected_quality]
                    if url is not None:
                        self.text.insert(tk.END, f"Серия {episode['episode']}: ")
                        hyperlink_start = self.text.index(tk.END)
                        # Embed index in the tag name
                        tag_name = f"hyperlink_episodes_{len(self.discovered_links)}"
                        self.text.insert(hyperlink_start, "Смотреть", (tag_name,))
                        hyperlink_end = self.text.index(tk.END)
                        self.text.insert(hyperlink_end, "\n")
                        self.text.tag_bind(tag_name, "<Button-1>", self.on_link_click)
                        self.discovered_links.append(url)
                        self.text.tag_add(tag_name, hyperlink_start, hyperlink_end)
                        self.text.tag_config(tag_name, foreground="blue")
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
                torrent_id = torrent.get("torrent_id")
                if url:
                    hyperlink_start = self.text.index(tk.END)
                    link_index = len(self.discovered_links)
                    self.text.insert(tk.END, f"Скачать ({quality})", (f"hyperlink_torrents_{link_index}",))
                    hyperlink_end = self.text.index(tk.END)
                    self.text.insert(hyperlink_end, "\n")
                    self.discovered_links.append(url)

                    # Привязка клика с передачей названия и ID тайтла
                    self.text.tag_bind(f"hyperlink_torrents_{link_index}", "<Button-1>",
                                       lambda e, tn=en_name, tid=torrent_id: self.on_link_click(e, tn, tid))
                    self.text.tag_add(f"hyperlink_torrents_{link_index}", hyperlink_start, hyperlink_end)
                    self.text.tag_config(f"hyperlink_torrents_{link_index}", foreground="blue")
                    torrents_found = True

        if not torrents_found:
            self.text.insert(tk.END, "\nТорренты не найдены\n")
        self.text.insert(tk.END, "\n")

        self.get_poster(title)

    def display_schedule(self, data):
        try:

            self.text.delete("1.0", tk.END)
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
            self.logger.error(error_message)
            print(error_message)
            self.text.delete("1.0", tk.END)
            self.text.insert(tk.END, error_message)

    def display_info(self, data):
        try:

            self.title_search_entry.delete(0, tk.END)
            self.text.delete("1.0", tk.END)
            if data is not None:
                self.discovered_links = []
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
        # Предполагая, что у вас есть текущие данные, сохраненные в self.current_data
        data = self.current_data
        if data:
            if "list" in data and isinstance(data["list"], list) and len(data["list"]) > 0:
                self.display_info(data)
            else:
                error_message = "No valid data available. Please fetch data first."
                self.logger.error(error_message)
                print(error_message)
        else:
            error_message = "No data available. Please fetch data first."
            self.logger.error(error_message)
            print(error_message)

    def on_title_click(self, event, en_name):
        try:
            self.title_search_entry.delete(0, tk.END)
            self.title_search_entry.insert(0, en_name)
            self.get_search_by_title()
        except Exception as e:
            error_message = f"An error occurred while clicking on title: {str(e)}"
            self.logger.error(error_message)
            print(error_message)



    def save_playlist_wrapper(self):
        """
        Wrapper function to handle saving the playlist.
        Collects title names and links, and passes them to save_playlist.
        """
        # Call save_playlist with title names and discovered links
        if self.discovered_links:
            self.playlist_manager.save_playlist(self.title_names, self.discovered_links, self.stream_video_url)
        else:
            print("Нет доступных ссылок для сохранения в плейлист.")

    def play_playlist_wrapper(self):
        """
        Wrapper function to handle playing the playlist.
        Determines the file name and passes it to play_playlist.
        """
        if not self.title_names:
            print("Плейлист не найден, сохраните плейлист сначала.")
            return

        # Generate file name based on the title names
        file_name = "_".join(self.title_names)[:100] + ".m3u"
        video_player_path = self.video_player_path
        self.playlist_manager.play_playlist(file_name, video_player_path)

    def save_torrent_wrapper(self, link, title_name, torrent_id):
        """
        Wrapper function to handle saving the torrent.
        Collects title names and links, and passes them to save_torrent_file.
        """
        try:
            # Generate a file name for the torrent
            file_name = f"{title_name}_{torrent_id}.torrent"

            # Call the save_torrent_file method from TorrentManager
            self.torrent_manager.save_torrent_file(link, file_name)
        except Exception as e:
            error_message = f"Error in save_torrent_wrapper: {str(e)}"
            self.logger.error(error_message)
            print(error_message)

        pass