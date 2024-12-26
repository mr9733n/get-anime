import base64
import json
import os
import logging
import random
import re

import vlc
from PyQt5.QtMultimediaWidgets import QVideoWidget
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QPushButton, QSlider, QLabel, QHBoxLayout, QListWidget
from PyQt5.QtCore import Qt, QTimer, pyqtSlot
from utils.library_loader import verify_library, load_library

# Настройка логирования
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s.%(funcName)s | %(message)s")
logger = logging.getLogger(__name__)

# Константы для библиотеки
LIB_DIR = "libs"
LIB_NAME = "libvlc.dll"
EXPECTED_HASH = "a2625d21b2cbca52ae5a9799e375529c715dba797a5646adf62f1c0289dbfb68"

# Проверка и загрузка библиотеки
try:
    lib_file_path = load_library(LIB_DIR, LIB_NAME)
    verify_library(lib_file_path, EXPECTED_HASH)
except Exception as e:
    logger.error(f"Failed to initialize library: {e}")
    exit(1)


class VideoWindow(QWidget):
    """Отдельное окно для видео."""
    def __init__(self, media_player):
        super().__init__()
        self.setWindowTitle("VLC Video Player")
        self.video_widget = QVideoWidget(self)
        self.setCentralWidget(self.video_widget)
        self.media_player = media_player
        self.media_player.set_hwnd(self.video_widget.winId())

    def closeEvent(self, event):
        """Останавливает воспроизведение, если закрывается окно видео."""
        self.media_player.stop()  # Останавливаем воспроизведение
        event.accept()


