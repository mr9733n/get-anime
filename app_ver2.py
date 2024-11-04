import ast
import json
import logging
import os
import platform
import re
import subprocess
import time
from datetime import datetime, timedelta

from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLineEdit, QLabel, QComboBox, QGridLayout, QScrollArea, QTextBrowser, QSizePolicy
)
from PyQt5.QtCore import Qt, QByteArray, QBuffer, QUrl, QTimer, QRunnable, QThreadPool, pyqtSlot, QObject, pyqtSignal
from PyQt5.QtGui import QPixmap
from core.database_manager import Title, Schedule, Episode, Torrent
from sqlalchemy.orm import joinedload
import base64

from core.database_manager import Poster
from utils.config_manager import ConfigManager
from utils.api_client import APIClient
from utils.poster_manager import PosterManager
from utils.playlist_manager import PlaylistManager
from utils.torrent_manager import TorrentManager


class CreateTitleBrowserTask(QRunnable):
    def __init__(self, app, title, row, column, show_description=False, show_one_title=False):
        super().__init__()
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


class AnimePlayerAppVer2(QWidget):
    add_title_browser_to_layout = pyqtSignal(QTextBrowser, int, int)
    def __init__(self, database_manager):
        super().__init__()
        self.thread_pool = QThreadPool()  # Пул потоков для управления задачами
        self.thread_pool.setMaxThreadCount(2)
        self.add_title_browser_to_layout.connect(self.on_add_title_browser_to_layout)
        self.playlist_filename = None
        self.play_playlist_button = None
        self.save_playlist_button = None
        self.current_data = None
        self.display_button = None
        self.discovered_links = []
        self.current_link = None
        self.poster_container = None
        self.scroll_area = None
        self.posters_layout = None
        self.day_buttons = None
        self.days_of_week = None
        self.refresh_button = None
        self.quality_dropdown = None
        self.quality_label = None
        self.random_button = None
        self.display_button = None
        self.title_search_entry = None
        self.sanitized_titles = []
        self.title_names = []
        self.playlists = {}
        self.titles_batch_size = 4  # Количество тайтлов, которые загружаются за раз
        self.current_offset = 0     # Текущий смещение для выборки тайтлов
        self.total_titles = []

        self.logger = logging.getLogger(__name__)

        self.logger.debug("Initializing AnimePlayerApp Version 2")

        self.cache_file_path = "poster_cache.txt"
        self.config_manager = ConfigManager('config.ini')

        """Loads the configuration settings needed by the application."""
        self.stream_video_url = self.config_manager.get_setting('Settings', 'stream_video_url')
        self.base_url = self.config_manager.get_setting('Settings', 'base_url')
        self.api_version = self.config_manager.get_setting('Settings', 'api_version')
        self.torrent_save_path = "torrents/"  # Ensure this is set correctly
        self.video_player_path, self.torrent_client_path = self.setup_paths()

        # Initialize TorrentManager with the correct paths
        self.torrent_manager = TorrentManager(
            torrent_save_path=self.torrent_save_path,
            torrent_client_path=self.torrent_client_path
        )
        # Corrected debug logging of paths using setup values
        self.pre = "https://"
        self.logger.debug(f"Video Player Path: {self.video_player_path}")
        self.logger.debug(f"Torrent Client Path: {self.torrent_client_path}")

        # Initialize other components
        self.api_client = APIClient(self.base_url, self.api_version)
        self.poster_manager = PosterManager()
        self.playlist_manager = PlaylistManager()
        self.poster_manager = PosterManager(
            save_callback=self.save_poster_to_db,
        )
        self.db_manager = database_manager
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
        self.setWindowTitle('Anime Player v2')
        self.setGeometry(100, 100, 980, 750)

        # Основной вертикальный layout
        main_layout = QVBoxLayout()

        # Верхняя часть контролов
        controls_layout = QHBoxLayout()

        # Общий стиль для кнопок
        button_style = """
            QPushButton {
                background-color: #4CAF50;  /* Зеленый фон */
                border: none;
                color: white;
                padding: 6px 12px;
                text-align: center;
                font-size: 14px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """

        # Поле для поиска
        self.title_search_entry = QLineEdit(self)
        self.title_search_entry.setPlaceholderText('TITLE NAME')
        self.title_search_entry.setMinimumWidth(100)
        self.title_search_entry.setMaximumWidth(150)
        self.title_search_entry.setStyleSheet("""
            QLineEdit {
                background-color: #f0f0f0;
                border: 1px solid #ccc;
                border-radius: 4px;
                padding: 4px;
                font-size: 14px;
            }
        """)
        controls_layout.addWidget(self.title_search_entry)

        # Кнопка "Find"
        self.display_button = QPushButton('FIND', self)
        self.display_button.setStyleSheet(button_style)
        self.display_button.clicked.connect(self.get_search_by_title)
        controls_layout.addWidget(self.display_button)

        # Дни недели
        self.days_of_week = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]
        self.day_buttons = []

        for i, day in enumerate(self.days_of_week):
            button = QPushButton(day, self)
            button.clicked.connect(
                lambda checked, i=i: self.display_titles_for_day(i))
            button.setStyleSheet(button_style)
            controls_layout.addWidget(button)
            self.day_buttons.append(button)

        # Добавляем контролы в основной layout
        main_layout.addLayout(controls_layout)

        # Кнопка "Random"
        self.random_button = QPushButton('RANDOM', self)
        self.random_button.setStyleSheet(button_style)
        self.random_button.clicked.connect(self.get_random_title)
        controls_layout.addWidget(self.random_button)

        # Метка "QLTY:"
        self.quality_label = QLabel('QLTY:', self)
        self.quality_label.setStyleSheet("""
            QLabel {
                font-size: 14px;
                color: #333;
            }
        """)
        controls_layout.addWidget(self.quality_label)

        # Выпадающий список качества
        self.quality_dropdown = QComboBox(self)
        self.quality_dropdown.addItems(['fhd', 'hd', 'sd'])
        self.quality_dropdown.setStyleSheet("""
            QComboBox {
                background-color: #f0f0f0;
                border: 1px solid #ccc;
                border-radius: 4px;
                padding: 4px;
                font-size: 14px;
            }
            QComboBox QAbstractItemView {
                background-color: white;
                selection-background-color: #4CAF50;
            }
        """)
        controls_layout.addWidget(self.quality_dropdown)

        # Кнопка "Refresh"
        self.refresh_button = QPushButton('REFRESH', self)
        self.refresh_button.setStyleSheet(button_style)
        self.refresh_button.clicked.connect(self.update_quality_and_refresh)
        controls_layout.addWidget(self.refresh_button)

        # Кнопка "Save Playlist"
        self.save_playlist_button = QPushButton('SAVE', self)
        self.save_playlist_button.setStyleSheet(button_style)
        self.save_playlist_button.clicked.connect(self.save_playlist_wrapper)  # Подключаем к обертке
        controls_layout.addWidget(self.save_playlist_button)

        # Кнопка "Play Playlist"
        self.play_playlist_button = QPushButton('PLAY', self)
        self.play_playlist_button.setStyleSheet(button_style)
        self.play_playlist_button.clicked.connect(self.play_playlist_wrapper)  # Подключаем к обертке
        controls_layout.addWidget(self.play_playlist_button)

        # Устанавливаем основной layout для виджета
        self.setLayout(main_layout)

        # Динамическая часть для отображения постеров
        self.posters_layout = QGridLayout()
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)

        # Контейнер для отображения постеров
        self.poster_container = QWidget()
        self.poster_container.setLayout(self.posters_layout)

        self.scroll_area.setWidget(self.poster_container)
        main_layout.addWidget(self.scroll_area)
        # Устанавливаем основной layout для окна
        self.setLayout(main_layout)

        # Добавляем кнопку "Загрузить еще" для ленивой загрузки
        self.load_more_button = QPushButton('LOAD MORE', self)
        self.load_more_button.setStyleSheet(button_style)
        self.load_more_button.clicked.connect(self.load_more_titles)
        self.layout().addWidget(self.load_more_button)

        #  Load 4 titles on start from DB
        self.display_titles()

    def update_quality_and_refresh(self, event=None):
        selected_quality = self.quality_dropdown.currentText()
        data = self.current_data

        if not data:
            error_message = "No data available. Please fetch data first."
            self.logger.error(error_message)
            return

        self.logger.debug(f"DATA: {data}")

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

    #
    # Fixme: Very long operation. For DEBUG use only!
    #
    def display_titles(self):
        """Отображение первых тайтлов при старте."""
        # Загружаем первую партию тайтлов
        titles = self.get_titles_from_db(show_all=True, batch_size=self.titles_batch_size, offset=self.current_offset)

        # Обновляем offset для следующей загрузки
        self.current_offset += self.titles_batch_size

        # Сохраняем загруженные тайтлы в список для доступа позже
        self.total_titles.extend(titles)

        # Отображаем тайтлы в UI
        num_columns = 2  # Количество колонок для отображения
        for index, title in enumerate(titles):
            row = (index + self.current_offset - self.titles_batch_size) // num_columns
            column = index % num_columns
            self.add_title_to_layout(title, row, column)

    def add_title_to_layout(self, title, row, column):
        """Создает виджет для тайтла и добавляет его в макет."""
        title_browser = self.create_title_browser(title, show_description=False, show_one_title=False)
        self.posters_layout.addWidget(title_browser, row, column)

    def load_more_titles(self):
        """Загружает и отображает следующие тайтлы."""
        titles = self.get_titles_from_db(show_all=True, batch_size=self.titles_batch_size, offset=self.current_offset)

        # Если тайтлы закончились, прекращаем загрузку
        if not titles:
            self.logger.info("Больше нет тайтлов для загрузки.")
            return

        # Обновляем offset для следующей загрузки
        self.current_offset += self.titles_batch_size

        # Сохраняем загруженные тайтлы в список для доступа позже
        self.total_titles.extend(titles)

        # Отображаем новые тайтлы в UI
        num_columns = 2  # Количество колонок для отображения
        for index, title in enumerate(titles):
            row = (index + self.current_offset - self.titles_batch_size) // num_columns
            column = index % num_columns
            self.add_title_to_layout(title, row, column)

    def start_create_title_task(self, title, row, column):
        task = CreateTitleBrowserTask(self, title, row, column, show_description=False, show_one_title=False)
        self.thread_pool.start(task)

    def display_info(self, title_id):
        self.clear_previous_posters()
        session = self.db_manager.session
        try:
            # Загружаем тайтл и загружаем связанные эпизоды
            title = (
                session.query(Title)
                .filter(Title.title_id == title_id)
                .one_or_none()  # Либо .first() для первого результата
            )
        except Exception as e:
            self.logger.error(f"Ошибка при загрузке тайтлов: {e}")
            return

        if title is None:
            self.logger.error(f"Title with title_id {title_id} not found in the database.")
            return

        # Обновление UI с загруженными данными
        title_layout = self.create_title_browser(title, show_description=True, show_one_title=True)
        self.posters_layout.addLayout(title_layout, 0, 0, 1, 2)

    def display_titles_for_day(self, day_of_week):
        # Очистка предыдущих постеров
        self.clear_previous_posters()

        session = self.db_manager.session
        titles = []

        if session is not None:
            try:
                # Проверка наличия тайтлов в базе данных для данного дня недели
                titles = self.get_titles_from_db(day_of_week)

                # Проверка, нужно ли обновить расписание (например, устаревшие данные)
                if not self.is_schedule_up_to_date(titles, day_of_week):
                    self.logger.info(f"Расписание для дня {day_of_week} устарело, обновляем...")
                    titles = self.update_schedule_for_day(day_of_week)

            except Exception as e:
                self.logger.error(f"Ошибка при загрузке тайтлов из базы данных: {e}")

        # Если в базе данных нет данных, то получаем их через get_schedule()
        if not titles:
            try:
                data = self.get_schedule(day_of_week)
                self.logger.debug(f"Получены данные с сервера: {data}")
                # Обработка данных и добавление их в базу данных
                if data is True:
                    # После сохранения данных в базе получаем их снова
                    titles = self.get_titles_from_db(day_of_week)
            except Exception as e:
                self.logger.error(f"Ошибка при получении тайтлов через get_schedule: {e}")
                return

        # Обновление UI с загруженными данными
        num_columns = 2  # Задайте количество колонок для отображения
        for index, title in enumerate(titles):
            title_browser = self.create_title_browser(title, show_description=False, show_one_title=False)
            self.posters_layout.addWidget(title_browser, index // num_columns, index % num_columns)

        # Проверяем и обновляем расписание после отображения
        self.check_and_update_schedule_after_display(day_of_week, titles)

    def check_and_update_schedule_after_display(self, day_of_week, current_titles):
        """Проверяет наличие обновлений в расписании и обновляет базу данных, если необходимо."""
        try:
            # Получаем актуальные данные из API
            new_data = self.get_schedule(day_of_week)
            if new_data:
                for day_info in new_data:
                    day = day_info.get("day")
                    if day == day_of_week:
                        new_titles = day_info.get("list", [])

                        # Проверяем, изменилось ли количество эпизодов или другие данные
                        if len(new_titles) != len(current_titles):
                            self.logger.info(
                                f"Обнаружены изменения в расписании для дня {day_of_week}, обновляем базу данных...")
                            self.invoke_database_save(new_titles)
                        else:
                            # Дополнительная проверка на изменения в данных
                            for new_title, current_title in zip(new_titles, current_titles):
                                if new_title.get('id') != current_title.title_id or \
                                        new_title.get('name') != current_title.name_en or \
                                        new_title.get('announce') != current_title.announce:
                                    self.logger.info(
                                        f"Обнаружены изменения в тайтле {new_title.get('name')}, обновляем базу данных...")
                                    self.invoke_database_save([new_title])
        except Exception as e:
            self.logger.error(f"Ошибка при проверке обновлений расписания: {e}")

    def is_schedule_up_to_date(self, titles, day_of_week):
        """Проверяет, актуально ли расписание в базе данных."""
        # Простая проверка: если расписание отсутствует или если с момента последнего обновления прошло слишком много времени
        if not titles:
            return False

        last_updated_time = max(title.last_updated for title in titles)
        current_time = datetime.utcnow()
        delta = current_time - last_updated_time
        # Например, обновлять расписание, если прошло больше 24 часов с момента последнего обновления
        if delta > timedelta(hours=24):
            return False

        return True

    def get_titles_from_db(self, day_of_week=None, show_all=False, batch_size=None, offset=0):
        """Получает список тайтлов для определенного дня недели или все тайтлы, если указано show_all."""
        session = self.db_manager.session
        titles = []

        if session is not None:
            try:
                query = session.query(Title).options(joinedload(Title.episodes))
                if not show_all:
                    query = query.join(Schedule).filter(Schedule.day_of_week == day_of_week)

                if batch_size:
                    query = query.offset(offset).limit(batch_size)

                titles = query.all()

            except Exception as e:
                self.logger.error(f"Ошибка при загрузке тайтлов из базы данных: {e}")

        return titles

    def clear_previous_posters(self):
        """Удаляет все предыдущие постеры из сетки."""
        for i in reversed(range(self.posters_layout.count())):
            widget_to_remove = self.posters_layout.itemAt(i).widget()
            if widget_to_remove is not None:
                widget_to_remove.setParent(None)

    def create_title_browser(self, title, show_description=False, show_one_title=False):
        """Создает элемент интерфейса для отображения информации о тайтле."""
        self.logger.debug("Начинаем создание title_browser...")
        if show_one_title:
            # Create a new horizontal layout for displaying the title details
            title_layout = QHBoxLayout()
            self.logger.debug(f"Создаем title_browser для title_id: {title.title_id}")

            # Poster on the left
            poster_label = QLabel(self)
            poster_data = self.db_manager.get_poster_blob(title.title_id)

            if not poster_data:
                # Если постер не найден, попробуем получить заглушку с title_id=-1
                self.logger.warning(f"Warning: No poster data for title_id: {title.title_id}, using placeholder.")
                poster_data = self.db_manager.get_poster_blob(-1)

            if poster_data:
                pixmap = QPixmap()
                if pixmap.loadFromData(poster_data):
                    poster_label.setPixmap(pixmap.scaled(455, 650, Qt.KeepAspectRatio))
                else:
                    self.logger.error(f"Error: Failed to load pixmap from data for title_id: {title.title_id}")
                    # Используем статическую картинку-заглушку в случае, если даже загрузка pixmap не удалась
                    poster_label.setPixmap(QPixmap("static/no_image.png").scaled(455, 650, Qt.KeepAspectRatio))
            else:
                # Если данные постера отсутствуют даже для заглушки, используем статическое изображение
                poster_label.setPixmap(QPixmap("static/no_image.png").scaled(455, 650, Qt.KeepAspectRatio))

            title_layout.addWidget(poster_label)

            # Title information on the right
            title_browser = QTextBrowser(self)
            title_browser.setPlainText(f"Title: {title.name_en}")
            title_browser.setOpenExternalLinks(True)
            title_browser.setFixedSize(455, 650)  # Set the size of the information browser
            title_browser.setProperty('title_id', title.title_id)

            html_content = self.get_title_html(title, show_description=True, show_more_link=False)
            title_browser.setHtml(html_content)

            # Connect link click event
            title_browser.anchorClicked.connect(self.on_link_click)

            # Add the title information to the layout
            title_layout.addWidget(title_browser)

            return title_layout

        else:
            self.logger.debug(f"Создаем title_browser для title_id: {title.title_id}")
            # Default layout for schedule view
            title_browser = QTextBrowser(self)
            title_browser.setPlainText(f"Title: {title.name_en}")
            title_browser.setOpenExternalLinks(True)
            title_browser.setFixedSize(455, 650)  # Размер плитки
            title_browser.setProperty('title_id', title.title_id)

            html_content = self.get_title_html(title, show_description, show_more_link=True)
            title_browser.setHtml(html_content)
            title_browser.anchorClicked.connect(self.on_link_click)
           # title_browser.mouseDoubleClickEvent(self.display_info(title.title_id))
            return title_browser

    def get_title_html(self, title, show_description=False, show_more_link=False):
        """Генерирует HTML для отображения информации о тайтле."""
        # Получаем данные постера
        poster_html = self.generate_poster_html(title)
        # Декодируем жанры и получаем другие поля
        genres_html = self.generate_genres_html(title)
        announce_html = self.generate_announce_html(title)
        status_html = self.generate_status_html(title)
        show_more_html = self.generate_show_more_html(title) if show_more_link else ""
        description_html = self.generate_description_html(title) if show_description else ""
        year_html = self.generate_year_html(title)
        type_html = self.generate_type_html(title)
        torrents_html = self.generate_torrents_html(title)

        # Добавляем информацию об эпизодах
        episodes_html = self.generate_episodes_html(title)

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
                        background-repeat: no-repeat;
                        background-position: center;
                        background-size: cover;
                        background-attachment: fixed;
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
            <body>
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
                        <p>Эпизоды:</p>
                        {episodes_html}
                    </div>
                    <div>
                        <p>Torrents:</p>
                        {torrents_html}
                    </div>
                </div>
                    <div>
                        <br><br><br><br><br><br><br><br><br>
                    </div>
            </body> 
        </html>
        """
        return html_content

    def generate_show_more_html(self, title):
        """Generates HTML to display 'show more' link"""
        return f'<a href=display_info/{title.title_id}>Подробнее</a>'

    def generate_torrents_html(self, title):
        """Generates HTML to display a list of torrents for a title."""
        torrents = self.db_manager.session.query(Torrent).filter_by(title_id=title.title_id).all()

        if not torrents:
            return "<p>Torrents not available</p>"

        torrents_html = "<ul>"
        for torrent in torrents:
            torrent_quality = torrent.quality if torrent.quality else "Unknown Quality"
            torrent_size = torrent.size_string if torrent.size_string else "Unknown Size"
            torrent_link = torrent.url if torrent.url else "#"
            torrents_html += f'<li><a href="{torrent_link}" target="_blank">{torrent_quality} ({torrent_size})</a></li>'
        torrents_html += "</ul>"
        return torrents_html

    def generate_poster_html(self, title):
        """Generates HTML for the poster in Base64 format or returns a placeholder."""
        # Попытка получить постер из базы данных
        poster_data = self.db_manager.get_poster_blob(title.title_id)

        # Если постер не найден, берем постер-заглушку с title_id=-1
        if not poster_data:
            self.logger.warning(f"Warning: No poster data for title_id: {title.title_id}, using placeholder.")
            poster_data = self.db_manager.get_poster_blob(-1)

        # Если даже заглушка не найдена, возвращаем URL к статическому изображению
        if not poster_data:
            return 'background-image: url("");'

        try:
            pixmap = QPixmap()
            if not pixmap.loadFromData(poster_data):
                self.logger.error(f"Error: Failed to load image data for title_id: {title.title_id}")
                return 'background-image: url("");'

            # Используем QBuffer для сохранения в байтовый массив
            byte_array = QByteArray()
            buffer = QBuffer(byte_array)
            buffer.open(QBuffer.WriteOnly)
            if not pixmap.save(buffer, 'PNG'):
                self.logger.error(f"Error: Failed to save image as PNG for title_id: {title.title_id}")
                return 'background-image: url("");'

            # Преобразуем данные в Base64
            poster_base64 = base64.b64encode(byte_array.data()).decode('utf-8')
            return f'background-image: url("data:image/png;base64,{poster_base64}");'
        except Exception as e:
            self.logger.error(f"Error processing poster for title_id: {title.title_id} - {e}")
            return 'background-image: url("");'

    def generate_genres_html(self, title):
        """Генерирует HTML для отображения жанров."""
        if title.genres:
            try:
                if isinstance(title.genres, bytes):
                    genres_str = title.genres.decode('utf-8')
                else:
                    genres_str = title.genres

                genres_list = ast.literal_eval(genres_str)

                if isinstance(genres_list, str):
                    genres_list = json.loads(genres_list)

                genres = ', '.join(genres_list) if genres_list else "Жанры отсутствуют"
            except (json.JSONDecodeError, ValueError, SyntaxError) as e:
                self.logger.error(f"Ошибка при декодировании жанров: {e}")
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


    def generate_year_html(self, title):
        """Генерирует HTML для отображения года выпуска."""
        title_year = title.season_year if title.season_year else "Год отсутствует"
        return f"""<p>Год выпуска: {title_year}</p>"""


    def generate_type_html(self, title):
        """Генерирует HTML для отображения типа аниме."""
        title_type = title.type_full_string if title.type_full_string else ""
        return f"""<p>{title_type}</p>"""


    def generate_episodes_html(self, title):
        """Генерирует HTML для отображения информации об эпизодах на основе выбранного качества."""
        selected_quality = self.quality_dropdown.currentText()  # Получаем выбранное качество

        # Подготовка HTML для эпизодов
        episodes_html = "<ul>"

        # Очищаем списки для ссылок и заголовков перед заполнением
        self.discovered_links = []
        self.sanitized_titles = []
        for i, episode in enumerate(title.episodes):
            episode_name = episode.name if episode.name else f'Серия {i + 1}'

            # Выбор ссылки на основе выбранного качества
            if selected_quality == 'fhd':
                link = episode.hls_fhd
            elif selected_quality == 'hd':
                link = episode.hls_hd
            elif selected_quality == 'sd':
                link = episode.hls_sd
            else:
                self.logger.error(f"Неизвестное качество: {selected_quality}")
                continue

            # Проверяем, что ссылка существует
            if link:
                episodes_html += f'<li><a href="{link}">{episode_name}</a></li>'
                # Добавляем ссылку в discovered_links
                self.discovered_links.append(link)

            else:
                episodes_html += f'<li>{episode_name} (нет ссылки для качества {selected_quality})</li>'


        episodes_html += "</ul>"
        # Добавляем имя эпизода в sanitized_titles

        sanitized_name = self.sanitize_filename(title.code)
        self.sanitized_titles.append(sanitized_name)

        if self.discovered_links:
            self.playlists[title.title_id] = {
                'links': self.discovered_links,
                'sanitized_title': sanitized_name
            }
        self.logger.debug(f"discovered_links: {self.discovered_links}")
        self.logger.debug(f"sanitized_name: {sanitized_name}")

        return episodes_html


    def invoke_database_save(self, title_list):
        for i, title_data in enumerate(title_list):
            # Обработка постеров
            self.process_poster_links(title_data)
            # Обработка эпизодов
            self.process_episodes(title_data)
            # Обработка торрентов
            self.process_torrents(title_data)
            self.process_titles(title_data)


    def get_random_title(self):
        data = self.api_client.get_random_title()
        if 'error' in data:
            self.logger.error(data['error'])
            return
        self.logger.debug(f"Full response data: {data}")
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
            if 'error' in data:
                self.logger.error(data['error'])
                return None
            if data is not None:
                for day_info in data:
                    day = day_info.get("day")
                    title_list = day_info.get("list")
                    for title in title_list:
                        title_id = title.get('id')
                        if title_id:
                            self.db_manager.save_schedule(day, title_id)

                    self.invoke_database_save(title_list)

            self.current_data = data
            return data  # Возвращаем данные вместо True
        except Exception as e:
            self.logger.error(f"Ошибка при получении расписания: {e}")
            return None

    def get_search_by_title(self):
        search_text = self.title_search_entry.text()
        if not search_text:
            return

        data = self.api_client.get_search_by_title(search_text)
        if 'error' in data:
            self.logger.error(data['error'])
            return

        # Получаем список тайтлов из ответа
        title_list = data.get('list', [])
        if not title_list:
            self.logger.error("No titles found in the response.")
            return
        self.invoke_database_save(title_list)
        # Перебираем каждый тайтл в списке и обрабатываем его
        for title_data in title_list:
            title_id = title_data.get('id')
            if title_id is None:
                self.logger.error("Title ID not found in response.")
                continue

            # Вызываем метод display_info для каждого тайтла
            self.display_info(title_id)

        # Сохраняем текущие данные
        self.current_data = data


    def process_poster_links(self, title_data):
        poster_links = []
        if "posters" in title_data and title_data.get("posters", {}).get("small"):
            poster_url = self.get_poster(title_data)
            if poster_url:
                poster_links.append((title_data['id'], poster_url))
                self.logger.debug(f"Poster url: {poster_url}")

        if poster_links:
            self.poster_manager.write_poster_links(poster_links)


    def save_poster_to_db(self, title_id, poster_blob):
        try:
            # Проверяем, существует ли уже постер для данного title_id
            existing_poster = self.db_manager.session.query(Poster).filter_by(title_id=title_id).first()
            if not existing_poster:
                # Создаем новый объект Poster и добавляем в базу
                new_poster = Poster(title_id=title_id, poster_blob=poster_blob, last_updated=datetime.utcnow())
                self.db_manager.session.add(new_poster)
            else:
                # Обновляем существующий постер
                existing_poster.poster_blob = poster_blob
                existing_poster.last_updated = datetime.utcnow()

            self.db_manager.session.commit()
            # Display the poster after a successful save
            # time.sleep(10)
            # self.display_info(title_id)

        except Exception as e:
            self.db_manager.session.rollback()
            self.logger.error(f"Ошибка при сохранении постера в базу данных: {e}")


    def process_titles(self, title_data):
        title = title_data
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

                self.db_manager.save_title(title_data)
        except Exception as e:
            self.logger.error(f"Failed to save title to database: {e}")


    def process_episodes(self, title_data):
        selected_quality = self.quality_dropdown.currentText()
        for episode in title_data.get("player", {}).get("list", {}).values():
            if not isinstance(episode, dict):
                self.logger.error(f"Invalid type for episode. Expected dict, got {type(episode)}")
                continue

            if "hls" in episode and selected_quality in episode["hls"]:
                try:
                    episode_data = {
                        'episode_id': episode.get('id'),
                        'title_id': title_data.get('id'),
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
                    self.db_manager.save_episode(episode_data)
                except Exception as e:
                    self.logger.error(f"Failed to save episode to database: {e}")


    def process_torrents(self, title_data):
        if "torrents" in title_data and "list" in title_data["torrents"]:
            for torrent in title_data["torrents"]["list"]:
                url = torrent.get("url")
                if url:
                    try:
                        torrent_data = {
                            'torrent_id': torrent.get('torrent_id'),
                            'title_id': title_data.get('id'),
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
                        self.db_manager.save_torrent(torrent_data)
                    except Exception as e:
                        self.logger.error(f"Ошибка при сохранении торрента в базе данных: {e}")



    def get_poster(self, title_data):
        try:
            # Construct the poster URL
            poster_url = self.pre + self.base_url + title_data["posters"]["small"]["url"]

            # Standardize the poster URL
            standardized_url = self.standardize_url(poster_url)
            self.logger.debug(f"Standardize the poster URL: {standardized_url}")

            # Check if the standardized URL is already in the cached poster links
            if standardized_url in map(self.standardize_url, self.poster_manager.poster_links):
                self.logger.debug(f"Poster URL already cached: {standardized_url}. Skipping fetch.")
                return None


            return standardized_url

        except Exception as e:
            error_message = f"An error occurred while getting the poster: {str(e)}"
            self.logger.error(error_message)
            return None


    def on_link_click(self, url):
        try:
            link = url.toString()  # Преобразуем объект QUrl в строку

            if link.startswith('display_info/'):
                # Получаем title_id из ссылки и вызываем display_info
                title_id = int(link.split('/')[1])
                QTimer.singleShot(100, lambda: self.display_info(title_id))

                return
            elif link.endswith('.m3u8'):
                video_player_path = self.video_player_path
                open_link = self.pre + self.stream_video_url + link
                media_player_command = [video_player_path, open_link]
                subprocess.Popen(media_player_command)
                self.logger.info(f"Playing video link: {open_link}")
            elif '/torrent/download.php' in link:
                # Здесь нужно извлечь название тайтла и идентификатор торрента из ссылки
                # title_name и torrent_id можно передать дополнительно, если нужно
                title_name = "Unknown Title"  # Вы можете настроить это значение
                torrent_id = None  # Если возможно, извлеките ID из ссылки
                self.save_torrent_wrapper(link, title_name, torrent_id)
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
        combined_playlist_filename = "_".join([info['sanitized_title'] for info in self.playlists.values()])[
                                     :100] + ".m3u"
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

    def play_playlist_wrapper(self):
        """
        Wrapper function to handle playing the playlist.
        Determines the file name and passes it to play_playlist.
        """
        if not self.sanitized_titles:
            self.logger.error("Playlist not found, please save playlist first.")
            return

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
