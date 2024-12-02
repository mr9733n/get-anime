import ast
import json
import logging
import logging.config
import os
import platform
import re
import subprocess
import sys
import base64
import datetime
from datetime import datetime, timezone

from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLineEdit, QLabel, QComboBox, QGridLayout, QScrollArea, QTextBrowser, QSizePolicy, QGraphicsDropShadowEffect,
    QMessageBox
)
from PyQt5.QtCore import Qt, QByteArray, QBuffer, QUrl, QTimer, QRunnable, QThreadPool, pyqtSlot, QObject, pyqtSignal
from PyQt5.QtGui import QPixmap

from core import database_manager
from core.database_manager import DatabaseManager
from app.qt.ui_manger import UIManager
from app.qt.layout_metadata import all_layout_metadata
from app.qt.ui_generator import UIGenerator
from app.qt.ui_s_generator import UISGenerator
from utils.config_manager import ConfigManager
from utils.api_client import APIClient
from utils.poster_manager import PosterManager
from utils.playlist_manager import PlaylistManager
from utils.torrent_manager import TorrentManager
from app.qt.app_helpers import TitleDisplayFactory, TitleDataFactory


APP_WIDTH = 1000
APP_HEIGHT = 800
APP_X_POS = 100
APP_Y_POS = 100


