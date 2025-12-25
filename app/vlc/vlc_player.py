import base64
import json
import math
import os
import logging
import logging.config
import re
import ctypes
from pathlib import Path

import vlc
import time
import sys
import argparse

from PyQt5.QtGui import QIcon
from PyQt5.QtMultimediaWidgets import QVideoWidget
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QPushButton, QSlider, QLabel, QHBoxLayout, QListWidget, QApplication, \
    QStyle, QSystemTrayIcon
from PyQt5.QtCore import Qt, QTimer, QSharedMemory


ES_CONTINUOUS       = 0x80000000  # постоянный режим
ES_SYSTEM_REQUIRED  = 0x00000001  # предотвращает переход в спящий режим
ES_DISPLAY_REQUIRED = 0x00000002  # предотвращает отключение дисплея


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
    def __init__(self, parent=None, current_template="default", proxy=None, log=None, log_level="2"):
        super().__init__(parent)
        self.logger = logging.getLogger(__name__)
        self.current_template = current_template
        self.skip_data_cache = None
        self.current_episode = None
        self.skip_opening = None
        self.skip_ending = None
        self.is_buffering = None
        self.title_id = None
        self.proxy = proxy
        self.log = log
        self.verbose = log_level

        self.setWindowTitle("VLC Video Player Controls")
        self.setGeometry(100, 950, 850, 100)
        self.setMinimumSize(850, 100)
        self.setMaximumSize(850, 200)
        self.setMinimumHeight(100)
        self.setMaximumHeight(200)
        self.video_window = None

        log_path = Path("logs/vlc.log").resolve()
        cfg_path = Path("config/vlcrc").resolve()

        args = [
            "--network-caching=2000",
            "--http-reconnect",
            "--retry=3",
        ]

        if self.log:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            args.append(f"--verbose={self.verbose}")
            args.append("--file-logging")
            args.append(f"--logfile={log_path}")

        if self.proxy:
            self.logger.debug(f"Initializing VLC with proxy: {self.proxy!r}")
            args.append(f"--config={cfg_path}")
            args.append(f"--http-proxy={self.proxy}")

        self.instance = vlc.Instance(*args)
        if not self.instance:
            raise RuntimeError(f"Failed to init VLC (bad args?): {args}")

        self.logger.debug(f"VLC args: {args}")

        self.list_player = self.instance.media_list_player_new()
        self.media_list = self.instance.media_list_new()
        self.media_player = self.list_player.get_media_player()

        self.is_repeat = False
        self.is_seeking = False

        self._last_mrl = None
        self._last_time_ms = 0
        self._resume_probe_time_ms = 0
        self._resume_watchdog = QTimer(self)
        self._resume_watchdog.setSingleShot(True)
        self._resume_watchdog.timeout.connect(self._resume_watchdog_check)

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
        self.playlist_widget.hide()
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
        self.apply_theme()

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

        self.timer = QTimer(self)
        self.timer.setInterval(500)
        self.timer.timeout.connect(self.update_ui)

        self.sleep_timer = QTimer(self)
        self.sleep_timer.setInterval(30000)
        self.sleep_timer.timeout.connect(self.prevent_sleep)
        self.sleep_timer.start()

    def apply_theme(self):
        """Применяет стили к VLC Player с учетом текущего шаблона."""

        if self.current_template == "default":
            background_style = "background-color: rgba(240, 240, 240, 1.0);"
        elif self.current_template == "no_background_night":
            background_style = "background-color: rgba(200, 200, 200, 0.5);"
        elif self.current_template == "no_background":
            background_style = "background-color: rgba(240, 240, 240, 1.0);"
        else:
            background_style = ""

        control_styles = """
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
                background: #bdc3c7;
                height: 25px;
                border-radius: 5px;
            }
            QSlider::handle:horizontal {
                background: #4a4a4a;
                width: 50px;
                height: 25px;
                margin: -1px 0;
            }
            QSlider::sub-page:horizontal {
                background: #7f7f7f;
            }
            QSlider::add-page:horizontal {
                background: #AAADAD;
                border-radius: 5px;
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
        """
        self.setStyleSheet(f"QWidget {{ {background_style} }} {control_styles}")

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
            os.makedirs(screenshots_dir)

        screenshot_path = os.path.join(screenshots_dir, f"screenshot_{self.title_id}_{self.get_timestamp()}.png")
        result = self.media_player.video_take_snapshot(0, screenshot_path, 0, 0)
        if result == 0:
            self.logger.info(f"Screenshot saved: {screenshot_path}")
        else:
            self.logger.error("Failed to take screenshot.")

    @staticmethod
    def get_timestamp():
        """Возвращает текущий таймкод в формате ЧЧ-ММ-СС."""
        return time.strftime("%H-%M-%S")

    def toggle_playlist_visibility(self):
        """Переключает видимость списка воспроизведения."""
        if self.playlist_widget.isVisible():
            self.playlist_widget.hide()
            self.resize(850, 100)
        else:
            self.playlist_widget.show()
            self.resize(850, 200)

    @staticmethod
    def is_url(path):
        """
        Проверяет, является ли path полным URL.

        Args:
            path: строка для проверки

        Returns:
            bool: True если это полный URL с протоколом
        """
        return path.startswith(("http://", "https://"))

    def load_playlist(self, path, title_id, skip_data=None):
        """
        Загружает плейлист из файла или ссылки и отображает серии в списке.

        Args:
            path (str): Путь к локальному файлу или URL плейлиста.
            title_id (str): Идентификатор текущего тайтла.
            skip_data (str): Закодированные данные о пропусках в base64.
        """
        self.playlist_widget.clear()
        self.title_id = title_id

        if skip_data:
            try:
                skip_data_json = base64.urlsafe_b64decode(skip_data.encode()).decode()
                self.skip_data_cache = json.loads(skip_data_json)
                self.logger.debug(f"Decoded skip_data: {self.skip_data_cache}")
            except Exception as e:
                self.logger.error(f"Failed to decode skip_data: {e}")
                self.skip_data_cache = None
        else:
            self.skip_data_cache = None

        try:
            if self.is_url(path):
                self.load_playlist_from_url(path, title_id)
            else:
                self.load_playlist_from_file(path, title_id)
        except Exception as e:
            self.logger.error(f"!!! Error playing playlist file: {e}", exc_info=True)

    def _clean_int(self, s: str) -> int:
        """Преобразует строку в int, отбрасывая ведущие нули."""
        return int(s.lstrip('0') or '0')

    def extract_from_link(self, url: str):
        """
        Возвращает (episode_number, episode_quality) как int.
        Поддерживает разные форматы URL.
        """
        try:
            m = re.search(r"/(\d+)/(\d+)/(\d+)/", url)
            if m:
                episode_number = self._clean_int(m.group(2))
                episode_quality = self._clean_int(m.group(3))
                self.logger.debug(
                    f"Parsed (old style) – episode:{episode_number}, quality:{episode_quality}"
                )
                return episode_number, episode_quality

            m = re.search(r"/(\d+)_\w+/[^/]+/(\d+)/", url)
            if m:
                episode_number = self._clean_int(m.group(1))
                episode_quality = self._clean_int(m.group(2))
                self.logger.debug(
                    f"Parsed (new style) – episode:{episode_number}, quality:{episode_quality}"
                )
                return episode_number, episode_quality

            parts = [p for p in url.split('/') if p.isdigit()]
            if len(parts) >= 2:
                episode_number = self._clean_int(parts[-2])
                episode_quality = self._clean_int(parts[-1])
                self.logger.debug(
                    f"Fallback parsing – episode:{episode_number}, quality:{episode_quality}"
                )
                return episode_number, episode_quality

            raise ValueError("No recognizable episode/quality pattern found")
        except Exception as exc:
            self.logger.error(f"!!! Error extracting from URL '{url}': {exc}")
            return None

    def load_playlist_from_url(self, url, title_id):
        """
        Загружает и воспроизводит один эпизод по URL.
        ВАЖНО: Ожидается ПОЛНЫЙ URL от app.py:
        https://cache.libria.fun/videos/media/ts/9978/1/1080/hash.m3u8
        https://aser.pro/content/stream/provozhayushhaya_v_poslednij_put_friren/001_27218/hls/720/index.m3u8
        https://example.com/abc/12/1080/video.m3u8
        """
        try:
            if not self.is_url(url):
                self.logger.error(f"Expected full URL, got: {url}")
                return

            episode_number, episode_quality = self.extract_from_link(url)
            self.current_episode = episode_number
            self.logger.debug(f"Playing title {title_id} episode {episode_number}")

            skip_opening, skip_ending = None, None
            if self.skip_data_cache and self.skip_data_cache.get("episode_number") == episode_number:
                skip_opening = self.skip_data_cache.get("skip_opening", [])
                skip_ending = self.skip_data_cache.get("skip_ending", [])

            self.logger.debug(f"Episode {episode_number}: Skip opening: {skip_opening}, Skip ending: {skip_ending}")

            media = self.instance.media_new(url)
            self.media_list.add_media(media)
            self.playlist_widget.addItem(url)
            self.list_player.set_media_list(self.media_list)
            self.list_player.play()

            self.logger.info(f"Playing stream URL: {url[-50:]}")
        except Exception as e:
            self.logger.error(f"Error playing stream URL: {e}", exc_info=True)

    def load_playlist_from_file(self, file_path, title_id):
        """
        Загружает и воспроизводит плейлист из локального файла.
        ВАЖНО: Плейлист должен содержать ПОЛНЫЕ URL.
        """
        if not os.path.exists(file_path):
            self.logger.error(f"Playlist file not found: {file_path}")
            return

        try:
            with open(file_path, "r", encoding="utf-8") as playlist_file:
                for line in playlist_file:
                    link = line.strip()

                    if not link or link.startswith("#"):
                        continue

                    if not self.is_url(link):
                        self.logger.warning(f"Skipping invalid URL: {link}")
                        continue

                    episode_number, episode_quality = self.extract_from_link(link)
                    self.current_episode = episode_number
                    self.logger.debug(f"Cached {title_id} Episode {self.current_episode}")

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
                    self.playlist_widget.addItem(link)

            self.list_player.set_media_list(self.media_list)
            self.list_player.play()
            self.logger.info(f"Playlist playing from file: {file_path}")
        except Exception as e:
            self.logger.error(f"Error playing playlist file: {e}", exc_info=True)

    def play_selected_item(self, item):
        """Воспроизводит выбранную серию."""
        index = self.playlist_widget.row(item)
        self.list_player.play_item_at_index(index)
        self.timer.start()

    @staticmethod
    def prevent_sleep():
        """Предотвращает переход системы в спящий режим и отключение дисплея."""
        try:
            ctypes.windll.kernel32.SetThreadExecutionState(
                ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED
            )
        except Exception as e:
            logging.getLogger(__name__).error("Error preventing sleep: %s", e)

    @staticmethod
    def allow_sleep():
        """Разрешает системе переход в спящий режим (сбрасывает флаги)."""
        try:
            ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS)
        except Exception as e:
            logging.getLogger(__name__).error("Error allowing sleep: %s", e)

    def _resume_watchdog_check(self):
        try:
            st = self.media_player.get_state()

            # если VLC ещё "раскачивается" — дадим шанс, но ограниченно
            if st in (vlc.State.Opening, vlc.State.Buffering):
                self._resume_watchdog.start(1500)
                return

            # ключевая проверка: двигается ли время
            now_t = self.media_player.get_time() or 0
            probe_t = self._resume_probe_time_ms or 0

            # если time пошёл — всё ок
            if now_t > probe_t + 300:  # 0.3 сек допуск
                return

            # если state "Playing", но time стоит — это и есть залипание
            self._force_reload_current()

        except Exception:
            self.logger.exception("resume watchdog failed")

    def _force_reload_current(self):
        mrl = None
        media = self.media_player.get_media()
        if media:
            mrl = media.get_mrl()
        if not mrl:
            mrl = self._last_mrl
        if not mrl:
            self.logger.warning("No MRL to reload.")
            return

        resume_time = self.media_player.get_time() or self._last_time_ms or 0
        self.logger.warning(f"Reloading stream after stalled resume. mrl={mrl[-80:]} time={resume_time}ms")

        try:
            self.media_player.stop()
            new_media = self.instance.media_new(mrl)
            self.media_player.set_media(new_media)
            self.media_player.play()

            # восстановим позицию чуть позже, когда стартанёт декодер
            QTimer.singleShot(1200, lambda: self._restore_time_safe(resume_time))
        except Exception:
            self.logger.exception("Failed to force reload.")

    def _restore_time_safe(self, resume_time_ms: int):
        try:
            if resume_time_ms > 0:
                self.media_player.set_time(resume_time_ms)
        except Exception:
            self.logger.exception("Failed to restore time after reload.")

    def play_pause(self):
        """Простой переключатель воспроизведения/паузы без автоматического пропуска титров."""
        st = self.media_player.get_state()  # vlc.State.*
        if st == vlc.State.Playing:
            self.media_player.set_pause(1)
            self.play_button.setText("PLAY")
            self.timer.stop()
            self.sleep_timer.stop()
            self.allow_sleep()
            return

        # Если было Paused/Stopped/Ended/Error — пробуем resume
        self.media_player.set_pause(0)  # если реально paused — снимет паузу
        self.media_player.play()  # если stopped/error — попробует стартануть

        self.play_button.setText("PAUSE")
        self.timer.start()
        self.sleep_timer.start()
        self.prevent_sleep()

        self._resume_probe_time_ms = self.media_player.get_time() or self._last_time_ms or 0
        self._resume_watchdog.start(1500)

    def stop_media(self):
        self.list_player.stop()
        self.play_button.setText("PLAY")
        self.timer.stop()
        self.allow_sleep()

    def set_volume(self, volume):
        self.media_player.audio_set_volume(volume)

    def slider_clicked(self, event):
        """Обрабатывает клик по слайдеру и перемещает ручку с учётом буферизации."""
        if event.button() == Qt.LeftButton:
            slider_width = self.progress_slider.width()
            click_position = event.pos().x()
            new_value = int((click_position / slider_width) * self.progress_slider.maximum())
            self.progress_slider.setValue(new_value)
            self.seek_position_with_buffer()

    def seek_position(self):
        """Перематывает воспроизведение на указанное положение с кратковременной паузой."""
        self.is_seeking = True
        if self.media_player.is_playing():
            self.media_player.pause()
        position = self.progress_slider.value() / 100
        self.media_player.set_position(position)
        QTimer.singleShot(500, self.resume_playback)

    def seek_position_with_buffer(self):
        """Перематывает потоковое видео с ожиданием загрузки."""
        self.is_buffering = True
        self.is_seeking = True
        if self.media_player.is_playing():
            self.media_player.pause()
        position = self.progress_slider.value() / 100
        self.media_player.set_position(position)
        QTimer.singleShot(1000, self.resume_stream)

    def resume_stream(self):
        """Возобновляет потоковое воспроизведение после буферизации."""
        if not self.media_player.is_playing():
            self.media_player.play()
        self.is_buffering = False
        self.is_seeking = False

    def resume_playback(self):
        """Возобновляет воспроизведение после перемотки."""
        self.is_seeking = False
        if not self.media_player.is_playing():
            self.media_player.play()
        self.play_button.setText("PAUSE")
        self.timer.start()

    @staticmethod
    def format_time(seconds):
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
        self.stop_media()
        if self.video_window is not None:
            self.video_window.close()
        self.list_player.release()
        self.media_player.release()
        self.instance.release()
        event.accept()
        self.logger.info("Custom VLC player is closed.")

    def resizeEvent(self, event):
        """Ограничивает размер окна при попытке изменения."""
        if self.playlist_widget.isVisible():
            self.resize(850, 200)
        else:
            self.resize(850, 100)
        event.accept()

    def update_ui(self):
        """Обновляет прогресс-бар, таймер и подсвечивает текущую серию."""
        try:
            st = self.media_player.get_state()

            # кэшировать MRL и time можно почти всегда (кроме NothingSpecial/Stopped без media)
            media = self.media_player.get_media()
            if media:
                self._last_mrl = media.get_mrl()

            t = self.media_player.get_time()
            if t is not None and t >= 0:
                self._last_time_ms = t

            # UI можно обновлять если хоть что-то загружено
            if st in (vlc.State.Playing, vlc.State.Paused, vlc.State.Buffering, vlc.State.Opening):
                length = max((self.media_player.get_length() or 0) / 1000, 0)
                current_time = max((self.media_player.get_time() or 0) / 1000, 0)

                if length > 0:
                    pos = int((current_time / length) * 100)
                    self.progress_slider.setValue(pos)

                self.time_label.setText(f"{self.format_time(current_time)} / {self.format_time(length)}")

            # кнопку можно выставлять по state
            if st == vlc.State.Paused:
                self.play_button.setText("PLAY")
            elif st == vlc.State.Playing:
                self.play_button.setText("PAUSE")

        except Exception as e:
            self.logger.error(f"An error occurred while updating UI: {e}", exc_info=True)

    def update_playlist_highlight(self):
        """Подсвечивает текущую серию в плейлисте."""
        current_media = self.media_player.get_media()
        if not current_media:
            return
        current_url = current_media.get_mrl()
        for i in range(self.playlist_widget.count()):
            item = self.playlist_widget.item(i)
            if item.text() == current_url:
                item.setBackground(Qt.lightGray)
                item.setForeground(Qt.black)
            else:
                item.setBackground(Qt.white)
                item.setForeground(Qt.black)

    def handle_skip_credits(self):
        """Обрабатывает нажатие кнопки SKIP CREDITS – выполняется единичный пропуск титров."""
        self.logger.info("SKIP CREDITS button pressed.")
        self.perform_skip_credits()

    def perform_skip_credits(self):
        """
        По кнопке пропуска:
          - если находимся в диапазоне открывающих титров -> перематываем к его концу;
          - если находимся в диапазоне закрывающих титров -> перематываем к его концу (НЕ next),
            чтобы не пропустить возможную сцену после титров;
          - авто-next только если мы уже у самого конца файла (tail_guard).
        """

        TAIL_GUARD = 2.0  # сек: считаем, что <2с до конца — можно авто-next (если нужно)
        EPS = 0.25  # сек: небольшая погрешность на сравнения

        def _as_pair_or_none(val):
            """
            Превращает вход в (start, end) с float секундами или None.
            Поддерживает: None, [], [None,None], ["146","230"], [146,230], tuple.
            Гарантирует start < end.
            """
            if not val:
                return None
            if isinstance(val, (list, tuple)) and len(val) == 2:
                a, b = val
            else:
                return None
            try:
                if a is None or b is None:
                    return None
                a = float(a)
                b = float(b)
            except (TypeError, ValueError):
                return None
            if not (math.isfinite(a) and math.isfinite(b)):
                return None
            if b <= a:
                return None
            return a, b

        try:
            episode_number = self.get_playing_episode_number()
            if episode_number is None:
                self.logger.warning("Unable to determine episode number for skipping credits.")
                return

            self.get_episode_skips(episode_number)
            current_time = (self.media_player.get_time() or 0) / 1000.0  # ms -> s
            total_length = max(((self.media_player.get_length() or 0) / 1000.0), 0.0)

            opening = _as_pair_or_none(getattr(self, "skip_opening", None))
            ending = _as_pair_or_none(getattr(self, "skip_ending", None))

            if opening:
                start_o, end_o = opening
                if current_time + EPS < end_o:
                    new_pos = min(end_o / total_length, 0.9999) if total_length > 0 else None
                    self.logger.info(
                        f"Skip opening [{start_o/60:.2f}-{end_o/60:.2f}]m: {current_time/60:.2f}m -> {end_o/60:.2f}m"
                    )
                    if new_pos is not None:
                        self.media_player.set_position(new_pos)
                        return

            if ending:
                start_e, end_e = ending
                if end_e > current_time + EPS >= start_e:
                    jump_to = min(end_e,
                                  max(total_length - TAIL_GUARD, 0.0))
                    new_pos = min(jump_to / total_length, 0.9999) if total_length > 0 else None
                    self.logger.info(
                        f"Skip ending [{start_e/60:.2f}-{end_e/60:.2f}]m: {current_time/60:.2f}m -> {jump_to/60:.2f}m"
                    )
                    if new_pos is not None:
                        self.media_player.set_position(new_pos)
                        return

            if total_length > 0 and (total_length - current_time) <= TAIL_GUARD:
                self.logger.info("Near file end — moving to next media.")
                self.media_player.stop()
                self.next_media()
                return

            self.logger.info("No applicable credits skip region found at the current time.")

        except Exception as e:
            self.logger.exception(f"perform_skip_credits failed: {e}")

    def get_episode_skips(self, episode_number):
        """
        Извлекает диапазоны для пропуска открывающих и закрывающих титров для данного эпизода.
        Args:
            episode_number (int): номер эпизода.
        """
        skip_opening, skip_ending = None, None
        if self.skip_data_cache:
            entries = self.skip_data_cache.get("episode_skips")
            if not entries:
                entries = [self.skip_data_cache]
            for skip_entry in entries:
                if skip_entry.get("episode_number") == episode_number:
                    try:
                        skip_opening = json.loads(skip_entry.get("skip_opening", "[]"))
                    except Exception:
                        skip_opening = skip_entry.get("skip_opening", [])
                    try:
                        skip_ending = json.loads(skip_entry.get("skip_ending", "[]"))
                    except Exception:
                        skip_ending = skip_entry.get("skip_ending", [])
                    break
        self.skip_opening = skip_opening
        self.skip_ending = skip_ending

    def get_playing_episode_number(self):
        """
        Извлекает номер текущего эпизода на основе URL текущего медиа.
        Returns:
            int или None: номер эпизода, если удалось определить.
        """
        media = self.media_player.get_media()
        if media:
            url = media.get_mrl()
            match = re.search(r"/\d+/(\d+)/", url)
            if match:
                return int(match.group(1))
        return None

    def get_episode_number(self, url):
        """
        Извлекает номер эпизода из URL.
        Returns:
            int или None: номер эпизода, если удалось определить.
        """
        media = self.media_player.get_media()
        if media:
            url = media.get_mrl()
            match = re.search(r"/\d+/(\d+)/", url)
            if match:
                return int(match.group(1))
        return None

