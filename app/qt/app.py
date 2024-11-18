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

from PyInstaller.lib.modulegraph.modulegraph import header
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLineEdit, QLabel, QComboBox, QGridLayout, QScrollArea, QTextBrowser, QSizePolicy, QGraphicsDropShadowEffect,
    QMessageBox
)
from PyQt5.QtCore import Qt, QByteArray, QBuffer, QUrl, QTimer, QRunnable, QThreadPool, pyqtSlot, QObject, pyqtSignal
from PyQt5.QtGui import QPixmap
from sqlalchemy.orm.loading import instances

from app.qt.ui_manger import UIManager
from core import database_manager
from core.database_manager import DatabaseManager
from utils.config_manager import ConfigManager
from utils.api_client import APIClient
from utils.poster_manager import PosterManager
from utils.playlist_manager import PlaylistManager
from utils.torrent_manager import TorrentManager


class CreateTitleBrowserTask(QRunnable):
    def __init__(self, app, title, row, column, show_description=False, show_one_title=False):
        super().__init__()
        self.logger = logging.getLogger(__name__)
        self.app = app
        self.title = title
        self.row = row
        self.column = column
        self.show_description = show_description
        self.show_one_title = show_one_title

    @pyqtSlot()
    def run(self):
        try:
            # Создаем виджет для отображения информации о тайтле
            title_browser = self.app.create_title_browser(self.title, self.show_description, self.show_one_title)
            self.app.logger.debug(f"Created title browser for title_id: {self.title.title_id}")

            # Emit signal to add the widget to the layout in the main thread
            self.app.add_title_browser_to_layout.emit(title_browser, self.row, self.column)
        except Exception as e:
            self.app.logger.error(f"Error in CreateTitleBrowserTask for title_id {self.title.title_id}: {e}")