class AnimePlayerAppVer3(QWidget):
    add_title_browser_to_layout = pyqtSignal(QTextBrowser, int, int)

    def __init__(self, db_manager, version):
        super().__init__()
        self.day_of_week = None
        self.quality_dropdown = None
        self.logger = logging.getLogger(__name__)
        self.thread_pool = QThreadPool()  # Пул потоков для управления задачами
        self.thread_pool.setMaxThreadCount(4)

        self.playlist_filename = None
        self.current_data = None
        self.current_link = None
        self.poster_container = None
        self.scroll_area = None
        self.posters_layout = None
        self.title_search_entry = None
        self.current_titles = None
        self.selected_quality = None
        self.torrent_data = None

        self.discovered_links = []
        self.sanitized_titles = []
        self.title_names = []
        self.total_titles = []
        self.playlists = {}
        self.app_version = version
        self.logger.debug(f"Starting AnimePlayerApp Version {self.app_version}..")
        self.row_start = 0
        self.col_start = 0
        self.pre = "https://"
        self.config_manager = ConfigManager('config/config.ini')

        """Loads the configuration settings needed by the application."""
        # self.stream_video_url = self.config_manager.get_setting('Settings', 'stream_video_url')
        self.stream_video_url = None
        self.base_url = self.config_manager.get_setting('Settings', 'base_url')
        self.api_version = self.config_manager.get_setting('Settings', 'api_version')

        self.titles_batch_size = int(self.config_manager.get_setting('Settings', 'titles_batch_size'))
        self.titles_list_batch_size = int(self.config_manager.get_setting('Settings', 'titles_list_batch_size'))
        self.current_offset = int(self.config_manager.get_setting('Settings', 'current_offset'))
        self.num_columns = int(self.config_manager.get_setting('Settings', 'num_columns'))
        self.user_id = int(self.config_manager.get_setting('Settings', 'user_id'))

        self.torrent_save_path = "torrents/"  # Ensure this is set correctly
        self.video_player_path, self.torrent_client_path = self.setup_paths()

        # Initialize TorrentManager with the correct paths
        self.torrent_manager = TorrentManager(
            torrent_save_path=self.torrent_save_path,
            torrent_client_path=self.torrent_client_path
        )
        # Corrected debug logging of paths using setup values
        self.logger.debug(f"Video Player Path: {self.video_player_path}")
        self.logger.debug(f"Torrent Client Path: {self.torrent_client_path}")

        # Initialize other components
        self.api_client = APIClient(self.base_url, self.api_version)
        self.poster_manager = PosterManager()
        self.playlist_manager = PlaylistManager()
        self.db_manager = db_manager
        self.poster_manager = PosterManager(
            save_callback=self.db_manager.save_poster,
        )

        self.ui_generator = UIGenerator(self, self.db_manager)
        self.ui_s_generator = UISGenerator(self, self.db_manager)
        self.add_title_browser_to_layout.connect(self.on_add_title_browser_to_layout)
        self.ui_manager = UIManager(self)

        self.callbacks = self.generate_callbacks()
        days_of_week = ["MO", "TU", "WE", "TH", "FR", "SA", "SU"]
        for i, day in enumerate(days_of_week):
            self.callbacks[f"display_titles_for_day_{i}"] = lambda checked, i=i: self.display_titles_for_day(i)


        self.init_ui()

    @pyqtSlot(QTextBrowser, int, int)
    def on_add_title_browser_to_layout(self, title_browser, row, column):
        self.posters_layout.addWidget(title_browser, row, column)

    def setup_paths(self):
        """Sets up paths based on the current platform and returns them for use."""
        current_platform = platform.system()
        video_player_path = self.config_manager.get_video_player_path(current_platform)
        torrent_client_path = self.config_manager.get_torrent_client_path(current_platform)

        # Return paths to be used in the class
        return video_player_path, torrent_client_path

    def init_ui(self):
        self.setWindowTitle(f'Anime Player App {self.app_version}')
        self.setGeometry(APP_X_POS, APP_Y_POS, APP_WIDTH, APP_HEIGHT)

        # Основной вертикальный layout
        main_layout = QVBoxLayout()

        self.ui_manager.setup_main_layout(main_layout, all_layout_metadata, self.callbacks)
        self.setLayout(main_layout)

        # Сохранение ссылок на виджеты после их создания
        self.title_search_entry = self.ui_manager.parent_widgets.get("title_input")
        self.quality_dropdown = self.ui_manager.parent_widgets.get("quality_dropdown")

        # Load 4 titles on start from DB
        self.display_titles(start=True)

    def refresh_display(self):
        """Обработчик кнопки REFRESH, выполняющий обновление текущего экрана."""
        try:
            selected_quality = self.quality_dropdown.currentText()
            self.logger.debug(f"REFRESH нажат, выбранное качество: {selected_quality}")

            # Если данные не загружены, выполнить запрос и обновить
            if not self.total_titles:
                self.logger.info("Данные не были загружены ранее, запрашиваем заново.")
                self.update_quality_and_refresh()
                return

            # Очищаем текущие виджеты и список тайтлов перед обновлением
            self.clear_previous_posters()
            updated_titles = []

            # Обновляем ссылки на эпизоды для уже загруженных тайтлов
            for title in self.total_titles:
                updated_title = self.update_title_links(title, selected_quality)
                updated_titles.append(updated_title)

            # Перезаписываем `self.total_titles` обновлённым списком
            self.total_titles = updated_titles

            # Отображаем обновленные тайтлы в UI
            self.display_titles_in_ui(updated_titles)

        except Exception as e:
            self.logger.error(f"Ошибка при обновлении экрана при нажатии REFRESH: {e}")

    def update_title_links(self, title, selected_quality):
        """Обновляет ссылки на эпизоды для заданного качества."""
        if selected_quality == 'fhd':
            title.current_links = [ep.hls_fhd for ep in title.episodes if ep.hls_fhd]
        elif selected_quality == 'hd':
            title.current_links = [ep.hls_hd for ep in title.episodes if ep.hls_hd]
        elif selected_quality == 'sd':
            title.current_links = [ep.hls_sd for ep in title.episodes if ep.hls_sd]
        else:
            self.logger.warning(f"Неизвестное качество: {selected_quality}, используем ссылки по умолчанию.")

        # Логирование обновленных ссылок
        self.logger.debug(f"Обновлены ссылки для тайтла {title.title_id}: {title.current_links}")
        return title

    def update_quality_and_refresh(self):
        selected_quality = self.quality_dropdown.currentText()
        data = self.current_data

        if not data:
            error_message = "No data available. Please fetch data first."
            self.logger.error(error_message)
            return

        self.logger.debug(f"DATA count: {len(data) if isinstance(data, dict) else 'not a dict'}")

        # Если текущие данные из расписания, обновляем расписание из базы данных
        if isinstance(data, list) and all(isinstance(day_info, dict) and "day" in day_info for day_info in data):
            for day_info in data:
                day = day_info.get("day")
                if isinstance(day, int):
                    self.display_titles_for_day(day)
                else:
                    self.logger.error("Invalid day value found, expected an integer.")

        # Проверка, если отображается информация об одном тайтле
        elif isinstance(data, dict):
            # Если это информация об одном тайтле или общем списке
            if "list" in data and isinstance(data["list"], list):
                title_list = data["list"]

                # Обновление информации для каждого тайтла в списке
                for title_data in title_list:
                    title_id = title_data.get('id')
                    if isinstance(title_id, int):
                        self.display_info(title_id)
                    else:
                        self.logger.error("Invalid title ID found in list, expected an integer.")
            else:
                # Если это один тайтл
                title_id = data.get('id')
                if isinstance(title_id, int):
                    self.display_info(title_id)
                else:
                    error_message = "No valid title ID found. Please fetch data again."
                    self.logger.error(error_message)

        else:
            error_message = "Unsupported data format. Please fetch data first."
            self.logger.error(error_message)

    def reload_schedule(self):
        """RELOAD и отображает тайтлы DISPLAY SCHEDULE."""
        day = self.day_of_week
        titles = self.current_titles
        if not day:
            day = 0 # Monday
        status, title_ids = self.check_and_update_schedule_after_display(day, titles)
        if status:
            self.display_titles(title_ids)

    def generate_callbacks(self):
        # Существующие статические колбеки
        callbacks = {
            "get_search_by_title": self.get_search_by_title,
            "get_random_title": self.get_random_title,
            "refresh_display": self.refresh_display,
            "save_playlist_wrapper": self.save_playlist_wrapper,
            "play_playlist_wrapper": self.play_playlist_wrapper,
            "reload_schedule": self.reload_schedule,
        }

        # Динамически добавляем колбэки для простых функций
        for metadata in all_layout_metadata:
            callback_key = metadata.get("callback_key")
            callback_type = metadata.get("callback_type", "complex")

            if callback_key and callback_type == "simple" and callback_key not in callbacks:
                callbacks[callback_key] = self.generate_simple_callback(callback_key)

        return callbacks

    def generate_simple_callback(self, callback_name):
        """Создает простой колбек, который вызывает display_titles с соответствующими параметрами."""

        def simple_callback(*args, **kwargs):
            self.logger.info(f"Вызван простой колбек: {callback_name}")
            if callback_name == "load_previous_titles":
                self.display_titles(show_previous=True)
            elif callback_name == "load_more_titles":
                self.display_titles(show_next=True)
            elif callback_name == "display_titles_text_list":
                self.display_titles(show_mode='titles_list', batch_size=self.titles_list_batch_size)
                self.current_offset += self.titles_list_batch_size
            elif callback_name == "display_franchises":
                self.display_titles(show_mode='franchise_list', batch_size=self.titles_list_batch_size)
                self.current_offset += self.titles_list_batch_size
            elif callback_name == "display_system":
                self.display_titles(show_mode='system')
            elif callback_name == "toggle_need_to_see":
                self.display_titles(show_mode='need_to_see_list', batch_size=self.titles_list_batch_size)
                self.current_offset += self.titles_list_batch_size
            else:
                self.logger.warning(f"Неизвестный колбек: {callback_name}")

        return simple_callback

    def display_titles(self, title_ids=None, batch_size=None, show_mode='default', show_previous=False, show_next=False,
                       start=False):
        try:
            # Логика определения offset
            if start:
                self.logger.debug(
                    f"START: current_offset: {self.current_offset} - titles_batch_size: {self.titles_batch_size}")
            if show_next:
                # Проверяем, достаточно ли данных для загрузки

                statistics = self.db_manager.get_statistics_from_db()  # Метод подсчета общего количества тайтлов
                total_available_titles = statistics.get('titles_count', 0)
                if self.current_offset + self.titles_batch_size >= total_available_titles:
                    self.logger.info("Достигнут конец списка тайтлов, сбрасываем оффсет.")
                    self.current_offset = 0  # Сбрасываем оффсет, если достигли конца данных
                else:
                    self.current_offset += self.titles_batch_size
                    self.logger.debug(
                        f"NEXT: current_offset: {self.current_offset} - titles_batch_size: {self.titles_batch_size}")
            if show_previous:
                self.current_offset = max(0, self.current_offset - self.titles_batch_size)
                self.logger.debug(
                    f"PREV: current_offset: {self.current_offset} - titles_batch_size: {self.titles_batch_size}")

            # Используем фабрику для получения данных
            data_factory = TitleDataFactory(self.db_manager, self.user_id)
            titles = data_factory.get_titles(
                show_mode=show_mode,
                title_ids=title_ids,
                current_offset=self.current_offset,
                batch_size=batch_size
            )

            # Если данных нет, сбрасываем оффсет
            if not titles:
                self.logger.info("Нет доступных данных для отображения, сбрасываем оффсет.")
                self.current_offset = 0
                self.total_titles = 0
                return

            # Передача данных в метод отображения
            self.display_titles_in_ui(titles, show_mode)

            self.logger.debug(f"Was sent to display {show_mode} {len(titles)} titles.")
            self.total_titles = titles
            self.logger.debug(f"self.total_titles: {len(self.total_titles)}")
        except Exception as e:
            self.logger.error(f"Ошибка display_titles: {e}")

    def display_titles_in_ui(self, titles, show_mode='default', row_start=0, col_start=0):
        try:
            self.clear_previous_posters()

            factory = TitleDisplayFactory(self)

            if len(titles) == 1:
                # Если у нас один тайтл, отображаем его с полным описанием
                title_widget, _ = factory.create('one_title', titles[0])
                self.posters_layout.addWidget(title_widget, 0, 0, 1, 2)

                self.logger.debug(f"Displayed one title.")
            elif show_mode == 'system':
                # Системный виджет
                system_widget, _ = factory.create('system', titles)
                self.posters_layout.addWidget(system_widget, 0, 0, 1, 2)
                self.logger.debug(f"Displayed {show_mode}")
            else:
                # Проходим по каждому тайтлу и создаем соответствующий виджет
                for index, title in enumerate(titles):
                    title_widget, num_columns = factory.create(show_mode, title)
                    # Размещение виджета в макете
                    row = (index + row_start) // num_columns
                    column = (index + col_start) % num_columns

                    self.posters_layout.addWidget(title_widget, row, column)

            self.logger.debug(f"Displayed {show_mode} with {len(titles)} titles.")
        except Exception as e:
            self.logger.error(f"Ошибка display_titles_in_ui: {e}")

    def display_info(self, title_id):
        """Отображает информацию о конкретном тайтле."""
        self.clear_previous_posters()

        # Получаем тайтл из базы данных по его идентификатору
        titles = self.db_manager.get_titles_from_db(title_id=title_id)

        if not titles or titles[0] is None:
            self.logger.error(f"Title with title_id {title_id} not found in the database.")
            return

        self.total_titles = titles

        self.display_titles_in_ui(titles)

    def display_titles_for_day(self, day_of_week):
        # Очистка предыдущих постеров
        self.clear_previous_posters()
        titles = self.db_manager.get_titles_from_db(show_all=False, day_of_week=day_of_week)
        self.day_of_week = day_of_week
        self.logger.debug(f"day_of_week: {day_of_week}, titles: {len(titles)}")
        if titles:
            # Сохраняем текущие тайтлы для последующего использования
            self.total_titles = titles
            # Отображаем тайтлы в UI
            self.display_titles_in_ui(titles)
            # Проверяем и обновляем расписание после отображения every 10 min
            QTimer.singleShot(600000, lambda: self.reload_schedule())

        else:
            try:
                # Если тайтлы отсутствуют, получаем данные с сервера
                titles_list = []
                data = self.get_schedule(day_of_week)
                self.logger.debug(f"Received data from server: {len(data)} keys (type: {type(data).__name__})")
                if data:
                    parsed_data = self.parse_schedule_data(data)
                    self.logger.debug(f"parsed_data: {parsed_data}")
                    self._save_parsed_data(parsed_data)

                    for titles_list in data:
                        titles_list = titles_list.get("list", [])
                    # TODO: fix this. need to count as dict
                    self.logger.debug(f"title_list: {len(titles_list)}")
                    # Сохраняем данные в базе данных
                    self._save_titles_list(titles_list)

                    titles = self.db_manager.get_titles_from_db(day_of_week)
                    self.total_titles = titles
                    self.display_titles_in_ui(titles)
                    self.day_of_week = day_of_week
            except Exception as e:
                self.logger.error(f"Error fetching titles from schedule: {e}")

    def _save_parsed_data(self, parsed_data):
        for i, item in enumerate(parsed_data):
            self.db_manager.save_schedule(item["day"], item["title_id"], last_updated=datetime.utcnow())
            # TODO: fix this. need to count as dict
            self.logger.debug(
                f"[{i + 1}/{len(parsed_data)}] Saved title_id from API: {item['title_id']} on day {item['day']}")

    def _save_titles_list(self, titles_list):
        try:
            for title_data in titles_list:
                title_id = title_data.get('id', {})
                self.logger.debug(
                f"[XXX] Saving title_id from API: {title_id}")
            self.invoke_database_save(titles_list)
            self.current_data = titles_list
        except Exception as e:
            self.logger.error(f"Ошибка при save titles расписания: {e}")

    def check_and_update_schedule_after_display(self, day_of_week, current_titles):
        """Проверяет наличие обновлений в расписании и обновляет базу данных, если необходимо."""
        try:
            # Получаем актуальные данные из API
            titles_list = []
            data = self.get_schedule(day_of_week)
            if data:
                parsed_data = self.parse_schedule_data(data)
                self.logger.debug(f"parsed_data: {parsed_data}")
                self._save_parsed_data(parsed_data)

                for item in data:
                    titles = item.get("list", [])
                    titles_list.extend(titles)
                # TODO: fix this. need to count as dict
                self.logger.debug(f"title_list: {len(titles_list)}")
                # Сохраняем данные в базе данных
                self._save_titles_list(titles_list)
                # TODO: fix this. need to count as dict
                self.logger.debug(f"Title list from db {len(titles_list)}")
                self.logger.debug(f"parsed data from API for saving schedule {len(parsed_data)}")
                self.logger.debug(f"DATA from API {len(data)}")

                new_title_ids = {title_data.get('id') for title_data in titles_list}
                if current_titles:
                    # TODO: fix this. need to count as dict
                    self.logger.debug(f"Attributes of current title: {len(vars(current_titles[0]))}")
                    current_title_ids = {title_data.title_id for title_data in current_titles}
                    titles_to_remove = current_title_ids - new_title_ids
                    if titles_to_remove:
                        self.logger.debug(f"find titles for remove: {titles_to_remove}")
                        self.db_manager.remove_schedule_day(titles_to_remove, day_of_week)
                    self.logger.debug(f"no need to update schedule {current_title_ids} equal {new_title_ids}")
                return True, new_title_ids
        except Exception as e:
            self.logger.error(f"Ошибка при проверке обновлений расписания: {e}")
            return False, None

    def clear_previous_posters(self):
        """Удаляет все предыдущие виджеты из сетки постеров."""
        while self.posters_layout.count():
            item = self.posters_layout.takeAt(0)
            widget_to_remove = item.widget()
            if widget_to_remove is not None:
                widget_to_remove.deleteLater()  # Полностью удаляет виджет из памяти
            # Также проверяем, если в сетке может быть элемент, а не виджет (например, пустое место)
            if item.layout() is not None:
                self.clear_layout(item.layout())

    def clear_layout(self, layout):
        """Рекурсивно очищает все элементы из переданного layout."""
        if layout is not None:
            while layout.count():
                item = layout.takeAt(0)
                widget_to_remove = item.widget()
                if widget_to_remove is not None:
                    widget_to_remove.deleteLater()
                elif item.layout() is not None:
                    self.clear_layout(item.layout())

    def create_system_browser(self, statistics):
        """
        Прокси-метод, который делегирует создание system_browser в UISGenerator.
        """
        self.logger.debug(f"Пытаемся создать system_browser с параметрами: {len(statistics)}")
        return self.ui_s_generator.create_system_browser(statistics)

    def create_title_browser(self, title, show_mode='default'):
        """
        Прокси-метод, который делегирует создание title_browser в UIGenerator.
        """
        return self.ui_generator.create_title_browser(title, show_mode=show_mode)

    def invoke_database_save(self, title_list):
        # TODO: fix this. need to count as dict
        self.logger.debug(f"Processing title data: {len(title_list)}")
        processes = {
            self.db_manager.process_episodes: "episodes",
            self.db_manager.process_torrents: "torrents",
            self.db_manager.process_titles: "titles"
        }
        for title_data in title_list:
            for process_func, process_name in processes.items():
                result = process_func(title_data)
                if result:
                    self.logger.debug(f"Successfully saved {process_name} table. STATUS: {result}")
                else:
                    self.logger.warning(f"Failed to process {process_name}")

    def get_random_title(self):
        data = self.api_client.get_random_title()
        if 'error' in data:
            self.logger.error(data['error'])
            return
        # TODO: fix this. need to count as dict
        self.logger.debug(f"Full response data: {len(data)} keys (type: {type(data).__name__})")
        # Получаем список тайтлов из ответа
        title_list = data.get('list', [])
        if not title_list:
            self.logger.error("No titles found in the response.")
            return
        # Извлекаем первый элемент из списка и получаем его ID
        title_data = title_list[0]
        title_id = title_data.get('id')
        self.invoke_database_save(title_list)
        if title_id is None:
            self.logger.error("Title ID not found in response.")
            return
        self.display_info(title_id)
        self.current_data = data

    def get_schedule(self, day):
        try:
            data = self.api_client.get_schedule(day)
            # Проверка на ошибку в данных
            if isinstance(data, dict) and 'error' in data:
                self.logger.error(data['error'])
                return None
            self.current_data = data
            return data  # Возвращаем данные вместо True
        except Exception as e:
            self.logger.error(f"Ошибка при получении расписания: {e}")
            return None

    def parse_schedule_data(self, data):
        """Парсит данные расписания и возвращает данные, подготовленные для сохранения, и список тайтлов."""
        parsed_data = []
        if not isinstance(data, list):
            self.logger.error(f"Ожидался список, получен: {type(data).__name__}")
            return parsed_data
        # prepare info saving to schedules table as dict
        for day_info in data:
            if not isinstance(day_info, dict):
                self.logger.error(f"Неправильный формат данных: ожидался словарь, получен {type(day_info).__name__}")
                continue
            day = day_info.get("day")
            title_list = day_info.get("list")
            # Проверка, что title_list является списком
            if not isinstance(title_list, list):
                self.logger.error(
                    f"Неправильный формат данных 'list': ожидался список, получен {type(title_list).__name__}")
                continue
            for title in title_list:
                if isinstance(title, dict):
                    title_id = title.get('id')
                    if title_id:
                        parsed_data.append({"day": day, "title_id": title_id})
        return parsed_data

    def get_search_by_title(self):
        search_text = self.title_search_entry.text()
        if not search_text:
            return
        self.logger.debug(f"keywords: {search_text}")
        title_ids = self.db_manager.get_titles_by_keywords(search_text)
        if title_ids:
            self._handle_found_titles(title_ids, search_text)
        else:
            self._handle_no_titles_found(search_text)

    def _handle_found_titles(self, title_ids, search_text):
        if len(title_ids) == 1:
            # If only one title is found, display its information directly
            self.display_info(title_ids[0])
        else:
            # If multiple titles are found, extract all title_ids for display_titles
            self.logger.debug(f"Get titles from DB with title_ids: {title_ids} by keyword {search_text}")
            self.display_titles(title_ids)

    def _handle_no_titles_found(self, search_text):
        keywords = search_text.split(',')
        keywords = [kw.strip() for kw in keywords]
        if len(keywords) == 1 and keywords[0].isdigit():
            title_id = int(keywords[0])
            data = self.api_client.get_search_by_title_id(title_id)
        elif all(kw.isdigit() for kw in keywords):
            title_ids = [int(kw) for kw in keywords]
            data = self.api_client.get_search_by_title_ids(title_ids)
        else:
            data = self.api_client.get_search_by_title(search_text)
        if 'error' in data:
            self.logger.error(data['error'])
            return
        # Проверяем тип данных в ответе
        if isinstance(data, dict) and 'list' in data:
            title_list = data['list']
        elif isinstance(data, dict) and 'id' in data:
            # Если это одиночный тайтл, оборачиваем его в список
            title_list = [data]
        elif isinstance(data, list):
            title_list = data
        else:
            self.logger.error("No titles found in the response.")
            return
        if not title_list:
            self.logger.error("No titles found in the response.")
            return
        self.logger.debug(f"Processing title data: {title_list}")
        self.invoke_database_save(title_list)
        title_ids = [title_data.get('id') for title_data in title_list if title_data.get('id') is not None]
        self._handle_found_titles(title_ids, search_text)
        # Сохраняем текущие данные
        self.current_data = data

    def save_playlist_wrapper(self):
        """
        Wrapper function to handle saving the playlists.
        Iterates through all discovered playlists and saves them.
        """
        self.playlist_filename = None
        if not self.playlists:
            self.logger.error("No playlists found to save.")
            return

        for title_id, playlist in self.playlists.items():
            sanitized_title = playlist['sanitized_title']
            discovered_links = playlist['links']
            if discovered_links:
                filename = self.playlist_manager.save_playlist([sanitized_title], discovered_links, self.stream_video_url)
                self.logger.debug(f"Playlist for title {sanitized_title} was sent for saving with filename; {filename}.")
            else:
                self.logger.error(f"No links found for title {sanitized_title}, skipping saving.")
        # Теперь сохраняем общий комбинированный плейлист
        combined_playlist_filename = "_".join([info['sanitized_title'] for info in self.playlists.values()])[:100] + ".m3u"
        combined_links = []
        # Собираем все ссылки из всех плейлистов
        for playlist_info in self.playlists.values():
            combined_links.extend(playlist_info['links'])
        # Сохраняем комбинированный плейлист
        if combined_links:
            if os.path.exists(os.path.join("playlists", combined_playlist_filename)):
                combined_playlist_filename = f"{combined_playlist_filename}_{int(datetime.now().timestamp())}"  # Добавляем временной штамп для уникальности

            filename = self.playlist_manager.save_playlist(combined_playlist_filename, combined_links,
                                                           self.stream_video_url)
            if filename:
                self.logger.debug(f"Combined playlist '{filename}' saved.")
                self.playlist_filename = filename
            else:
                self.logger.error("Failed to save the combined playlist.")
        else:
            self.logger.error("No valid links found for saving the combined playlist.")

    def play_playlist_wrapper(self, file_name=None):
        """
        Wrapper function to handle playing the playlist.
        Determines the file name and passes it to play_playlist.
        """
        if not self.sanitized_titles:
            self.logger.error("Playlist not found, please save playlist first.")
            return
        if not file_name:
            file_name = self.playlist_filename
        video_player_path = self.video_player_path
        self.logger.debug(f"Attempting to play playlist: {file_name} with player: {video_player_path}")
        self.playlist_manager.play_playlist(file_name, video_player_path)
        self.logger.debug("Opening video player...")

    def save_torrent_wrapper(self, link, title_name, torrent_id):
        """
        Wrapper function to handle saving the torrent.
        Collects title names and links, and passes them to save_torrent_file.
        """
        try:
            sanitized_title_name = self.sanitize_filename(title_name)
            file_name = f"{sanitized_title_name}_{torrent_id}.torrent"

            self.torrent_manager.save_torrent_file(link, file_name)
            self.logger.debug("Opening torrent client ..")
        except Exception as e:
            error_message = f"Error in save_torrent_wrapper: {str(e)}"
            self.logger.error(error_message)

    def on_link_click(self, url):
        try:
            link = url.toString()
            if link.startswith('display_info/'):
                title_id = int(link.split('/')[1])
                QTimer.singleShot(100, lambda: self.display_info(title_id))
            elif link.startswith('reload_template/'):
                template_name = link.split('/')[1]
                self.db_manager.save_template(template_name)
                QTimer.singleShot(100, lambda: self.display_titles(start=True))
            elif link.startswith('reset_offset/'):
                reset_status = link.split('/')[1]
                if reset_status:
                    self.current_offset = 0
                    QTimer.singleShot(100, lambda: self.display_titles(start=True))
            elif link.startswith('reload_info/'):
                title_id = int(link.split('/')[1])
                QTimer.singleShot(100, lambda: self.display_info(title_id))
            elif link.startswith('set_download_status/'):
                parts = link.split('/')
                if len(parts) >= 4:
                    user_id = int(parts[1])
                    title_id = int(parts[2])
                    torrent_id = int(parts[3]) if len(parts) > 3 and parts[3] != 'None' else None
                    self.logger.debug(f"Setting user:{user_id} download status for title_id, torrent_id: {title_id}, {torrent_id}")
                    _, current_download_status = self.db_manager.get_history_status(user_id=user_id, title_id=title_id, torrent_id=torrent_id)
                    new_download_status = not current_download_status
                    self.logger.debug(f"Setting download status for user_id: {user_id}, title_id: {title_id}, torrent_id: {torrent_id}, status: {new_download_status}")
                    self.db_manager.save_watch_status(user_id=user_id, title_id=title_id, torrent_id=torrent_id, is_download=new_download_status)
                    QTimer.singleShot(100, lambda: self.display_info(title_id))
                else:
                    self.logger.error(f"Invalid set_download_status/ link structure: {link}")
            elif link.startswith('set_need_to_see/'):
                parts = link.split('/')
                if len(parts) >= 3:
                    user_id = int(parts[1])
                    title_id = int(parts[2])
                    self.logger.debug(f"Setting user:{user_id} need to see status for title_id: {title_id}")
                    current_status = self.db_manager.get_need_to_see(user_id=user_id, title_id=title_id)
                    new_watch_status = not current_status
                    self.logger.debug(f"Setting watch status for user_id: {user_id}, title_id: {title_id}, status: {new_watch_status}")
                    self.db_manager.save_need_to_see(user_id=user_id, title_id=title_id, need_to_see=new_watch_status)
                    QTimer.singleShot(100, lambda: self.display_info(title_id))
                else:
                    self.logger.error(f"Invalid set_need_to_see/ link structure: {link}")
            elif link.startswith('set_watch_status/'):
                parts = link.split('/')
                if len(parts) >= 4:
                    user_id = int(parts[1])
                    title_id = int(parts[2])
                    episode_id = int(parts[3]) if len(parts) > 3 and parts[3] != 'None' else None
                    self.logger.debug(f"Setting user:{user_id} watch status for title_id, episode_id: {title_id}, {episode_id}")
                    current_status = self.db_manager.get_history_status(user_id=user_id, title_id=title_id,episode_id=episode_id)
                    current_watched_status, _ = current_status
                    new_watch_status = not current_watched_status
                    self.logger.debug(f"Setting watch status for user_id: {user_id}, title_id: {title_id}, episode_id: {episode_id}, status: {new_watch_status}")
                    self.db_manager.save_watch_status(user_id=user_id, title_id=title_id, episode_id=episode_id, is_watched=new_watch_status)
                    QTimer.singleShot(100, lambda: self.display_info(title_id))
                else:
                    self.logger.error(f"Invalid set_watch_status/ link structure: {link}")
            elif link.startswith('set_watch_all_episodes_status/'):
                parts = link.split('/')
                if len(parts) >= 4:
                    user_id = int(parts[1])
                    title_id = int(parts[2])
                    episode_ids = eval(parts[3])
                    if not isinstance(episode_ids, list):
                        raise ValueError("Invalid episode_ids, expected a list.")
                    self.logger.debug(f"Setting user:{user_id} watch status for title_id, all_episodes: {title_id}")
                    current_watched_status = self.db_manager.get_all_episodes_watched_status(user_id=user_id, title_id=title_id)
                    new_watch_status = not current_watched_status
                    self.logger.debug(f"Setting watch status for user_id: {user_id}, title_id: {title_id} all_episodes status: {new_watch_status}")
                    self.db_manager.save_watch_all_episodes(user_id, title_id, is_watched=new_watch_status, episode_ids=episode_ids)
                    QTimer.singleShot(100, lambda: self.display_info(title_id))
                else:
                    self.logger.error(f"Invalid set_watch_all_episodes_status/ link structure: {link}")
            elif link.startswith('set_rating/'):
                parts = link.split('/')
                if len(parts) >= 4:
                    title_id = int(parts[1])
                    rating_name = parts[2]
                    rating_value = parts[3]
                    self.logger.debug(f"Setting rating for title_id: {title_id}, rating: {rating_name}:{rating_value}")
                    self.db_manager.save_ratings(title_id, rating_name=rating_name, rating_value=rating_value)
                    QTimer.singleShot(100, lambda: self.display_info(title_id))
                else:
                    self.logger.error(f"Invalid set_rating/ link structure: {link}")
            elif link.startswith('play_all/'):
                parts = link.split('/')
                if len(parts) >= 3:
                    title_id = int(parts[1])
                    filename = parts[2]
                    self.logger.debug(f"Play_all: title_id: {title_id}, filename: {filename}")
                    self.play_playlist_wrapper(filename)
                    QTimer.singleShot(100, lambda: self.display_info(title_id))
                else:
                    self.logger.error(f"Invalid play_all link structure: {link}")
            elif link.endswith('.m3u8'):
                video_player_path = self.video_player_path
                open_link = self.pre + self.stream_video_url + link
                media_player_command = [video_player_path, open_link]
                subprocess.Popen(media_player_command)
                self.logger.info(f"Playing video link: {link}")
                title_id = link.split('/')[4]
                QTimer.singleShot(100, lambda: self.display_info(title_id))
            elif '/torrent/download.php' in link:
                title_id, title_code, torrent_id = self.torrent_data
                self.save_torrent_wrapper(link, title_code, torrent_id)
                self.logger.info(
                    f"Torrent data: ["
                    f"title_id: {title_id}, "
                    f"title_code: {title_code}, "
                    f"torrent_id: {torrent_id}"
                    f"]"
                )
                QTimer.singleShot(100, lambda: self.display_info(title_id))
            else:
                self.logger.error(f"Unknown link type: {link}")
        except Exception as e:
            error_message = f"An error occurred while processing the link: {str(e)}"
            self.logger.error(error_message)

    def get_poster_or_placeholder(self, title_id):
        try:
            poster_data, is_placeholder = self.db_manager.get_poster_blob(title_id)
            if is_placeholder:
                self.logger.warning(f"Warning: No poster data for title_id: {title_id}, using placeholder.")
                poster_link = self.db_manager.get_poster_link(title_id)
                processed_link = self.perform_poster_link(poster_link)
                link_to_download = []
                if processed_link:
                    link_to_download.append((title_id, processed_link))
                if link_to_download:
                    self.poster_manager.write_poster_links(link_to_download)
            return poster_data

        except Exception as e:
            self.logger.error(f"Ошибка get_poster_or_placeholder: {e}")
            return None

    def perform_poster_link(self, poster_link):
        try:
            self.logger.debug(f"Processing poster link: {poster_link}")
            poster_url = self.pre + self.base_url + poster_link
            standardized_url = self.standardize_url(poster_url)
            self.logger.debug(f"Standardize the poster URL: {standardized_url[-41:]}")
            # Check if the standardized URL is already in the cached poster links
            if standardized_url in map(self.standardize_url, self.poster_manager.poster_links):
                self.logger.debug(f"Poster URL already cached: {standardized_url[-41:]}. Skipping fetch.")
                return None
            return standardized_url
        except Exception as e:
            error_message = f"An error occurred while getting the poster: {str(e)}"
            self.logger.error(error_message)
            return None

    @staticmethod
    def sanitize_filename(name):
        """
        Sanitize the filename by removing special characters that are not allowed in filenames.
        """
        return re.sub(r'[<>:"/\\|?*]', '_', name)

    def standardize_url(self, url):
        """
        Standardizes the URL for consistent comparison.
        Strips spaces, removes query parameters if necessary, or any other needed cleaning.
        """
        # Basic URL standardization example: stripping spaces and removing query parameters
        return url.strip().split('?')[0]

