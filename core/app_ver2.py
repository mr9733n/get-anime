import ast
import json
import logging
import platform
import re
from datetime import datetime

from PIL.Image import frombytes
#from PyQt5.QtNfc import title
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLineEdit, QLabel, QComboBox, QGridLayout, QScrollArea, QTextBrowser, QSizePolicy
)
from PyQt5.QtCore import Qt, QByteArray, QBuffer
from PyQt5.QtGui import QPixmap
import sys

from requests import session

from core.database_manager import Title, Schedule, Episode
from sqlalchemy.orm import joinedload
import base64

from core.database_manager import Poster
from utils.config_manager import ConfigManager
from utils.api_client import APIClient
from utils.poster_manager import PosterManager
from utils.playlist_manager import PlaylistManager
from utils.torrent_manager import TorrentManager


class AnimePlayerAppVer2(QWidget):
    def __init__(self, database_manager):
        super().__init__()

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
            display_callback=self.display_poster,
            save_callback=self.save_poster_to_db
        )
        

        self.db_manager = database_manager
        self.init_ui()


    def setup_paths(self):
        """Sets up paths based on the current platform and returns them for use."""
        current_platform = platform.system()
        video_player_path = self.config_manager.get_video_player_path(current_platform)
        torrent_client_path = self.config_manager.get_torrent_client_path(current_platform)

        # Return paths to be used in the class
        return video_player_path, torrent_client_path


    def init_ui(self):
        self.setWindowTitle('Anime Player v2')
        self.setGeometry(100, 100, 980, 725)

        # Основной вертикальный layout
        main_layout = QVBoxLayout()

        # Верхняя часть контролов
        controls_layout = QHBoxLayout()

        # Поле для поиска
        self.title_search_entry = QLineEdit(self)
        self.title_search_entry.setPlaceholderText('Enter title name')
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

        # Кнопка "Find"
        self.display_button = QPushButton('Find', self)
        self.display_button.setStyleSheet(button_style)
        controls_layout.addWidget(self.display_button)

        # Кнопка "Random"
        self.random_button = QPushButton('Random', self)
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
        self.refresh_button = QPushButton('Refresh', self)
        self.refresh_button.setStyleSheet(button_style)
        controls_layout.addWidget(self.refresh_button)

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


    def display_info(self, title_id):
        self.clear_previous_posters()
        session = self.db_manager.session
        try:
            # Загружаем тайтлы для определенного дня недели и загружаем связанные эпизоды
            title = (
                session.query(Title)
                .filter(Title.title_id == title_id)
                .one_or_none()  # Либо .first() для первого результата
            )
        except Exception as e:
            self.logger.error(f"Ошибка при загрузке тайтлов: {e}")
            return

        # Обновление UI с загруженными данными
        title_browser = self.create_title_browser(title, show_description=True)
        self.posters_layout.addWidget(title_browser)


    def display_titles_for_day(self, day_of_week):
        # Очистка предыдущих постеров
        self.clear_previous_posters()

        session = self.db_manager.session
        titles = []

        if session is not None:
            try:
                # Проверка наличия тайтлов в базе данных
                titles = (
                    session.query(Title)
                    .options(joinedload(Title.episodes))  # Загрузка эпизодов вместе с тайтлом
                    .join(Schedule)
                    .filter(Schedule.day_of_week == day_of_week)
                    .all()
                )
            except Exception as e:
                self.logger.error(f"Ошибка при загрузке тайтлов из базы данных: {e}")

        # Если в базе данных нет данных, то получаем их через get_schedule()
        if not titles:
            try:
                data = self.get_schedule(day_of_week)
                self.logger.debug(f"{data}")
                # Обработка данных и добавление их в базу данных
                if data is True:
                    # После сохранения данных в базе получаем их снова
                    titles = (
                        session.query(Title)
                        .options(joinedload(Title.episodes))
                        .join(Schedule)
                        .filter(Schedule.day_of_week == day_of_week)
                        .all()
                    )
            except Exception as e:
                self.logger.error(f"Ошибка при получении тайтлов через get_schedule: {e}")
                return

        # Обновление UI с загруженными данными
        num_columns = 2  # Задайте количество колонок для отображения
        for index, title in enumerate(titles):
            title_browser = self.create_title_browser(title, show_description=False)
            self.posters_layout.addWidget(title_browser, index // num_columns, index % num_columns)


    def clear_previous_posters(self):
        """Удаляет все предыдущие постеры из сетки."""
        for i in reversed(range(self.posters_layout.count())):
            widget_to_remove = self.posters_layout.itemAt(i).widget()
            if widget_to_remove is not None:
                widget_to_remove.setParent(None)


    def create_title_browser(self, title, show_description=False):
        """Создает элемент интерфейса для отображения информации о тайтле."""
        title_browser = QTextBrowser(self)
        title_browser.setOpenExternalLinks(True)
        title_browser.setFixedSize(455, 650)  # Размер плитки

        html_content = self.get_title_html(title, show_description)
        title_browser.setHtml(html_content)

        return title_browser


    def play_episode(self, episode):
        # Заглушка для функции воспроизведения эпизода
        self.logger.info(f"Воспроизведение серии: {episode.name}")


    def get_title_html(self, title, show_description=False):
        """Генерирует HTML для отображения информации о тайтле."""
        # Получаем данные постера
        poster_html = self.generate_poster_html(title)
        # Декодируем жанры и получаем другие поля
        genres_html = self.generate_genres_html(title)
        announce_html = self.generate_announce_html(title)
        status_html = self.generate_status_html(title)
        description_html = self.generate_description_html(title) if show_description else ""
        year_html = self.generate_year_html(title)
        type_html = self.generate_type_html(title)

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
                        background-image: url("data:image/png;base64,{poster_html}");
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
                </div>
                    <div>
                        <br><br><br><br><br><br><br><br><br>
                    </div>
            </body> 
        </html>
        """
        return html_content


    def generate_poster_html(self, title):
        """Генерирует HTML для постера в формате Base64."""
        poster_data = self.db_manager.get_poster_blob(title.title_id)
        if poster_data:
            try:
                pixmap = QPixmap()
                if not pixmap.loadFromData(poster_data):
                    self.logger.error(f"Ошибка: Не удалось загрузить изображение для title_id: {title.title_id}")
                    return '<div style="width:455px;height:650px;background-color:#ccc;"></div>'

                # Используем QBuffer для сохранения в байтовый массив
                byte_array = QByteArray()
                buffer = QBuffer(byte_array)
                buffer.open(QBuffer.WriteOnly)
                if not pixmap.save(buffer, 'PNG'):
                    self.logger.error(
                        f"Ошибка: Не удалось сохранить изображение в формат PNG для title_id: {title.title_id}")
                    return '<div style="width:455px;height:650px;background-color:#ccc;"></div>'

                # Преобразуем данные в Base64
                poster_base64 = base64.b64encode(byte_array.data()).decode('utf-8')
                self.logger.debug(f"Base64 изображение (часть): {poster_base64[:16]}...")  # Вывести первые 16 символов
                return poster_base64
            except Exception as e:
                self.logger.error(f"Ошибка при обработке постера для title_id: {title.title_id} - {e}")
                return '<div style="width:455px;height:650px;background-color:#ccc;"></div>'
        else:
            self.logger.warning(f"Предупреждение: Нет данных для постера для title_id: {title.title_id}")
            return '<div style="width:455px;height:650px;background-color:#ccc;"></div>'


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
        """Генерирует HTML для отображения списка эпизодов."""
        if not title.episodes:
            return "<p>Эпизоды отсутствуют</p>"

        episodes_html = "<ul>"
        for i, episode in enumerate(title.episodes):
            episode_name = episode.name if episode.name else f'Серия {i + 1}'
            episodes_html += f'<li><a href="#">{episode_name}</a></li>'
        episodes_html += "</ul>"
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
        data = self.api_client.get_schedule(day)
        if 'error' in data:
            self.logger.error(data['error'])
            return
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
        return True

    def get_search_by_title(self):
        search_text = self.title_search_entry.get()
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
        except Exception as e:
            self.db_manager.session.rollback()
            self.logger.error(f"Ошибка при сохранении постера в базу данных: {e}")


    def display_poster(self, poster_image, title_id):
        if poster_image:
            try:
                pixmap = QPixmap()
                if not pixmap.loadFromData(poster_image):
                    self.logger.error(f"Ошибка: Не удалось загрузить изображение для title_id: {title_id}")
                    return '<div style="width:455px;height:650px;background-color:#ccc;"></div>'

                # Используем QBuffer для сохранения в байтовый массив
                byte_array = QByteArray()
                buffer = QBuffer(byte_array)
                buffer.open(QBuffer.WriteOnly)
                if not pixmap.save(buffer, 'PNG'):
                    self.logger.error(
                        f"Ошибка: Не удалось сохранить изображение в формат PNG для title_id: {title_id}")
                    return '<div style="width:455px;height:650px;background-color:#ccc;"></div>'

                # Преобразуем данные в Base64
                poster_base64 = base64.b64encode(byte_array.data()).decode('utf-8')
                self.logger.debug(f"Base64 изображение (часть): {poster_base64[:16]}...")  # Вывести первые 16 символов
                return poster_base64
            except Exception as e:
                self.logger.error(f"Ошибка при обработке постера для title_id: {title_id} - {e}")
                return '<div style="width:455px;height:650px;background-color:#ccc;"></div>'
        else:
            self.logger.warning(f"Предупреждение: Нет данных для постера для title_id: {title_id}")
            return '<div style="width:455px;height:650px;background-color:#ccc;"></div>'


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


    def save_playlist_wrapper(self):
        """
        Wrapper function to handle saving the playlist.
        Collects title names and links, and passes them to save_playlist.
        """
        if self.discovered_links:
            self.sanitized_titles = [self.sanitize_filename(name) for name in self.title_names]
            self.playlist_manager.save_playlist(self.sanitized_titles, self.discovered_links, self.stream_video_url)
            self.logger.debug("Links was sent for saving playlist...")
        else:
            self.logger.error("No links was found for saving playlist.")


    def play_playlist_wrapper(self):
        """
        Wrapper function to handle playing the playlist.
        Determines the file name and passes it to play_playlist.
        """
        if not self.sanitized_titles:
            self.logger.error("Playlist not found, please save playlist first.")
            return

        file_name = "_".join(self.sanitized_titles)[:100] + ".m3u"
        video_player_path = self.video_player_path
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