if __name__ == "__main__":
    if getattr(sys, 'frozen', False):
        log_dir = os.path.join(os.path.dirname(sys.executable), 'logs')

        try:
            logging.config.fileConfig(os.path.join(os.path.dirname(sys.executable), 'config', 'logging.conf'),
                                      disable_existing_loggers=False)
        except Exception as e:
            logging.basicConfig(
                level=logging.DEBUG,
                format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                filename=os.path.join(log_dir, 'vlc_player.log')
            )
            logging.error(f"Could not load logging config: {e}")

    parser = argparse.ArgumentParser(description='VLC Player')
    parser.add_argument('--playlist', help='Path to playlist or m3u8 URL')
    parser.add_argument('--title_id', type=int, help='Title ID')
    parser.add_argument('--skip_data', help='Base64 encoded skip data')
    parser.add_argument('--template', default="default", help='UI template name')
    parser.add_argument('--proxy', help='Use SOCK proxy')
    parser.add_argument('--log', help='Use logs')
    parser.add_argument('--verbose', help='Verbose level')
    parser.add_argument('--prod_key')
    args = parser.parse_args()

    icon_path = os.path.join('static', 'icon.png')
    icon_path = os.path.normpath(icon_path)

    app = QApplication(sys.argv)
    app.setApplicationName("Anime Player VLC")
    app.setWindowIcon(QIcon(icon_path))

    if args.prod_key:
        unique_key = str(args.prod_key) + '-APV'
        shared_memory = QSharedMemory(unique_key)
        if not shared_memory.create(1):
            logging.getLogger().error("Anime Player VLC player is already running!")
            sys.exit(1)

        player = VLCPlayer(current_template=args.template, proxy=args.proxy, log=args.log, log_level=args.verbose)

        if args.playlist:
            player.load_playlist(args.playlist, args.title_id, args.skip_data)

        player.show()
        player.timer.start()

    else:
        message = "VLC player cannot be run without AnimePlayer application!"
        logging.getLogger().error(message)
        tray_icon = QSystemTrayIcon()
        tray_icon.setIcon(app.style().standardIcon(QStyle.SP_MessageBoxWarning))
        tray_icon.show()
        tray_icon.showMessage("Error", message, QSystemTrayIcon.Warning, 5000)
        QTimer.singleShot(500, lambda: sys.exit(1))

    sys.exit(app.exec_())