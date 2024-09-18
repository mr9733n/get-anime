# ui.py
from operator import index
import re
import subprocess
import logging
import logging.config
from PIL import ImageTk
import tkinter as tk
from tkinter import ttk
from tkinter.ttk import Combobox

class FrontManager:
    def __init__(self, app):
        self.logger = logging.getLogger(__name__)
        self.app = app
        self.init_ui()

    def init_ui(self):
        self.app.window.title("Anime Player")
        self.app.window.geometry("1200x700")
        self.app.window.grid_rowconfigure(2, weight=1)
        self.app.window.grid_columnconfigure(0, weight=1)
        self.setup_widgets()
        self.pre = "https://"

    def setup_widgets(self):
        self.days_of_week = {
            0: "Понедельник",
            1: "Вторник",
            2: "Среда",
            3: "Четверг",
            4: "Пятница",
            5: "Суббота",
            6: "Воскресенье"
        }
        self.day_buttons = []
        for i in range(7):
            day_name = self.days_of_week[i]
            button = ttk.Button(self.app.window, text=day_name, command=lambda i=i: self.app.get_schedule(i))
            button.grid(row=1, column=3 + i, sticky="ew")
            self.day_buttons.append(button)

        # Поле для поиска по названию
        self.title_search_label = ttk.Label(self.app.window, text="Поиск по названию:")
        self.title_search_label.grid(row=0, column=0, columnspan=3)
        self.title_search_entry = ttk.Entry(self.app.window)
        self.title_search_entry.grid(row=0, column=3, columnspan=7, sticky="ew")

        # Кнопки управления
        self.display_button = ttk.Button(self.app.window, text="Отобразить информацию", command=self.app.get_search_by_title)
        self.display_button.grid(row=1, column=0, sticky="ew")
        self.random_button = ttk.Button(self.app.window, text="Random", command=self.app.get_random_title)
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
        self.refresh_button = ttk.Button(self.app.window, text="Обновить", command=self.app.update_quality_and_refresh)
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

    def display_poster(self, poster_image):
        try:
            poster_photo = ImageTk.PhotoImage(poster_image)
            self.poster_label.configure(image=poster_photo)
            self.poster_label.image = poster_photo  # Сохраняем ссылку на изображение
        except Exception as e:
            error_message = f"An error occurred while displaying the poster: {str(e)}"
            self.logger.error(error_message)

    def change_poster(self):
        poster_image = self.app.poster_manager.get_next_poster()
        if poster_image:
            self.display_poster(poster_image)
        else:
            self.logger.warning("No poster to display.")
    
    def display_schedule(self, data):
        try:
            self.text.delete("1.0", tk.END)
            day_enum, items = self.app.get_items_data(data)  # Expecting day_enum and items
            print(f"Days: {day_enum}")
            print(f"Items count: {len(items)}")  # Check the count of items

            # Iterate over day_enum to print day names
            for day in day_enum:
                if day is not None and day in self.days_of_week:
                    day_name = self.days_of_week.get(day, "Unknown day")
                    print(f"Day {day}: {day_name}")

            self.text.insert(tk.END, f"День недели: {day_name}\n\n")

            # Check if items exist and process them
            if items:
                for i, item in enumerate(items):  # Enumerate to get the index i
                    if isinstance(item, tuple) and len(item) == 2:  # Unpack if item is a tuple
                        item, _ = item  # Ignore the second value in the tuple
                    print(f"display_schedule: Item {i}: {item['id']}")  # Print item id

                    self.display_title_info(item, i, show_description=False)
            else:
                self.logger.error("No items found in schedule.")

        except Exception as e:
            error_message = f"An error occurred while displaying the schedule: {str(e)}"
            self.logger.error(error_message)
            self.text.delete("1.0", tk.END)
            self.text.insert(tk.END, error_message)

    def display_info(self, data):
        try:
            self.title_search_entry.delete(0, tk.END)
            self.text.delete("1.0", tk.END)
            self.app.discovered_links = []
            items = self.app.get_items_data(data)

            # Ensure item is a dictionary and has an "id" key

            print(f"display_info: Item ID: {items['id']}")
            if items is not None:
                for item, i in items:
                    if item is not None:        
                        self.display_title_info(item, i)

            if not items:
                self.logger.error("Failed to retrieve information data. Please check the input format.")

        except Exception as e:
            error_message = f"An error occurred while displaying information: {str(e)}"
            self.logger.error(error_message)
    
    def display_title_info(self, title, index, show_description=True):
        """
        Helper function to display information about a title.
        """
        print("display_title_info:", title["id"], index)
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
        print(ru_name, en_name)
        print(status, announce)
        print(season_info, year_str)
        print(description)
        print(type_full_string, genres)
        # Insert title information into the text widget
        self.text.insert(tk.END, f"Название: {ru_name}\n")
        self.text.insert(tk.END, f"Название: {en_name}\n\n")
        self.app.title_names.append(en_name)
        self.text.insert(tk.END, f"Анонс: {announce}\n")
        self.text.insert(tk.END, f"{type_full_string}\n")
        self.text.insert(tk.END, f"Статус: {status}\n")
        if show_description and description:
            self.text.insert(tk.END, f"Описание: {description}\n")
        self.text.insert(tk.END, f"Жанры: {genres}\n")
        self.text.insert(tk.END, f"Год: {year_str}\n")
        self.text.insert(tk.END, "---\n\n")

        # Create a hyperlink for opening the title's page
        link_id = f"title_link_{index}"
        print(link_id)
        self.text.insert(tk.END, "Открыть страницу тайтла", (f"hyperlink_title_{link_id}", en_name))
        self.text.insert(tk.END, "\n\n")
        self.text.tag_bind(f"hyperlink_title_{link_id}", "<Button-1>", lambda event, en=en_name: self.on_title_click(event, en))

        # Handle episode links
        episodes_found = False
        selected_quality = self.quality_var.get()
        print(title['id'], selected_quality)
    
        url, episode = self.app.get_links_data(title, selected_quality)
        if url:
            episode_number = episode.get('episode', 'Номер эпизода не указан')
            self.text.insert(tk.END, f"Серия {episode_number}: ")
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

        if not episodes_found:
            self.text.insert(tk.END, "\nСерии не найдены! Выберите другое качество или исправьте запрос поиска.\n")
        self.text.insert(tk.END, "\n")

        # Handle torrent links
        torrents_found = False
        link_index = len(self.app.discovered_links)
        url, quality, torrent_id = self.app.get_links_data(title)
        if url:
            self.text.insert(tk.END, f"Скачать ({quality})", (f"hyperlink_torrents_{link_index}",))
            hyperlink_start = self.text.index(tk.END)
            hyperlink_end = self.text.index(tk.END)
            self.text.insert(hyperlink_end, "\n")
            self.app.discovered_links.append(url)
            self.text.tag_bind(f"hyperlink_torrents_{link_index}", "<Button-1>",
                            lambda e, tn=en_name, tid=torrent_id: self.on_link_click(e, tn, tid))
            self.text.tag_add(f"hyperlink_torrents_{link_index}", hyperlink_start, hyperlink_end)
            self.text.tag_config(f"hyperlink_torrents_{link_index}", foreground="blue")
            torrents_found = True

        if not torrents_found:
            self.text.insert(tk.END, "\nТорренты не найдены\n")
        self.text.insert(tk.END, "\n")
    


    def on_title_click(self, event, en_name):
        try:
            self.title_search_entry.delete(0, tk.END)
            self.title_search_entry.insert(0, en_name)
            self.app.get_search_by_title()
        except Exception as e:
            error_message = f"An error occurred while clicking on title: {str(e)}"
            self.logger.error(error_message)
