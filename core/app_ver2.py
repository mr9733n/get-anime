import ast
import json
import logging

from PIL.Image import frombytes
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLineEdit, QLabel, QComboBox, QGridLayout, QScrollArea, QTextBrowser
)
from PyQt5.QtCore import Qt, QByteArray, QBuffer
from PyQt5.QtGui import QPixmap
import sys
from core.database_manager import Title, Schedule, Episode
from sqlalchemy.orm import joinedload
import base64

class AnimePlayerAppVer2(QWidget):
    def __init__(self, database_manager):
        super().__init__()
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
        self.logger = logging.getLogger(__name__)
        self.db_manager = database_manager
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle('Anime Player v2')
        self.setGeometry(100, 100, 1400, 1200)

        # Основной вертикальный layout
        main_layout = QVBoxLayout()

        # Верхняя часть контролов
        controls_layout = QHBoxLayout()

        # Поле для поиска
        self.title_search_entry = QLineEdit(self)
        self.title_search_entry.setPlaceholderText('Введите название тайтла')
        controls_layout.addWidget(self.title_search_entry)

        # Кнопка "Отобразить информацию"
        self.display_button = QPushButton('Отобразить информацию', self)
        controls_layout.addWidget(self.display_button)

        # Кнопка "Random"
        self.random_button = QPushButton('Random', self)
        controls_layout.addWidget(self.random_button)

        # Список выбора качества
        self.quality_label = QLabel('Качество:', self)
        controls_layout.addWidget(self.quality_label)

        self.quality_dropdown = QComboBox(self)
        self.quality_dropdown.addItems(['fhd', 'hd', 'sd'])
        controls_layout.addWidget(self.quality_dropdown)

        # Кнопка "Обновить"
        self.refresh_button = QPushButton('Обновить', self)
        controls_layout.addWidget(self.refresh_button)

        # Добавляем контролы в основной layout
        main_layout.addLayout(controls_layout)

        # Кнопки дней недели
        days_layout = QHBoxLayout()
        self.days_of_week = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
        self.day_buttons = []

        for i, day in enumerate(self.days_of_week):
            button = QPushButton(day, self)
            button.clicked.connect(
                lambda checked, i=i: self.display_titles_for_day(i))  # Передаем значение i напрямую в get_schedule
            days_layout.addWidget(button)
            self.day_buttons.append(button)

        # Добавляем кнопки дней недели в основной layout
        main_layout.addLayout(days_layout)

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

    def display_titles_for_day(self, day_of_week):
        self.clear_previous_posters()
        session = self.db_manager.session
        try:
            # Загружаем тайтлы для определенного дня недели и загружаем связанные эпизоды
            titles = (
                session.query(Title)
                .options(joinedload(Title.episodes))  # Загрузка эпизодов вместе с тайтлом
                .join(Schedule)
                .filter(Schedule.day_of_week == day_of_week)  # Используем значение day_of_week
                .all()
            )
        except Exception as e:
            self.logger.error(f"Ошибка при загрузке тайтлов: {e}")
            return

        # Обновление UI с загруженными данными
        for index, title in enumerate(titles):
            title_browser = self.create_title_browser(title)
            self.posters_layout.addWidget(title_browser, index // 4, index % 4)

    def clear_previous_posters(self):
        """Удаляет все предыдущие постеры из сетки."""
        for i in reversed(range(self.posters_layout.count())):
            widget_to_remove = self.posters_layout.itemAt(i).widget()
            if widget_to_remove is not None:
                widget_to_remove.setParent(None)

    def create_title_browser(self, title):
        """Создает элемент интерфейса для отображения информации о тайтле."""
        title_browser = QTextBrowser(self)
        title_browser.setOpenExternalLinks(True)
        title_browser.setFixedSize(350, 600)  # Размер плитки

        html_content = self.get_title_html(title)
        title_browser.setHtml(html_content)

        return title_browser

    def play_episode(self, episode):
        # Заглушка для функции воспроизведения эпизода
        self.logger.info(f"Воспроизведение серии: {episode.name}")

    def get_title_html(self, title):
        """Генерирует HTML для отображения информации о тайтле."""
        # Получаем данные постера
        poster_html = self.generate_poster_html(title)

        # Декодируем жанры и получаем другие поля
        genres_html = self.generate_genres_html(title)
        announce_html = self.generate_announce_html(title)
        status_html = self.generate_status_html(title)
        description_html = self.generate_description_html(title)
        year_html = self.generate_year_html(title)
        type_html = self.generate_type_html(title)

        # Добавляем информацию об эпизодах
        episodes_html = self.generate_episodes_html(title)

        # Генерируем полный HTML
        html_content = f"""
        <html>
        <head>
            <style>
                body {{
                    background-image: url("data:image/png;base64,{poster_html}");
                    background-repeat: no-repeat;
                    background-position: center;
                    background-size: 200px 300px;  /* Размер постера на фоне */
                    background-attachment: fixed;  /* Фиксируем фон, чтобы он не прокручивался */
                    padding: 20px;
                    border: 1px solid #444;
                    margin: 10px;
                    width: 300px;
                    height: 600px;
                    position: relative;
                    color: white;
                }}
                div {{
                    background: rgba(0, 0, 0, 0.5);  /* Полупрозрачный черный фон */
                    padding: 15px;
                    border-radius: 5px;
                    color: white;  /* Цвет текста для всего контейнера */
                    position: absolute;
                    bottom: 10px;
                    left: 10px;
                    right: 10px;
                    overflow-y: auto; /* Добавляем прокрутку для длинного текста */
                }}
                h3 {{
                    background: rgba(0, 0, 0, 0.3);  /* Полупрозрачный черный фон */
                    color: #FFD700;  /* Золотой цвет для заголовка */
                    margin: 5px 0;
                }}
                p, ul, li {{
                    color: white;  /* Белый цвет для всех текстовых элементов */
                    margin: 5px 0;
                    background: rgba(0, 0, 0, 0.3);  /* Полупрозрачный черный фон */
                }}
                a {{
                    color: #FFD700;  /* Цвет ссылки */
                    text-decoration: none;
                    background: rgba(0, 0, 0, 0.3);  /* Полупрозрачный черный фон */
                }}
            </style>
        </head>
        <body>
            <div>
                <h3>{title.name_en}</h3>
                <h3>{title.name_ru}</h3>
                {announce_html}
                {status_html}
                {description_html}
                {genres_html}
                {year_html}
                {type_html}
                <p>Эпизоды:</p>
                {episodes_html}
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
                    return '<div style="width:220px;height:320px;background-color:#ccc;"></div>'

                # Используем QBuffer для сохранения в байтовый массив
                byte_array = QByteArray()
                buffer = QBuffer(byte_array)
                buffer.open(QBuffer.WriteOnly)
                if not pixmap.save(buffer, 'PNG'):
                    self.logger.error(
                        f"Ошибка: Не удалось сохранить изображение в формат PNG для title_id: {title.title_id}")
                    return '<div style="width:220px;height:320px;background-color:#ccc;"></div>'

                # Преобразуем данные в Base64
                poster_base64 = base64.b64encode(byte_array.data()).decode('utf-8')
                self.logger.debug(f"Base64 изображение (часть): {poster_base64[:16]}...")  # Вывести первые 16 символов
                return poster_base64
            except Exception as e:
                self.logger.error(f"Ошибка при обработке постера для title_id: {title.title_id} - {e}")
                return '<div style="width:220px;height:320px;background-color:#ccc;"></div>'
        else:
            self.logger.warning(f"Предупреждение: Нет данных для постера для title_id: {title.title_id}")
            return '<div style="width:220px;height:320px;background-color:#ccc;"></div>'

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
