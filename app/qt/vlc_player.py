import os
import logging
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
        self.setWindowTitle("VLC Video Player Controls")
        self.setMinimumSize(810, 50)
        self.setMaximumSize(900, 150)
        self.setMinimumHeight(50)
        self.setMaximumHeight(150)
        self.video_window = None
        self.logger = logging.getLogger(__name__)
        self.instance = vlc.Instance()
        self.list_player = self.instance.media_list_player_new()
        self.media_list = self.instance.media_list_new()
        self.media_player = self.list_player.get_media_player()

        # Интерфейс
        self.play_button = QPushButton("PLAY")
        self.stop_button = QPushButton("STOP")
        self.next_button = QPushButton("NEXT")
        self.previous_button = QPushButton("PREV")
        self.playlist_button = QPushButton("PLAYLIST")
        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(50)
        self.progress_slider = QSlider(Qt.Horizontal)
        self.progress_slider.setRange(0, 100)
        self.time_label = QLabel("00:00 / 00:00")
        self.playlist_widget = QListWidget()
        self.playlist_widget.hide()  # Прячем список по умолчанию

        # Задание длины слайдеров
        self.volume_slider.setFixedWidth(50)
        self.progress_slider.setFixedWidth(200)

        # Layout
        control_layout = QHBoxLayout()
        control_layout.addWidget(self.progress_slider)
        control_layout.addWidget(self.time_label)
        control_layout.addWidget(self.play_button)
        control_layout.addWidget(self.stop_button)
        control_layout.addWidget(self.previous_button)
        control_layout.addWidget(self.next_button)
        control_layout.addWidget(self.playlist_button)
        control_layout.addWidget(QLabel("VOLUME"))
        control_layout.addWidget(self.volume_slider)

        main_layout = QVBoxLayout()
        main_layout.addLayout(control_layout)
        main_layout.addWidget(self.playlist_widget)
        self.setLayout(main_layout)

        # Стили             ("#4a4a4a", "#5c5c5c", "#000"),  # Dark gray : 0
        self.setStyleSheet("""
            QPushButton {
                background-color: #4a4a4a;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 5px;
            }
            QPushButton:hover {
                background-color: #5c5c5c;
            }
            QSlider::groove:horizontal {
                background: #bdc3c7;
                height: 8px;
                border-radius: 4px;
            }
            QSlider::handle:horizontal {
                background: #4a4a4a;
                width: 14px;
                height: 14px;
                margin: -3px 0;
                border-radius: 7px;
            }
            QLabel {
                color: #2c3e50;
                font-size: 14px;
            }
            QListWidget {
                background-color: #ecf0f1;
                border: 1px solid #bdc3c7;
                font-size: 14px;
            }
        """)

        # Сигналы
        self.play_button.clicked.connect(self.play_pause)
        self.stop_button.clicked.connect(self.stop_media)
        self.next_button.clicked.connect(self.next_media)
        self.previous_button.clicked.connect(self.previous_media)
        self.playlist_button.clicked.connect(self.toggle_playlist_visibility)
        self.playlist_widget.itemClicked.connect(self.play_selected_item)
        self.volume_slider.valueChanged.connect(self.set_volume)
        self.progress_slider.sliderReleased.connect(self.seek_position)

        # Таймер для обновления прогресса
        self.timer = QTimer(self)
        self.timer.setInterval(500)
        self.timer.timeout.connect(self.update_ui)

    def toggle_playlist_visibility(self):
        """Переключает видимость списка воспроизведения."""
        if self.playlist_widget.isVisible():
            self.playlist_widget.hide()
            self.resize(810, 50)
        else:
            self.playlist_widget.show()
            self.resize(810, 150)

    def load_playlist(self, path):
        """
        Загружает плейлист из файла или ссылки и отображает серии в списке.

        Args:
            path (str): Путь к локальному файлу или URL плейлиста.
        """
        self.playlist_widget.clear()  # Очищаем список серий

        try:
            if self.is_url(path):
                self.load_playlist_from_url(path)
            else:
                self.load_playlist_from_file(path)
        except Exception as e:
            self.logger.error(f"Ошибка при загрузке плейлиста: {e}")
            return

    def is_url(self, path):
        """Проверяет, является ли path URL."""
        return path.startswith(("http://", "https://"))

    def load_playlist_from_url(self, url):
        """Загружает и воспроизводит плейлист из URL."""
        try:
            media = self.instance.media_new(url)
            self.media_list.add_media(media)
            self.list_player.set_media_list(self.media_list)
            self.list_player.play()
            self.logger.info(f"Плейлист из URL загружен: {url}")
        except Exception as e:
            self.logger.error(f"Ошибка при загрузке плейлиста из URL: {e}")

    def load_playlist_from_file(self, file_path):
        """Загружает и воспроизводит плейлист из локального файла."""
        if not os.path.exists(file_path):
            self.logger.error(f"Файл плейлиста не найден: {file_path}")
            return

        try:
            with open(file_path, "r", encoding="utf-8") as playlist_file:
                for line in playlist_file:
                    line = line.strip()
                    if line and not line.startswith("#"):  # Игнорируем комментарии
                        media = self.instance.media_new(line)
                        self.media_list.add_media(media)
                        self.playlist_widget.addItem(line)  # Добавляем серию в список

            self.list_player.set_media_list(self.media_list)
            self.list_player.play()
            self.logger.info(f"Плейлист из файла загружен: {file_path}")
        except Exception as e:
            self.logger.error(f"Ошибка при чтении файла плейлиста: {e}")

    def play_selected_item(self, item):
        """Воспроизводит выбранную серию."""
        index = self.playlist_widget.row(item)
        self.list_player.play_item_at_index(index)
        self.timer.start()

    def play_pause(self):
        if self.media_player.is_playing():
            self.media_player.pause()
            self.play_button.setText("Play")
            self.timer.stop()
        else:
            self.list_player.play()
            self.play_button.setText("Pause")
            self.timer.start()

    def stop_media(self):
        self.list_player.stop()
        self.play_button.setText("Play")
        self.timer.stop()

    def set_volume(self, volume):
        self.media_player.audio_set_volume(volume)

    def seek_position(self):
        position = self.progress_slider.value() / 100
        self.media_player.set_position(position)

    def update_ui(self):
        if not self.media_player.is_playing():
            return

        length = self.media_player.get_length() / 1000
        current_time = self.media_player.get_time() / 1000

        if length > 0:
            position = int((current_time / length) * 100)
            self.progress_slider.setValue(position)

        self.time_label.setText(f"{self.format_time(current_time)} / {self.format_time(length)}")

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
            self.resize(810, 150)
        else:
            self.resize(810, 50)  # Устанавливаем фиксированный размер при попытке изменить
        event.accept()



