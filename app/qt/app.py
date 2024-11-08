import ast
import json
import logging
import os
import platform
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta

from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLineEdit, QLabel, QComboBox, QGridLayout, QScrollArea, QTextBrowser, QSizePolicy, QGraphicsDropShadowEffect
)
from PyQt5.QtCore import Qt, QByteArray, QBuffer, QUrl, QTimer, QRunnable, QThreadPool, pyqtSlot, QObject, pyqtSignal
from PyQt5.QtGui import QPixmap

from app.qt.ui_manger import UIManager
from core import database_manager
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


class AnimePlayerAppVer3(QWidget):
    add_title_browser_to_layout = pyqtSignal(QTextBrowser, int, int)

    def __init__(self, db_manager):
        super().__init__()
        self.load_more_button = None
        self.thread_pool = QThreadPool()  # Пул потоков для управления задачами
        self.thread_pool.setMaxThreadCount(4)
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

        self.logger.debug("Initializing AnimePlayerApp Version 3")

        self.cache_file_path = "temp/poster_cache.txt"
        self.config_manager = ConfigManager('config/config.ini')

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
        self.db_manager = db_manager
        self.poster_manager = PosterManager(
            save_callback=self.db_manager.save_poster_to_db,
        )

        self.days_of_week = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]
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
        self.setGeometry(100, 100, 980, 750)

        # Основной вертикальный layout
        main_layout = QVBoxLayout()
        self.ui_manager.setup_main_layout(main_layout)
        self.setLayout(main_layout)

        # Load 4 titles on start from DB
        self.display_titles()

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

    def display_titles(self):
        """Отображение первых тайтлов при старте."""
        # Загружаем первую партию тайтлов
        titles = self.db_manager.get_titles_from_db(show_all=True, batch_size=self.titles_batch_size, offset=self.current_offset)

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
        titles = self.db_manager.get_titles_from_db(show_all=True, batch_size=self.titles_batch_size, offset=self.current_offset)

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
        """Отображает информацию о конкретном тайтле."""
        self.clear_previous_posters()

        # Получаем тайтл из базы данных по его идентификатору
        titles = self.db_manager.get_titles_from_db(title_id=title_id)

        if not titles or titles[0] is None:
            self.logger.error(f"Title with title_id {title_id} not found in the database.")
            return

        title = titles[0]

        # Обновление UI с загруженными данными
        title_layout = self.create_title_browser(title, show_description=True, show_one_title=True)
        self.posters_layout.addLayout(title_layout, 0, 0, 1, 2)

    def display_titles_for_day(self, day_of_week):
        # Очистка предыдущих постеров
        self.clear_previous_posters()

        titles = self.db_manager.get_titles_from_db(day_of_week)

        if not titles:
            try:
                data = self.get_schedule(day_of_week)
                self.logger.debug(f"Получены данные с сервера: {len(data)} keys (type: {type(data).__name__})")
                # Обработка данных и добавление их в базу данных
                if data is True:
                    # После сохранения данных в базе получаем их снова
                    titles = self.db_manager.get_titles_from_db(day_of_week)
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
                                        new_title.get('code') != current_title.code or \
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
        if delta > timedelta(hours=1):
            return False

        return True

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
                poster_data = self.db_manager.get_poster_blob(2)

            if poster_data:
                pixmap = QPixmap()
                if pixmap.loadFromData(poster_data):
                    poster_label.setPixmap(pixmap.scaled(550, 650, Qt.KeepAspectRatio))
                else:
                    self.logger.error(f"Error: Failed to load pixmap from data for title_id: {title.title_id}")
                    # Используем статическую картинку-заглушку в случае, если даже загрузка pixmap не удалась
                    poster_label.setPixmap(QPixmap("static/no_image.png").scaled(550, 650, Qt.KeepAspectRatio))
            else:
                # Если данные постера отсутствуют даже для заглушки, используем статическое изображение
                poster_label.setPixmap(QPixmap("static/no_image.png").scaled(550, 650, Qt.KeepAspectRatio))

            title_layout.addWidget(poster_label)

            # Title information on the right
            title_browser = QTextBrowser(self)
            title_browser.setPlainText(f"Title: {title.name_en}")
            title_browser.setOpenExternalLinks(True)
            title_browser.setFixedSize(550, 650)  # Set the size of the information browser
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
            title_browser.setFixedSize(550, 650)  # Размер плитки
            title_browser.setProperty('title_id', title.title_id)

            html_content = self.get_title_html(title, show_description, show_more_link=True)
            title_browser.setHtml(html_content)
            title_browser.anchorClicked.connect(self.on_link_click)
           # title_browser.mouseDoubleClickEvent(self.display_info(title.title_id))
            return title_browser

    def get_title_html(self, title, show_description=False, show_more_link=False):
        """Генерирует HTML для отображения информации о тайтле."""
        # Получаем данные постера
        poster_html = self.generate_poster_html(title) if show_more_link else f"background-image: url('static/background.png');"
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
        torrents = self.db_manager.get_torrents_from_db(title.title_id)

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
            poster_data = self.db_manager.get_poster_blob(1)

        # Если даже заглушка не найдена, возвращаем URL к статическому изображению
        if not poster_data:
            return f"background-image: url('static/background.png');"

        try:
            pixmap = QPixmap()
            if not pixmap.loadFromData(poster_data):
                self.logger.error(f"Error: Failed to load image data for title_id: {title.title_id}")
                return f"background-image: url('static/background.png');"

            # Используем QBuffer для сохранения в байтовый массив
            byte_array = QByteArray()
            buffer = QBuffer(byte_array)
            buffer.open(QBuffer.WriteOnly)
            if not pixmap.save(buffer, 'PNG'):
                self.logger.error(f"Error: Failed to save image as PNG for title_id: {title.title_id}")
                return f"background-image: url('static/background.png');"

            # Преобразуем данные в Base64
            poster_base64 = base64.b64encode(byte_array.data()).decode('utf-8')
            return f'background-image: url("data:image/png;base64,{poster_base64}");'
        except Exception as e:
            self.logger.error(f"Error processing poster for title_id: {title.title_id} - {e}")
            return f"background-image: url('static/background.png');"

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
                episodes_html += f'<li><a href="{link}" target="_blank">{episode_name}</a></li>'
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
        self.logger.debug(f"discovered_links: {len(self.discovered_links)}")
        self.logger.debug(f"sanitized_name: {sanitized_name}")

        return episodes_html

    def invoke_database_save(self, title_list):
        processes = {
            self.process_poster_links: "poster links",
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
                self.logger.debug(f"Poster url: {poster_url[-41:]}")

        if poster_links:
            self.poster_manager.write_poster_links(poster_links)
        return True

    def get_poster(self, title_data):
        try:
            # Construct the poster URL
            poster_url = self.pre + self.base_url + title_data["posters"]["small"]["url"]

            # Standardize the poster URL
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

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = AnimePlayerAppVer3(database_manager)
    window.show()
    sys.exit(app.exec_())