class VLCPlayer(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.is_skip_credits_pressed = None
        self.skip_credits_pressed = False
        self.skip_in_progress = None
        self.skip_data_cache = None
        self.current_episode = None
        self.skip_opening = None
        self.skip_ending = None
        self.is_buffering = None
        self.title_id = None
        self.setWindowTitle("VLC Video Player Controls")
        self.setMinimumSize(850, 100)
        self.setMaximumSize(850, 200)
        self.setMinimumHeight(100)
        self.setMaximumHeight(200)
        self.video_window = None
        self.logger = logging.getLogger(__name__)
        self.instance = vlc.Instance()
        self.instance = vlc.Instance('--network-caching=2000')

        self.list_player = self.instance.media_list_player_new()
        self.media_list = self.instance.media_list_new()
        self.media_player = self.list_player.get_media_player()

        # Флаги для повторения и перемешивания
        self.is_repeat = False
        self.is_seeking = False

        # Интерфейс
        self.play_button = QPushButton("PLAY")
        self.previous_button = QPushButton("PREV")
        self.stop_button = QPushButton("STOP")
        self.next_button = QPushButton("NEXT")
        self.repeat_button = QPushButton("REPEAT")
        self.playlist_button = QPushButton("PLAYLIST")
        self.screenshot_button = QPushButton("SCREENSHOT")
        self.skip_credits_button = QPushButton("SKIP CREDITS")
        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(100)
        self.progress_slider = QSlider(Qt.Horizontal)
        self.progress_slider.setRange(0, 100)
        self.time_label = QLabel("00:00 / 00:00")
        self.playlist_widget = QListWidget()
        self.playlist_widget.hide()  # Прячем список по умолчанию

        # Задание длины слайдеров
        self.play_button.setFixedHeight(25)
        self.stop_button.setFixedHeight(25)
        self.next_button.setFixedHeight(25)
        self.previous_button.setFixedHeight(25)
        self.playlist_button.setFixedHeight(25)
        self.screenshot_button.setFixedHeight(25)
        self.skip_credits_button.setFixedHeight(25)
        self.volume_slider.setFixedHeight(25)
        self.volume_slider.setFixedWidth(80)
        self.progress_slider.setFixedWidth(830)

        # Layout
        progress_layout = QHBoxLayout()
        progress_layout.addWidget(self.progress_slider)

        control_layout = QHBoxLayout()
        control_layout.addWidget(self.time_label)
        control_layout.addWidget(self.skip_credits_button)
        control_layout.addWidget(self.play_button)
        control_layout.addWidget(self.previous_button)
        control_layout.addWidget(self.stop_button)
        control_layout.addWidget(self.next_button)
        control_layout.addWidget(self.repeat_button)
        control_layout.addWidget(self.playlist_button)
        control_layout.addWidget(self.screenshot_button)
        control_layout.addWidget(self.volume_slider)

        main_layout = QVBoxLayout()
        main_layout.addLayout(progress_layout)
        main_layout.addLayout(control_layout)
        main_layout.addWidget(self.playlist_widget)
        self.setLayout(main_layout)

        # Стили             ("#4a4a4a", "#5c5c5c", "#000"),  # Dark gray : 0
        self.setStyleSheet("""
            QPushButton {
                background-color: #4a4a4a;
                color: white;
                border: none;
                font-size: 14px;
                border-radius: 5px;
                font-weight: bold;
                padding: 5px;
            }
            QPushButton:hover {
                background-color: #5c5c5c;
            }
            QSlider::groove:horizontal {
                background: #bdc3c7;  /* Цвет трека (основного пути) */
                height: 25px;         /* Высота трека */
                border-radius: 5px;   /* Радиус углов для закругления */
            }
            
            QSlider::handle:horizontal {
                background: #4a4a4a;  /* Цвет ручки слайдера */
                width: 50px;          /* Ширина ручки */
                height: 25px;         /* Высота ручки */
                margin: -1px 0;       /* Смещение ручки относительно трека */
                border-radius: 5px;   /* Радиус углов ручки */
            }
            
            QSlider::sub-page:horizontal {
                background: #7f7f7f;  /* Цвет закрашенного участка до ручки */
                border-radius: 5px;   /* Радиус углов закрашенного участка */
            }
            
            QSlider::add-page:horizontal {
                background: #ecf0f1;  /* Цвет оставшегося участка после ручки */
                border-radius: 5px;   /* Радиус углов */
            }
            QLabel {
                color: #2c3e50;
                font-weight: bold;
                font-size: 14px;
            }
            QListWidget {
                background-color: #ecf0f1;
                border: 1px solid #bdc3c7;
                font-size: 14px;
            }
        """)

        # Сигналы
        self.progress_slider.sliderReleased.connect(self.seek_position)
        self.progress_slider.mousePressEvent = self.slider_clicked
        self.play_button.clicked.connect(self.play_pause)
        self.previous_button.clicked.connect(self.previous_media)
        self.stop_button.clicked.connect(self.stop_media)
        self.next_button.clicked.connect(self.next_media)
        self.repeat_button.clicked.connect(self.toggle_repeat)
        self.playlist_button.clicked.connect(self.toggle_playlist_visibility)
        self.screenshot_button.clicked.connect(self.take_screenshot)
        self.skip_credits_button.clicked.connect(self.handle_skip_credits)
        self.playlist_widget.itemClicked.connect(self.play_selected_item)
        self.volume_slider.valueChanged.connect(self.set_volume)

        # Таймер для обновления прогресса
        self.timer = QTimer(self)
        self.timer.setInterval(500)
        self.timer.timeout.connect(self.update_ui)

    def toggle_repeat(self):
        """Переключает режим повторения."""
        self.is_repeat = not self.is_repeat
        self.logger.info(f"Repeat mode {'enabled' if self.is_repeat else 'disabled'}")
        self.repeat_button.setStyleSheet("background-color: #5c5c5c;" if self.is_repeat else "")

        if self.is_repeat:
            self.list_player.set_playback_mode(vlc.PlaybackMode.loop)
        else:
            self.list_player.set_playback_mode(vlc.PlaybackMode.default)

    def take_screenshot(self):
        """Создает скриншот текущего кадра и сохраняет его в папке screenshots."""
        screenshots_dir = "screenshots"
        if not os.path.exists(screenshots_dir):
            os.makedirs(screenshots_dir)  # Создаем папку, если она не существует

        screenshot_path = os.path.join(screenshots_dir, f"screenshot_{self.title_id}_{self.get_timestamp()}.png")

        # Используем метод VLC для создания скриншота
        if self.media_player.video_take_snapshot(0, screenshot_path, 0, 0):
            self.logger.info(f"Screenshot saved: {screenshot_path}")
        else:
            self.logger.error("Failed to take screenshot.")

    def get_timestamp(self):
        """Возвращает текущий таймкод в формате ЧЧ-ММ-СС."""
        import time
        return time.strftime("%H-%M-%S")

    def toggle_playlist_visibility(self):
        """Переключает видимость списка воспроизведения."""
        if self.playlist_widget.isVisible():
            self.playlist_widget.hide()
            self.resize(850, 100)
        else:
            self.playlist_widget.show()
            self.resize(850, 200)

    def is_url(self, path):
        """Проверяет, является ли path URL."""
        return path.startswith(("http://", "https://"))

    def load_playlist(self, path, title_id, skip_data=None):
        """
        Загружает плейлист из файла или ссылки и отображает серии в списке.

        Args:
            path (str): Путь к локальному файлу или URL плейлиста.
            title_id (str): Идентификатор текущего тайтла.
            skip_data (str): Закодированные данные о пропусках в base64.
        """
        self.playlist_widget.clear()  # Очищаем список серий
        self.title_id = title_id

        if skip_data:
            try:
                skip_data_json = base64.urlsafe_b64decode(skip_data.encode()).decode()
                self.skip_data_cache = json.loads(skip_data_json)  # Кешируем данные
                self.logger.debug(f"Decoded skip_data: {self.skip_data_cache}")
            except Exception as e:
                self.logger.error(f"Failed to decode skip_data: {e}")
                self.skip_data_cache = None
        else:
            self.skip_data_cache = None

        try:
            if self.is_url(path):
                self.load_playlist_from_url(path)
            else:
                self.load_playlist_from_file(path)
        except Exception as e:
            self.logger.error(f"!!! Error playing playlist file: {e}")

    def extract_from_link(self, url):
        try:
            # Extract title ID, episode number, and quality from the URL
            match = re.search(r"/(\d+)/(\d+)/(\d+)/", url)
            if match:
                title_id = int(match.group(1))
                episode_number = int(match.group(2))
                episode_quality = int(match.group(3))
                self.logger.debug(f"Title {title_id} Episode {episode_number} Quality {episode_quality}")
            else:
                raise ValueError(f"Could not parse URL for title_id, episode_number, or quality: {url}")
            return title_id, episode_number, episode_quality
        except Exception as e:
            self.logger.error(f"!!! Error extracting from URL: {e}")

    def load_playlist_from_url(self, url):
        """Loads and plays a playlist from a URL."""
        try:
            # Extract title ID, episode number, and quality from the URL
            title_id, episode_number, episode_quality = self.extract_from_link(url)

            self.current_episode =  episode_number
            self.logger.debug(f"Cached {title_id} Episode {self.current_episode}")

            # Fetch skip data from the cache
            skip_opening, skip_ending = None, None
            if self.skip_data_cache:
                for skip_entry in self.skip_data_cache.get("episode_skips", []):
                    if skip_entry["episode_number"] == episode_number:
                        skip_opening = json.loads(skip_entry.get("skip_opening", "[]"))
                        skip_ending = json.loads(skip_entry.get("skip_ending", "[]"))
                        break

            self.logger.debug(f"Episode {episode_number}: Skip opening: {skip_opening}, Skip ending: {skip_ending}")

            # Load media
            media = self.instance.media_new(url)
            self.media_list.add_media(media)
            self.playlist_widget.addItem(url)
            self.list_player.set_media_list(self.media_list)
            self.list_player.play()

            self.logger.info(f"Playing stream URL: {url}")
        except Exception as e:
            self.logger.error(f"!!! Error playing stream URL: {e}")

    def load_playlist_from_file(self, file_path):
        """Загружает и воспроизводит плейлист из локального файла."""
        if not os.path.exists(file_path):
            self.logger.error(f"!!! Playlist file not found: {file_path}")
            return

        try:
            with open(file_path, "r", encoding="utf-8") as playlist_file:
                for link in playlist_file:
                    link = link.strip()
                    if link and not link.startswith("#"):  # Игнорируем комментарии
                        # Извлекаем номер эпизода из строки
                        title_id, episode_number, episode_quality = self.extract_from_link(link)

                        self.current_episode = episode_number
                        self.logger.debug(f"Cached {title_id} Episode {self.current_episode}")

                        # Получаем данные о пропусках из кэша
                        skip_opening, skip_ending = None, None
                        if self.skip_data_cache and episode_number:
                            for skip_entry in self.skip_data_cache.get("episode_skips", []):
                                if skip_entry["episode_number"] == episode_number:
                                    skip_opening = skip_entry.get("skip_opening", [])
                                    skip_ending = skip_entry.get("skip_ending", [])
                                    break

                        self.logger.debug(
                            f"Episode {episode_number}: Skip opening: {skip_opening}, Skip ending: {skip_ending}")

                        media = self.instance.media_new(link)
                        self.media_list.add_media(media)
                        self.playlist_widget.addItem(link)  # Добавляем серию в список

            self.list_player.set_media_list(self.media_list)
            self.list_player.play()
            self.logger.info(f"Playlist playing from file: {file_path}")
        except Exception as e:
            self.logger.error(f"!!! Error playing playlist file: {e}")

    def play_selected_item(self, item):
        """Воспроизводит выбранную серию."""
        index = self.playlist_widget.row(item)
        self.list_player.play_item_at_index(index)
        self.timer.start()

    def play_pause(self):
        if self.skip_opening and not self.media_player.is_playing():
            # Пропуск начала
            self.logger.debug(f"Skipping opening: {self.skip_opening}")
            total_length = self.media_player.get_length() / 1000  # Общая длина в секундах
            if total_length > 0:
                skip_position = self.skip_opening[1] / total_length
                self.logger.debug(f"Setting position to skip opening: {skip_position:.2f}")
                self.media_player.set_position(skip_position)
            self.skip_opening = None  # Убираем, чтобы больше не срабатывало
            self.play_button.setText("PLAY")
            self.media_player.play()
            self.timer.start()
        elif self.skip_ending and not self.media_player.is_playing():
            # Пропуск конца
            self.logger.debug(f"Skipping ending: {self.skip_ending}")
            total_length = self.media_player.get_length() / 1000  # Общая длина в секундах
            if total_length > 0:
                skip_position = (total_length - self.skip_ending[0]) / total_length
                self.logger.debug(f"Setting position to skip ending: {skip_position:.2f}")
                self.media_player.set_position(skip_position)
            self.skip_ending = None  # Убираем, чтобы больше не срабатывало
            self.play_button.setText("PLAY")
            self.media_player.play()
            self.timer.start()
        elif self.media_player.is_playing():
            # Пауза
            self.media_player.pause()
            self.play_button.setText("PLAY")
            self.timer.stop()
        else:
            # Обычное воспроизведение
            self.media_player.play()
            self.play_button.setText("PAUSE")
            self.timer.start()

    def stop_media(self):
        self.list_player.stop()
        self.play_button.setText("PLAY")
        self.timer.stop()

    def set_volume(self, volume):
        self.media_player.audio_set_volume(volume)

    def slider_clicked(self, event):
        """Обрабатывает клик по слайдеру и перемещает ручку с учетом буферизации."""
        if event.button() == Qt.LeftButton:
            # Определяем относительное положение клика
            slider_width = self.progress_slider.width()
            click_position = event.pos().x()
            new_value = int((click_position / slider_width) * self.progress_slider.maximum())

            # Устанавливаем новую позицию
            self.progress_slider.setValue(new_value)

            # Перематываем видео с учетом буферизации
            self.seek_position_with_buffer()

    def seek_position(self):
        """Перематывает воспроизведение на указанное положение с мини-паузой и фиксацией положения слайдера."""
        self.is_seeking = True  # Отключаем автоматическое обновление
        if self.media_player.is_playing():
            self.media_player.pause()

        position = self.progress_slider.value() / 100
        self.media_player.set_position(position)

        # Устанавливаем таймер для возобновления воспроизведения и обновления UI
        QTimer.singleShot(500, self.resume_playback)

    def seek_position_with_buffer(self):
        """Перематывает потоковое видео с ожиданием загрузки."""
        self.is_buffering = True  # Включаем режим буферизации
        self.is_seeking = True  # Отключаем обновление UI

        if self.media_player.is_playing():
            self.media_player.pause()

        position = self.progress_slider.value() / 100
        self.media_player.set_position(position)

        # Устанавливаем таймер для ожидания буферизации
        QTimer.singleShot(1000, self.resume_stream)

    def resume_stream(self):
        """Возобновляет потоковое воспроизведение после буферизации."""
        if not self.media_player.is_playing():
            self.media_player.play()

        # Выключаем режимы ожидания
        self.is_buffering = False
        self.is_seeking = False

    def format_time(self, seconds):
        minutes = int(seconds // 60)
        seconds = int(seconds % 60)
        return f"{minutes:02}:{seconds:02}"

    def next_media(self):
        if self.media_list.count() > 0:
            self.list_player.next()
            self.timer.start()

    def previous_media(self):
        if self.media_list.count() > 0:
            self.list_player.previous()
            self.timer.start()

    def closeEvent(self, event):
        """Останавливает воспроизведение и закрывает окно видео при закрытии основного окна."""
        self.stop_media()  # Останавливаем воспроизведение
        if self.video_window is not None:  # Проверяем, если окно видео открыто
            self.video_window.close()  # Закрываем окно видео
        self.list_player.release()  # Освобождаем ресурсы MediaListPlayer
        self.media_player.release()  # Освобождаем ресурсы MediaPlayer
        self.instance.release()  # Освобождаем VLC instance
        event.accept()  # Подтверждаем закрытие основного окна

    def resizeEvent(self, event):
        """Ограничивает размер окна при попытке изменения."""
        if self.playlist_widget.isVisible():
            self.resize(850, 150)
        else:
            self.resize(850, 50)  # Устанавливаем фиксированный размер при попытке изменить
        event.accept()

    def update_ui(self):
        """Updates the progress bar, timer, and checks for skips."""
        try:
            if self.is_seeking or self.is_buffering:
                return

            if not self.media_player.is_playing():
                return

            length = self.media_player.get_length() / 1000
            current_time = self.media_player.get_time() / 1000

            # Highlight the currently playing video
            self.update_playlist_highlight()

            if self.skip_credits_pressed:
                # Get current episode and skip data
                episode_number = self.get_playing_episode_number()
                if episode_number is not None:
                    self.get_episode_skips(episode_number)

                    if not self.skip_in_progress:
                        self.skip_in_progress = True
                        self.logger.debug(f"Setting position to skip: {self.skip_in_progress}")
                        # Проверка пропуска начала
                        if self.skip_opening and self.skip_opening[0] <= current_time <= self.skip_opening[1]:
                            self.logger.info(f"Skipping opening for episode {episode_number}: {self.skip_opening}")
                            total_length = self.media_player.get_length() / 1000
                            if total_length > 0:
                                skip_position = self.skip_opening[1] / total_length
                                self.logger.info(f"Skip opening: {(self.skip_opening[1] - self.skip_opening[0]):.2f} seconds. "
                                                 f"Setting position to: {(skip_position * total_length)/60:.2f} minutes")

                                self.media_player.set_position(skip_position)
                            self.skip_opening = None  # Убираем, чтобы больше не срабатывало
                            self.play_button.setText("PLAY")
                            return

                        # Проверка пропуска конца
                        if self.skip_ending and (length - self.skip_ending[0]) <= current_time:
                            self.logger.debug(f"Skipping ending for episode {episode_number}: {self.skip_ending}")
                            self.media_player.stop()
                            self.next_media()
                            return
                        self.skip_in_progress = False
                        self.logger.debug(f"Setting position to skip: {self.skip_in_progress}")

            # Update progress bar
            if length > 0:
                position = int((current_time / length) * 100)
                self.progress_slider.setValue(position)

            self.time_label.setText(f"{self.format_time(current_time)} / {self.format_time(length)}")
        except Exception as e:
            error_message = f"An error occurred while updating UI: {str(e)}"
            self.logger.error(error_message)

    def update_playlist_highlight(self):
        """Highlight the currently playing video in the playlist."""
        current_media = self.media_player.get_media()
        if not current_media:
            return

        current_url = current_media.get_mrl()
        for i in range(self.playlist_widget.count()):
            item = self.playlist_widget.item(i)
            if item.text() == current_url:
                # Highlight the currently playing item
                item.setBackground(Qt.lightGray)
                item.setForeground(Qt.black)
            else:
                # Reset the color of other items
                item.setBackground(Qt.white)
                item.setForeground(Qt.black)

    def handle_skip_credits(self):
        """Handles manual skip credits button press."""
        self.is_skip_credits_pressed = not self.is_skip_credits_pressed
        self.logger.info(f"Skip credits mode {'enabled' if self.is_skip_credits_pressed else 'disabled'}")
        self.skip_credits_button.setStyleSheet("background-color: #5c5c5c;" if self.is_skip_credits_pressed else "")
        self.skip_credits_pressed = True
        self.logger.info("SKIP CREDITS button pressed.")

    def get_episode_skips(self, episode_number):
        """
        Retrieves skip_opening and skip_ending for a given episode.

        Args:
            episode_number (int): The episode number.

        Returns:
            tuple: skip_opening (list), skip_ending (list)
        """
        skip_opening, skip_ending = None, None
        if self.skip_data_cache:
            for skip_entry in self.skip_data_cache.get("episode_skips", []):
                if skip_entry["episode_number"] == episode_number:
                    skip_opening = json.loads(skip_entry.get("skip_opening", "[]"))
                    skip_ending = json.loads(skip_entry.get("skip_ending", "[]"))
                    break
            self.skip_opening = skip_opening
            self.skip_ending = skip_ending

    def get_playing_episode_number(self):
        """
        Retrieves the current episode number based on the media player's current state.

        Returns:
            int: The current episode number, or None if unavailable.
        """
        media = self.media_player.get_media()
        if media:
            url = media.get_mrl()
            match = re.search(r"/\d+/(\d+)/", url)  # Assuming the URL contains the episode number
            if match:
                return int(match.group(1))
        return None

    def get_episode_number(self, url):
        """
        Retrieves the current episode number based on the media player's current state.

        Returns:
            int: The current episode number, or None if unavailable.
        """
        media = self.media_player.get_media()
        if media:
            url = media.get_mrl()
            match = re.search(r"/\d+/(\d+)/", url)  # Assuming the URL contains the episode number
            if match:
                return int(match.group(1))
        return None