class AnimePlayerAppVer3(QWidget):
    add_title_browser_to_layout = pyqtSignal(QTextBrowser, int, int)

    def __init__(self, db_manager, version):
        super().__init__()
        self.logger = logging.getLogger(__name__)
        self.thread_pool = QThreadPool()  # Пул потоков для управления задачами
        self.thread_pool.setMaxThreadCount(4)
        self.add_title_browser_to_layout.connect(self.on_add_title_browser_to_layout)
        self.playlist_filename = None
        self.play_playlist_button = None
        self.save_playlist_button = None
        self.current_data = None
        self.display_button = None
        self.current_link = None
        self.poster_container = None
        self.scroll_area = None
        self.posters_layout = None
        self.day_buttons = None
        self.days_of_week = None
        self.day_of_week = None
        self.refresh_button = None
        self.quality_dropdown = None
        self.quality_label = None
        self.random_button = None
        self.display_button = None
        self.title_search_entry = None
        self.current_titles = None
        self.selected_quality = None
        self.torrent_data = None
        self.load_more_button = None
        self.discovered_links = []
        self.sanitized_titles = []
        self.title_names = []
        self.total_titles = []
        self.playlists = {}
        self.app_version = version
        self.logger.debug(f"Initializing AnimePlayerApp Version {self.app_version}")
        # TODO: fix blank spase
        self.blank_spase = '&nbsp;'
        self.row_start = 0
        self.col_start = 0
        self.pre = "https://"
        self.days_of_week = ["MO", "TU", "WE", "TH", "FR", "SA", "SU"]
        self.cache_file_path = "temp/poster_cache.txt"
        self.config_manager = ConfigManager('config/config.ini')

        """Loads the configuration settings needed by the application."""
        # self.stream_video_url = self.config_manager.get_setting('Settings', 'stream_video_url')
        self.stream_video_url = None
        self.base_url = self.config_manager.get_setting('Settings', 'base_url')
        self.api_version = self.config_manager.get_setting('Settings', 'api_version')

        self.titles_batch_size = int(self.config_manager.get_setting('Settings', 'titles_batch_size'))
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
        self.ui_manager = UIManager(self)
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
        self.setWindowTitle('Anime Player v3')
        self.setGeometry(100, 100, 1000, 800)

        # Основной вертикальный layout
        main_layout = QVBoxLayout()
        self.ui_manager.setup_main_layout(main_layout)
        self.setLayout(main_layout)

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
            self.display_titles_in_ui(self.total_titles, self.row_start, self.col_start, self.num_columns)

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

    def update_quality_and_refresh(self, event=None):
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
            # Если day невозможно преобразовать в целое число, установим его в 0
            day = 0
        status, title_ids = self.check_and_update_schedule_after_display(day, titles)
        if status:
            self.display_titles(title_ids)
        return True

    def display_titles_text_list(self):
        """Загружает и отображает тайтлы DISPLAY TITLES."""
        self.display_titles(titles_text_list=True)
        return True

    def load_more_titles(self):
        """Загружает и отображает тайтлы LOAD MORE."""
        self.logger.debug(f"LOAD MORE BUTTON PRESSED")
        self.display_titles(show_next=True)
        return True

    def load_previous_titles(self):
        """Загружает и отображает тайтлы LOAD PREV."""
        self.logger.debug(f"LOAD PREV BUTTON PRESSED")
        self.display_titles(show_previous=True)
        return True

    def display_franchises(self):
        self.display_titles(franchises=True)

    def display_system(self):
        self.display_titles(system=True)

    def display_titles(self, title_ids=None, titles_text_list=False, franchises=False, system=False, show_previous=False, show_next=False, start=False):
        """Отображение первых тайтлов при старте.
        :param start:
        :param show_next:
        :param show_previous:
        :param system:  Show system layout
        :param franchises: Отображение нескольких тайтлов with relationship Franchise по title_id
        :param title_ids: Отображение нескольких тайтлов по title_id
        :param titles_text_list: Отображение списка тайтлов.
        """
        if start:
            self.logger.debug(f"START: current_offset: {self.current_offset} - titles_batch_size: {self.titles_batch_size}")
        if show_next:
            # FIXME: would be increment offset at the end of title list
            self.current_offset += self.titles_batch_size
            self.logger.debug(
                f"NEXT: current_offset: {self.current_offset} - titles_batch_size: {self.titles_batch_size}")

        if show_previous:
            self.current_offset = max(0, self.current_offset - self.titles_batch_size)  # Ограничиваем offset снизу
            self.logger.debug(f"PREV: current_offset: {self.current_offset} - titles_batch_size: {self.titles_batch_size}")

        match (bool(title_ids), titles_text_list, franchises):
            case (True, _, _):
                show_mode = 'title_ids'
                titles = self.db_manager.get_titles_from_db(show_all=False,
                                                            offset=self.current_offset, title_ids=title_ids)
                self.display_titles_in_ui(titles, self.row_start, self.col_start, self.num_columns)
            case (False, True, False):
                titles = self.db_manager.get_titles_from_db(show_all=True, batch_size=12, offset=self.current_offset)
                show_mode = 'titles_text_list'
                self.display_titles_in_ui(titles, row_start=0, col_start=0, num_columns=4, titles_text_list=True)
            case (False, False, False):
                titles = self.db_manager.get_titles_from_db(show_all=True, batch_size=self.titles_batch_size,
                                                            offset=self.current_offset)
                show_mode = 'default'
                self.display_titles_in_ui(titles, self.row_start, self.col_start, self.num_columns)
            case (False, False, True):
                titles = self.db_manager.get_franchises_from_db(show_all=True, batch_size=12, offset=self.current_offset)
                show_mode = 'franchise_list'
                self.display_titles_in_ui(titles, row_start=0, col_start=0, num_columns=4, franchises_list=True)
        self.logger.debug(f"Was sent to display {show_mode} {len(titles)} titles.")
        # self.logger.debug(f"{titles}")

        if system:
            titles = self.db_manager.get_statistics_from_db()
            self.display_titles_in_ui(titles, row_start=0, col_start=0, num_columns=4, system=True)
        # Сохраняем загруженные тайтлы в список для доступа позже
        else:
            self.total_titles = titles
            len_total_titles = len(self.total_titles)
            self.logger.debug(f"self.total_titles:{len_total_titles}")

    def display_titles_in_ui(self, titles, row_start=0, col_start=0, num_columns=2, titles_text_list=False, franchises_list=False, system=False):
        """Создает виджет для тайтла и добавляет его в макет."""
        self.clear_previous_posters()
        if len(titles) == 1:
            # Если у нас один тайтл, отображаем его с полным описанием
            title = titles[0]
            self.logger.debug(f"One title ;)")
            title_layout = self.create_title_browser(title, show_description=True, show_one_title=True)
            self.posters_layout.addLayout(title_layout, 0, 0, 1, 2)
            self.logger.debug(f"Displayed one title.")
        elif system:
            # Создаем системный экран с количеством тайтлов и франшиз
            show_mode = 'system'
            system_widget = QWidget(self)
            system_layout = self.create_system_browser(titles)
            system_widget.setLayout(system_layout)

            self.posters_layout.addWidget(system_widget, 0, 0, 1, 2)
            self.logger.debug(f"Displayed {show_mode}")
        else:
            for index, title in enumerate(titles):
                row = (index + row_start) // num_columns
                column = (index + col_start) % num_columns

                if titles_text_list:
                    show_mode = 'titles_text_list'
                    title_browser = self.create_title_browser(title, show_list=True)
                elif franchises_list:
                    show_mode = 'franchise_list'
                    title_browser = self.create_title_browser(title, show_franchise=True)
                else:
                    show_mode = 'default'
                    title_browser = self.create_title_browser(title, show_description=False, show_one_title=False)
                self.logger.debug(f"Displayed {show_mode} {len(titles)} titles.")
                self.posters_layout.addWidget(title_browser, row, column)

    def display_info(self, title_id):
        """Отображает информацию о конкретном тайтле."""
        self.clear_previous_posters()

        # Получаем тайтл из базы данных по его идентификатору
        titles = self.db_manager.get_titles_from_db(title_id=title_id)

        if not titles or titles[0] is None:
            self.logger.error(f"Title with title_id {title_id} not found in the database.")
            return

        self.total_titles = titles

        self.display_titles_in_ui(titles, self.row_start, self.col_start, self.num_columns)

    def display_titles_for_day(self, day_of_week):
        # Очистка предыдущих постеров
        self.clear_previous_posters()

        titles = self.db_manager.get_titles_from_db(day_of_week)

        if titles:
            # Сохраняем текущие тайтлы для последующего использования
            self.total_titles = titles
            # Отображаем тайтлы в UI
            self.display_titles_in_ui(titles, self.row_start, self.col_start, self.num_columns)
            # Проверяем и обновляем расписание после отображения every 10 min
            QTimer.singleShot(600000, lambda: self.check_and_update_schedule_after_display(day_of_week, titles))
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
                    self.logger.debug(f"title_list: {len(titles_list)}")
                    # Сохраняем данные в базе данных
                    self._save_titles_list(titles_list)

                    titles = self.db_manager.get_titles_from_db(day_of_week)
                    self.total_titles = titles
                    self.display_titles_in_ui(titles, self.row_start, self.col_start, self.num_columns)
                    self.day_of_week = day_of_week
            except Exception as e:
                self.logger.error(f"Error fetching titles from schedule: {e}")

    def _save_parsed_data(self, parsed_data):
        for i, item in enumerate(parsed_data):
            self.db_manager.save_schedule(item["day"], item["title_id"], last_updated=datetime.utcnow())
            self.logger.debug(
                f"[{i + 1}/{len(parsed_data)}] Saved title_id from API: {item['title_id']} on day {item['day']}")
        return True

    def _save_titles_list(self, titles_list):
        try:
            for title_data in titles_list:
                title_id = title_data.get('id', {})
                self.logger.debug(
                f"[XXX] Saving title_id from API: {title_id}")
            self.invoke_database_save(titles_list)
            self.current_data = titles_list
            return True
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

                for titles_list in data:
                    titles_list = titles_list.get("list", [])
                self.logger.debug(f"title_list: {len(titles_list)}")
                # Сохраняем данные в базе данных
                self._save_titles_list(titles_list)

                # self.logger.debug(f"Title list from db {titles_list}")
                # self.logger.debug(f"parsed data frpm API for saving schedulw {parsed_data}")
                # self.logger.debug(f"DATA from API {data}")

                new_title_ids = {title_data.get('id') for title_data in titles_list}
                if current_titles:
                    # self.logger.debug(f"Attributes of current title: {vars(current_titles[0])}")

                    # Сравнение данных из базы с данными, полученными из API
                    current_title_ids = {title_data.title_id for title_data in current_titles}


                    # Находим тайтлы, которые отсутствуют в новых данных из API
                    titles_to_remove = current_title_ids - new_title_ids
                    if titles_to_remove:
                        self.logger.debug(f"find titles for remove: {titles_to_remove}")

                        # TODO: fix ths
                        # 10 -
                        new_day_of_week = 10

                        self.db_manager.remove_schedule_day(titles_to_remove, day_of_week, new_day_of_week)
                    self.logger.debug(f"no need to update schedule {current_title_ids} equal {new_title_ids}")
                return True, new_title_ids
        except Exception as e:
            self.logger.error(f"Ошибка при проверке обновлений расписания: {e}")

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

    def create_system_browser(self, statistics):
        """Создает системный экран, отображающий количество всех тайтлов и франшиз."""
        self.logger.debug("Начинаем создание system_browser...")

        # Создаем главный вертикальный layout для системного экрана
        system_layout = QVBoxLayout()

        # Создаем виджет, чтобы обернуть все элементы вместе
        container_widget = QWidget(self)
        container_layout = QVBoxLayout(container_widget)

        # Информация о версии приложения
        app_version = self.app_version

        # Извлечение статистики из аргумента statistics
        titles_count = statistics.get('titles_count', 0)
        franchises_count = statistics.get('franchises_count', 0)
        episodes_count = statistics.get('episodes_count', 0)
        posters_count = statistics.get('posters_count', 0)
        unique_translators_count = statistics.get('unique_translators_count', 0)
        teams_count = statistics.get('unique_teams_count', 0)
        blocked_titles_count = statistics.get('blocked_titles_count', 0)
        # Заблокированные тайтлы могут быть слишком длинными, поэтому мы будем выводить их ограниченно
        blocked_titles_count = statistics.get('blocked_titles_count', 0)
        blocked_titles = statistics.get('blocked_titles', [])

        blocked_titles_list = ""
        if blocked_titles:
            # Разделяем строку на элементы
            blocked_titles_entries = blocked_titles.split(',')
            # Формируем HTML список из элементов
            blocked_titles_list = ''.join(
                f'<li>{entry.strip()}</li>' for entry in blocked_titles_entries
            )

        # Логирование статистики
        self.logger.debug(f"Количество тайтлов: {titles_count}, Количество франшиз: {franchises_count}")
        self.logger.debug(f"Количество эпизодов: {episodes_count}, Количество постеров: {posters_count}")
        self.logger.debug(
            f"Количество уникальных переводчиков: {unique_translators_count}, Количество команд: {teams_count}")
        self.logger.debug(f"Количество заблокированных тайтлов: {blocked_titles_count}")
        self.logger.debug(f"blocked_titles: {blocked_titles}")
        # Создаем QTextBrowser для отображения информации о тайтлах и франшизах
        system_browser = QTextBrowser(self)
        system_browser.setPlainText(f"Title: SYSTEM")

        #system_browser.setProperty('title_id', title.title_id)
        system_browser.anchorClicked.connect(self.on_link_click)
        system_browser.setOpenExternalLinks(True)

        system_browser.setStyleSheet(
            """
            text-align: left;
            border: 1px solid #444;
            color: #000;
            font-size: 14pt;
            font-weight: bold;
            position: relative;
            text-shadow: 1px 1px 2px #FFF;  /* Тень для выделения текста */
            background: rgba(255, 255, 0, 0.5);  /* Полупрозрачный желтый фон */
            """
        )

        # HTML контент для отображения статистики
        html_content = f'''
        <div style="font-size: 20pt;">
            <p>Application version: {app_version}</p>
            <p>Application DB statistics:</p>
        </div>
        <div style="margin: 30px;">
            <p>Количество тайтлов: {titles_count}</p>
            <p>Количество франшиз: {franchises_count}</p>
            <p>Количество эпизодов: {episodes_count}</p>
            <p>Количество постеров: {posters_count}</p>
            <p>Количество уникальных переводчиков: {unique_translators_count}</p>
            <p>Количество команд переводчиков: {teams_count}</p>
            <p>Количество заблокированных тайтлов: {blocked_titles_count}</p>
            <div class="blocked-titles">
                <p>Заблокированные тайтлы (no more updates):</p>
                <ul>{blocked_titles_list}</ul>
            </div>
        </div>
        '''

        system_browser.setHtml(html_content)
        # Добавляем элементы в layout контейнера
        container_layout.addWidget(system_browser)

        # Добавляем контейнер в основной layout
        system_layout.addWidget(container_widget)

        return system_layout

    def create_title_browser(self, title, show_description=False, show_one_title=False, show_list=False, show_franchise=False):
        """Создает элемент интерфейса для отображения информации о тайтле.
        :param title:
        :param show_description:
        :param show_one_title:
        :param show_list:
        :param show_franchise:
        :return:
        """
        self.logger.debug("Начинаем создание title_browser...")

        title_browser = QTextBrowser(self)
        title_browser.setPlainText(f"Title: {title.name_en}")
        title_browser.setOpenExternalLinks(True)
        title_browser.setProperty('title_id', title.title_id)
        title_browser.anchorClicked.connect(self.on_link_click)

        # Общие настройки для различных режимов отображения
        if show_one_title:
            # Создаем горизонтальный layout для отображения деталей тайтла
            title_layout = QHBoxLayout()
            self.logger.debug(f"Создаем title_browser для title_id: {title.title_id}")

            # Постер слева
            poster_label = QLabel(self)
            poster_data = self.get_poster_or_placeholder(title.title_id)

            if poster_data:
                pixmap = QPixmap()
                if pixmap.loadFromData(poster_data):
                    poster_label.setPixmap(pixmap.scaled(455, 650, Qt.KeepAspectRatio))
                else:
                    self.logger.error(f"Error: Failed to load pixmap from data for title_id: {title.title_id}")
                    poster_label.setPixmap(QPixmap("static/no_image.png").scaled(455, 650, Qt.KeepAspectRatio))
            else:
                poster_label.setPixmap(QPixmap("static/no_image.png").scaled(455, 650, Qt.KeepAspectRatio))

            title_layout.addWidget(poster_label)

            # Информация о тайтле справа
            title_browser.setFixedSize(455, 650)
            html_content = self.get_title_html(title, show_description=True, show_more_link=False)
            title_browser.setHtml(html_content)

            # Добавляем title_browser в layout
            title_layout.addWidget(title_browser)
            return title_layout

        elif show_list or show_franchise:
            self.logger.debug(
                f"Создаем title_browser для {'show_list' if show_list else 'show_franchise'} берем title_id: {title.title_id}")
            title_browser.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            title_browser.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            title_browser.setStyleSheet(
                """
                text-align: right;
                border: 1px solid #444;
                width: 100%;
                height: 100%;
                position: relative;
                text-shadow: 1px 1px 2px #FFF;  /* Тень для выделения текста */
                background: rgba(255, 255, 0, 0.5);  /* Полупрозрачный желтый фон */
                """
            )
            html_content = self.get_title_html(title, show_text_list=True)
            title_browser.setHtml(html_content)
            return title_browser

        else:
            self.logger.debug(f"Создаем title_browser для title_id: {title.title_id}")
            title_browser.setFixedSize(455, 650)  # Размер плитки
            html_content = self.get_title_html(title, show_description, show_more_link=True)
            title_browser.setHtml(html_content)
            return title_browser

    def get_title_html(self, title, show_description=False, show_more_link=False, show_text_list=False):
        """Генерирует HTML для отображения информации о тайтле."""
        poster_html = self.generate_poster_html(title, need_background=True) if show_more_link else f"background-image: url('static/background.png');"
        if show_text_list:
            year_html = self.generate_year_html(title,show_text_list=True)
            body_html = f'''
        <p class="header_p">{title.title_id} | {year_html}</p>
        <div class="header">
            <a href="display_info/{title.title_id}">{title.name_en} ({title.name_ru})</a>
        </div>
        '''
        else:
            reload_html = self.generate_reload_button_html(title.title_id)
            rating_html = self.generate_rating_html(title)
            show_more_html = self.generate_show_more_html(title.title_id) if show_more_link else ""
            announce_html = self.generate_announce_html(title)
            status_html = self.generate_status_html(title)
            description_html = self.generate_description_html(title) if show_description else ""
            genres_html = self.generate_genres_html(title)
            year_html = self.generate_year_html(title)
            type_html = self.generate_type_html(title)
            episodes_html = self.generate_episodes_html(title)
            torrents_html = self.generate_torrents_html(title)
            # TODO: fix empty line:
            empty_line = f'<br />'
            body_html = f'''
                <div class="reload">{reload_html}
                    <span class="header_span">{rating_html}</span>
                </div>
                <div>
                    <p class="header">{title.name_en}</p>
                    <p class="header">{title.name_ru}</p>
                    <p class="header">{show_more_html}</p>
                    <div>
                        {announce_html}
                        {status_html}
                        {description_html}
                        {genres_html}
                        {year_html}
                        {type_html}
                    </div>
                    <div>
                        {episodes_html}
                    </div>
                    <div>
                        <p class="header_p">Torrents:</p>
                        {torrents_html}
                    </div>
                </div>
                <div>
                    {empty_line * 6}
                </div>
            '''

        # Генерируем полный HTML
        html_content = f"""
        <html>
            <head>
                <style>
                    html, body {{
                        width: 100%;
                        height: 100%;
                        margin: 0; /* Убираем отступы */
                        padding: 0;
                    }}

                    body {{
                        {poster_html}
                        background-color: rgb(240, 240, 240); /* Светлее, чем #999 */
                        font-size: 12pt;
                        text-align: right;
                        color: #000;
                        font-weight: bold;
                        padding: 20px;
                        border: 1px solid #444;
                        margin: 10px;
                        width: 100%;
                        height: 100%;
                        position: relative;
                    }}
 
                    /* Общие стили для текстовых элементов */
                    h3, p, ul, li {{
                        margin: 5px 0;
                        text-shadow: 1px 1px 2px #FFF;  /* Тень для выделения текста */
                        background: rgba(255, 255, 0, 0.5);  /* Полупрозрачный желтый фон */
                        padding: 3px 6px;
                        border-radius: 3px;
                        display: inline-block;  
                        -webkit-user-select: none;  /* Добавляем для Qt */
                        user-select: none;
                        text-align: right;  /* Выравнивание текста по левому краю */
                        line-height: 0.9;  /* Увеличенный межстрочный интервал */
                        margin-left: 100px;
                    }}
                    
                    .reload {{
                        text-align: left;
                        margin-left: -50px;
  
                    }}
                    
                    .header_episodes {{
                        text-align: left;
                        background: rgba(255, 255, 0, 0.5);  /* Полупрозрачный желтый фон */
                    }}
                    
                    .episodes {{
                        text-align: left;
                        background: rgba(255, 255, 0, 0.5);  /* Полупрозрачный желтый фон */
                    }}
                    
                    .header_span {{
                        text-align: right;
                        background: rgba(255, 255, 0, 0.5);  /* Полупрозрачный желтый фон */
                    }}
              
                    /* Специальные стили для заголовка */
                    .header {{
                        font-size: 29pt;
                        text-shadow: 1px 1px 2px #FFF;
                        display: inline-block;
                        margin-bottom: 15px;
                        line-height: 0.9;
                        padding: 5px 8px;
                        background: rgba(255, 255, 0, 0.4)
                    }}
                
                    /* Специальные стили для ссылок */
                    a {{
                        text-decoration: none;
                        padding: 2px 4px;
                        border-radius: 3px;
                        -webkit-user-select: none;  /* Добавляем для Qt */
                        user-select: none;
                    }}
                
                    a:link, a:visited {{
                        color: #000;
                        text-shadow: 1px 1px 2px #FFF;

                    }}
                
                    a:active {{
                        color: #FFF7D6;
                        background: rgba(0, 0, 0, 0.7);
                        text-decoration: underline;
                    }}
                
                    /* Стили для списков */
                    ul {{
                        padding-left: 20px;
                        list-style-position: inherit;
                        margin-right: 15px;
                    }}
                
                    li {{
                        margin-bottom: 8px;
                        text-align: left;
                        line-height: 0.8;
                        margin-left: 50px;
                    }}
                    
                    div {{
                        padding-top: 10px;
                        padding-bottom: 10px;
                    }}
                
                    /* Стиль для активного состояния - используем :active вместо :hover */
                    h3:active, p:active, li:active {{
                        background: rgba(255, 255, 255, 0.2);
                    }}
                
                    .header:active {{
                        background: rgba(0, 0, 0, 0.8);
                        color: #FFE55C;
                    }}
                </style>
            </head>
            <body>{body_html}</body> 
        </html>
        """
        return html_content

    def generate_reload_button_html(self, title_id):
        """Generates HTML to display reload button"""
        image_base64 = self.prepare_generate_poster_html(7)
        # TODO: fix blank spase
        blank_spase = self.blank_spase

        reload_link = f'<a href="reload_info/{title_id}" title="Reload title"><img src="data:image/png;base64,{image_base64}" /></a>{blank_spase*16}'
        return reload_link

    def generate_show_more_html(self, title_id):
        """Generates HTML to display 'show more' link"""
        return f'<a href=display_info/{title_id}>Подробнее</a>'

    def generate_rating_html(self, title):
        """Generates HTML to display ratings and allows updating"""
        ratings = self.db_manager.get_rating_from_db(title.title_id)
        rating_star_images = []
        poster_base64_full = self.prepare_generate_poster_html(4)
        poster_base64_blank = self.prepare_generate_poster_html(3)
        if ratings:
            rating_name = ratings.rating_name
            rating_value = ratings.rating_value
            for i in range(5):
                if i < rating_value:
                    rating_star_images.append(
                        f'<a href="set_rating/{title.title_id}/{rating_name}/{i + 1}"><img src="data:image/png;base64,{poster_base64_full}" /></a>')
                else:
                    rating_star_images.append(
                        f'<a href="set_rating/{title.title_id}/{rating_name}/{i + 1}"><img src="data:image/png;base64,{poster_base64_blank}" /></a>')
        else:
            rating_name = 'CMERS'
            for i in range(5):
                poster_base64 = self.prepare_generate_poster_html(3)
                rating_star_images.append(f'<a href="set_rating/{title.title_id}/{rating_name}/{i + 1}"><img src="data:image/png;base64,{poster_base64}" /></a>')

        # TODO: fix blank spase
        blank_spase = self.blank_spase
        rating_value = ''.join(rating_star_images)
        watch_html = self.generate_watch_history_html(title.title_id)
        need_to_see_html = self.generate_nee_to_see_html((title.title_id))
        return f'{watch_html}{blank_spase}{title.title_id}{blank_spase}{need_to_see_html}{blank_spase*4}{rating_name}:{blank_spase}{rating_value}'

    def generate_download_history_html(self, title_id, torrent_id):
        """Generates HTML to display download history"""
        image_base64_green = self.prepare_generate_poster_html(9)
        image_base64_red = self.prepare_generate_poster_html(8)
        # TODO: fix it later
        user_id = self.user_id

        if torrent_id:
            _, is_download = self.db_manager.get_history_status(user_id, title_id, torrent_id=torrent_id)
            self.logger.debug(
                f"user_id/title_id/torrent_id: {user_id}/{title_id}/{torrent_id} Status:{is_download}")
            if is_download:
                return f'<a href="set_download_status/{user_id}/{title_id}/{torrent_id}" title="Set download status"><img src="data:image/png;base64,{image_base64_green}" alt="Set download status" /></a>'
            return f'<a href="set_download_status/{user_id}/{title_id}/{torrent_id}" title="Set download status"><img src="data:image/png;base64,{image_base64_red}" alt="Set download status" /></a>'

    def generate_watch_all_episodes_html(self, title_id, episode_ids):
        """Generates HTML to display watch history"""
        image_base64_watched = self.prepare_generate_poster_html(6)
        image_base64_blank = self.prepare_generate_poster_html(5)
        # TODO: fix it later
        user_id = self.user_id

        all_watched = self.db_manager.get_all_episodes_watched_status(user_id, title_id)
        self.logger.debug(f"user_id/title_id/episode_ids: {user_id}/{title_id}/{episode_ids} Status:{all_watched}")
        if all_watched:
            return f'<a href="set_watch_all_episodes_status/{user_id}/{title_id}/{episode_ids}" title="Set watch all episodes"><img src="data:image/png;base64,{image_base64_watched}" alt="Set watch all episodes" /></a>'
        return f'<a href="set_watch_all_episodes_status/{user_id}/{title_id}/{episode_ids}" title="Set watch all episodes"><img src="data:image/png;base64,{image_base64_blank}" alt="Set watch all episodes" /></a>'

    def generate_nee_to_see_html(self, title_id):
        """Generates HTML to display watch history"""
        image_base64_watched = self.prepare_generate_poster_html(11)
        image_base64_blank = self.prepare_generate_poster_html(10)
        # TODO: fix it later
        user_id = self.user_id

        if title_id:
            is_need_to_see = self.db_manager.get_need_to_see(user_id, title_id)
            self.logger.debug(f"user_id/title_id : {user_id}/{title_id} Status:{is_need_to_see}")
            if is_need_to_see:
                return f'<a href="set_need_to_see/{user_id}/{title_id}" title="Set need to see"><img src="data:image/png;base64,{image_base64_watched}" alt="Need to see" /></a>'
            return f'<a href="set_need_to_see/{user_id}/{title_id}" title="Set need to see"><img src="data:image/png;base64,{image_base64_blank}" alt="Need to see" /></a>'

    def generate_watch_history_html(self, title_id, episode_id=None):
        """Generates HTML to display watch history"""
        image_base64_watched = self.prepare_generate_poster_html(6)
        image_base64_blank = self.prepare_generate_poster_html(5)
        # TODO: fix it later
        user_id = self.user_id

        if episode_id or title_id:
            is_watched, _ = self.db_manager.get_history_status(user_id, title_id, episode_id=episode_id)
            self.logger.debug(f"user_id/title_id/episode_id: {user_id}/{title_id}/{episode_id} Status:{is_watched}")
            if is_watched:
                return f'<a href="set_watch_status/{user_id}/{title_id}/{episode_id}" title="Set watch status"><img src="data:image/png;base64,{image_base64_watched}" alt="Set watch status" /></a>'
            return f'<a href="set_watch_status/{user_id}/{title_id}/{episode_id}" title="Set watch status"><img src="data:image/png;base64,{image_base64_blank}" alt="Set watch status" /></a>'

    def generate_play_all_html(self, title):
        """Generates M3U Playlist link"""
        self.stream_video_url = title.host_for_player
        playlist = self.playlists.get(title.title_id)
        if playlist:
            sanitized_title = playlist['sanitized_title']
            discovered_links = playlist['links']
            if discovered_links:
                filename = self.playlist_manager.save_playlist([sanitized_title], discovered_links,
                                                               self.stream_video_url)

                self.logger.debug(
                    f"Playlist for title {sanitized_title} was sent for saving with filename: {filename}.")
                return f'<a href="play_all/{title.title_id}/{filename}">Play all</a>'
            else:
                self.logger.error(f"No links found for title {sanitized_title}, skipping saving.")
                return "No playlist available"
        else:
            return "No playlist available"

    def generate_torrents_html(self, title):
        """Generates HTML to display a list of torrents for a title."""
        self.torrent_data = {}
        # TODO: fix blank spase
        blank_spase = self.blank_spase
        torrents = self.db_manager.get_torrents_from_db(title.title_id)

        if not torrents:
            return "<p>Torrents not available</p>"

        torrents_html = "<ul>"
        for torrent in torrents:
            torrent_quality = torrent.quality if torrent.quality else "Unknown Quality"
            torrent_size = torrent.size_string if torrent.size_string else "Unknown Size"
            torrent_link = torrent.url if torrent.url else "#"
            download_html = self.generate_download_history_html(title.title_id, torrent.torrent_id)
            torrents_html += f'<li><a href="{torrent_link}" target="_blank">{torrent_quality} ({torrent_size})</a>{blank_spase*4}{download_html}</li>'
            self.torrent_data = torrent.title_id, title.code, torrent.torrent_id
        torrents_html += "</ul>"

        return torrents_html

    def prepare_generate_poster_html(self, title_id):
        poster_data = self.get_poster_or_placeholder(title_id)

        try:
            pixmap = QPixmap()
            if not pixmap.loadFromData(poster_data):
                self.logger.error(f"Error: Failed to load image data for title_id: {title_id}")

                return None

            # Используем QBuffer для сохранения в байтовый массив
            byte_array = QByteArray()
            buffer = QBuffer(byte_array)
            buffer.open(QBuffer.WriteOnly)
            if not pixmap.save(buffer, 'PNG'):
                self.logger.error(f"Error: Failed to save image as PNG for title_id: {title_id}")
                return None

            # Преобразуем данные в Base64
            poster_base64 = base64.b64encode(byte_array.data()).decode('utf-8')
            return poster_base64

        except Exception as e:
            self.logger.error(f"Error processing poster for title_id: {title_id} - {e}")
            return None

    def generate_poster_html(self, title, need_image=False, need_background=False):
        """Generates HTML for the poster in Base64 format or returns a placeholder."""
        # Попытка получить постер из базы данных
        poster_base64 = self.prepare_generate_poster_html(title.title_id)
        try:
            if need_image:
                return f'<img src="data:image/png;base64,{poster_base64}" alt="{title.title_id}.{title.code}" style=\"float: left; margin-right: 20px;\"" />'
            elif need_background:
                return f'background-image: url("data:image/png;base64,{poster_base64}");'

            # TODO: fix this return
            return f"background-image: url('static/background.png');"
        except Exception as e:
            self.logger.error(f"Error processing poster for title_id: {title.title_id} - {e}")
            # TODO: fix this return
            return f"background-image: url('static/background.png');"

    def generate_genres_html(self, title):
        """Генерирует HTML для отображения жанров."""
        if hasattr(title, 'genre_names') and title.genre_names:
            try:
                # Используем жанры в виде списка строк
                genres_list = title.genre_names
                genres = ', '.join(genres_list) if genres_list else "Жанры отсутствуют"
            except Exception as e:
                self.logger.error(f"Ошибка при генерации HTML жанров: {e}")
                genres = "Жанры отсутствуют"
        else:
            genres = "Жанры отсутствуют"

        return f"""<p>Жанры: {genres}</p>"""

    def generate_announce_html(self, title):
        """Генерирует HTML для отображения анонса."""
        title_announced = title.announce if title.announce else 'Анонс отсутствует'
        return f"""<p>Анонс: {title_announced}</p>"""

    def generate_status_html(self, title):
        """Генерирует HTML для отображения статуса."""
        title_status = title.status_string if title.status_string else "Статус отсутствует"
        return f"""<p>Статус: {title_status}</p>"""

    def generate_description_html(self, title):
        """Генерирует HTML для отображения описания, если оно есть."""
        if title.description:
            return f"""<p>Описание: {title.description}</p>"""
        else:
            return ""

    def generate_year_html(self, title, show_text_list=False):
        """Генерирует HTML для отображения года выпуска."""
        title_year = title.season_year if title.season_year else "Год отсутствует"
        if show_text_list:
            return f"""{title_year}"""
        else:
            return f"""<p>Год выпуска: {title_year}</p>"""

    def generate_type_html(self, title):
        """Генерирует HTML для отображения типа аниме."""
        title_type = title.type_full_string if title.type_full_string else ""
        return f"""<p>{title_type}</p>"""

    def generate_episodes_html(self, title):
        """Генерирует HTML для отображения информации об эпизодах на основе выбранного качества."""
        selected_quality = self.quality_dropdown.currentText()
        self.discovered_links = []
        self.sanitized_titles = []
        # TODO: fix blank space
        blank_space = self.blank_spase
        episode_ids = []
        episode_links = []
        for i, episode in enumerate(title.episodes):
            episode_name = episode.name if episode.name else f'Серия {i + 1}'
            link = None
            if selected_quality == 'fhd':
                link = episode.hls_fhd
            elif selected_quality == 'hd':
                link = episode.hls_hd
            elif selected_quality == 'sd':
                link = episode.hls_sd
            else:
                self.logger.error(f"Неизвестное качество: {selected_quality}")
                continue
            if link:
                episode_ids.append(episode.episode_id)
                episode_links.append((episode.episode_id, episode_name, link))
            else:
                self.logger.warning(f"Нет ссылки для эпизода '{episode_name}' для выбранного качества '{selected_quality}'")
        watch_all_episodes_html = self.generate_watch_all_episodes_html(title.title_id, episode_ids)
        play_all_html = self.generate_play_all_html(title)
        if episode_links:
            episodes_html = f'<p class="header_episodes">{watch_all_episodes_html}{blank_space * 4}Episodes:{blank_space * 6}{play_all_html}</p><ul>'
            for episode_id, episode_name, link in episode_links:
                watched_html = self.generate_watch_history_html(title.title_id, episode_id=episode_id)
                episodes_html += f'<p class="episodes">{watched_html}{blank_space * 4}<a href="{link}" target="_blank">{episode_name}</a></p>'
                self.discovered_links.append(link)
        else:
            episodes_html = f'<p class="header_episodes">Episodes:{blank_space * 6}{play_all_html}</p><ul>'
            episodes_html += f'<li>Нет доступных ссылок для выбранного качества: {selected_quality}</li>'
        episodes_html += "</ul>"
        # Добавляем имя эпизода в sanitized_titles
        sanitized_name = self.sanitize_filename(title.code)
        self.sanitized_titles.append(sanitized_name)
        # Обновляем плейлисты, если есть обнаруженные ссылки
        if self.discovered_links:
            self.playlists[title.title_id] = {
                'links': self.discovered_links,
                'sanitized_title': sanitized_name
            }
        self.logger.debug(f"discovered_links: {len(self.discovered_links)}")
        self.logger.debug(f"sanitized_name: {sanitized_name}")
        return episodes_html

    def invoke_database_save(self, title_list):
        self.logger.debug(f"Processing title data: {title_list}")
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
                        # Добавляем данные о дне и title_id в parsed_data
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

    def on_link_click(self, url):
        try:
            link = url.toString()
            if link.startswith('display_info/'):
                title_id = int(link.split('/')[1])
                QTimer.singleShot(100, lambda: self.display_info(title_id))
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

            # TODO: add link capture for "need_to_see"
            elif link.startswith('set_need_to_see/'):
                parts = link.split('/')
                if len(parts) >= 3:
                    user_id = int(parts[1])
                    title_id = int(parts[2])
                    self.logger.debug(f"Setting user:{user_id} need to see status for title_id: {title_id}")
                    current_status = self.db_manager.get_need_to_see(user_id=user_id, title_id=title_id)
                    current_watched_status = current_status
                    new_watch_status = not current_watched_status
                    self.logger.debug(f"Setting watch status for user_id: {user_id}, title_id: {title_id}, status: {new_watch_status}")
                    self.db_manager.save_need_to_see(user_id=user_id, title_id=title_id, need_to_see=new_watch_status)
                    QTimer.singleShot(100, lambda: self.display_info(title_id))
                else:
                    self.logger.error(f"Invalid set_need_to_see/ link structure: {link}")

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
                # Получаем title_id и filename из ссылки и вызываем play_playlist_wrapper
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
        if file_name is None:
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

