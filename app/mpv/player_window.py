# app/mpv/player_window.py
from __future__ import annotations

import os
import re
import json
import math
import time
import base64
import ctypes
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QSlider, QLineEdit, QLabel, QFrame,
    QListWidget, QListWidgetItem, QFileDialog, QMessageBox
)

from app.mpv.base_engine import PlayerEngine


ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001
ES_DISPLAY_REQUIRED = 0x00000002
BTN_H = 25
SLIDER_H = 16
EPS = 0.25
TAIL_GUARD = 3.0

def fmt_ms(ms: int) -> str:
    ms = max(0, ms)
    s = ms // 1000
    m = s // 60
    s = s % 60
    h = m // 60
    m = m % 60
    return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


class ClickSlider(QSlider):
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            if self.orientation() == Qt.Horizontal:
                x = event.pos().x()
                ratio = x / max(1, self.width())
                val = self.minimum() + int((self.maximum() - self.minimum()) * ratio)
                self.setValue(val)
                self.sliderMoved.emit(val)
                self.sliderReleased.emit()
                event.accept()
                return
        super().mousePressEvent(event)


class VideoWindow(QMainWindow):
    def __init__(self, parent=None, on_user_close=None):
        super().__init__(parent)
        self._on_user_close = on_user_close
        self.setWindowTitle("Video")

        self.video = QFrame(self)

        # ВАЖНО для Windows/mpv: гарантировать нативный HWND
        self.video.setAttribute(Qt.WA_NativeWindow, True)
        self.video.setAttribute(Qt.WA_DontCreateNativeAncestors, True)

        self.video.setStyleSheet("background: black;")
        self.setCentralWidget(self.video)

    def win_id(self) -> int:
        # winId будет валиден после show()/processEvents()
        return int(self.video.winId())

    def closeEvent(self, event):
        try:
            if callable(self._on_user_close):
                self._on_user_close()
        finally:
            event.accept()


class PlayerWindow(QMainWindow):
    def __init__(
            self,
            engine: PlayerEngine,
            *,
            playlist: str | None = None,
            title_id: int | None = None,
            skip_data: str | None = None,
            proxy: str | None = None,
            autoplay: bool = True,
            template: str | None = None,
    ):
        super().__init__()

        self.engine = engine
        self.logger = logging.getLogger(__name__)
        self.apply_template(template)

        # входные параметры
        self.title_id: int | None = title_id
        self.skip_data_cache: dict | None = None
        self.skip_opening = None
        self.skip_ending = None
        self.proxy = proxy
        self.autoplay = autoplay

        self._skip_data_b64: str | None = skip_data
        if skip_data:
            self._decode_skip_data(skip_data)

        self._cur_index = 0
        self._switch_in_progress = None
        self._closing = False
        self._early_error_retry = {}
        self._repeat_enabled: bool = False

        # НОВОЕ: флаг готовности движка
        self._engine_ready = False

        # плейлист
        self.playlist_urls: list[str] = []
        self.playlist_index: int = 0

        # watchdog
        self._dragging = False
        self._wd_last_time_ms: Optional[int] = None
        self._wd_stuck_count: int = 0
        self._wd_timer = QTimer(self)
        self._wd_timer.setInterval(1500)
        self._wd_timer.timeout.connect(self._resume_watchdog_check)

        self.setWindowTitle("Mini Player (mpv)")
        self.resize(850, 100)
        self.setMinimumSize(850, 100)
        self.setMaximumSize(850, 200)
        self.setMinimumHeight(100)
        self.setMaximumHeight(200)

        root = QFrame(self)
        root.setObjectName("RootPanel")
        self.setCentralWidget(root)
        v = QVBoxLayout(root)

        # video surface - создаём но НЕ показываем сразу
        self.video_window = VideoWindow(on_user_close=self._on_video_window_user_close)
        self.video_window.hide()

        # КРИТИЧНО: устанавливаем WID СИНХРОННО и ждём готовности
        self._init_engine_wid()

        # URL / playlist row
        row_url = QHBoxLayout()
        self.url = QLineEdit(root)
        self.url.setPlaceholderText("URL / stream / path-to-playlist ...")
        btn_load = QPushButton("LOAD", root)
        btn_load.clicked.connect(self.on_load_clicked)
        btn_open = QPushButton("OPEN", root)
        btn_open.clicked.connect(self.on_open_file)
        row_url.addWidget(self.url, 1)
        row_url.addWidget(btn_load)
        row_url.addWidget(btn_open)
        v.addLayout(row_url)

        # controls row
        row_ctl = QHBoxLayout()
        self.btn_prev = QPushButton("PREV", root)
        self.btn_next = QPushButton("NEXT", root)
        self.btn_play = QPushButton("PLAY", root)
        self.btn_stop = QPushButton("STOP", root)
        self.btn_repeat = QPushButton("REPEAT", root)
        self.btn_skip = QPushButton("SKIP CREDITS", root)
        self.btn_shot = QPushButton("SCREENSHOT", root)
        self.btn_playlist = QPushButton("PLAYLIST", root)

        self.btn_prev.clicked.connect(self.prev_media)
        self.btn_next.clicked.connect(self.next_media)
        self.btn_play.clicked.connect(self.on_play_pause)
        self.btn_stop.clicked.connect(self.on_stop)
        self.btn_repeat.clicked.connect(self.toggle_repeat)
        self.btn_skip.clicked.connect(self.handle_skip_credits)
        self.btn_shot.clicked.connect(self.take_screenshot)
        self.btn_playlist.clicked.connect(self.toggle_playlist_visibility)

        row_ctl.addWidget(self.btn_prev)
        row_ctl.addWidget(self.btn_next)
        row_ctl.addWidget(self.btn_play)
        row_ctl.addWidget(self.btn_stop)
        row_ctl.addWidget(self.btn_repeat)
        row_ctl.addWidget(self.btn_skip)
        row_ctl.addWidget(self.btn_shot)
        row_ctl.addWidget(self.btn_playlist)

        self.vol = QSlider(Qt.Horizontal, root)
        self.vol.setRange(0, 100)
        self.vol.setValue(100)
        self.vol.valueChanged.connect(lambda x: self.engine.set_volume(x))
        row_ctl.addWidget(self.vol, 1)
        v.addLayout(row_ctl)

        # playlist widget
        self.playlist_widget = QListWidget(root)
        self.playlist_widget.itemDoubleClicked.connect(self.on_playlist_double_click)
        v.addWidget(self.playlist_widget, stretch=0)

        # progress
        row_prog = QHBoxLayout()
        self.lbl_time = QLabel("00:00 / 00:00", root)
        self.prog = ClickSlider(Qt.Horizontal, root)
        self.prog.setRange(0, 1000)
        self.prog.sliderPressed.connect(self._on_seek_press)
        self.prog.sliderReleased.connect(self._on_seek_release)
        self.prog.sliderMoved.connect(self._on_seek_move)
        row_prog.addWidget(self.lbl_time)
        row_prog.addWidget(self.prog, 1)
        v.addLayout(row_prog)

        # events
        self.engine.on_eof = self.on_eof
        self.engine.on_error = self.on_error

        # ui timer
        self.t = QTimer(self)
        self.t.setInterval(300)
        self.t.timeout.connect(self._tick)

        # размеры кнопок
        for b in (self.btn_skip, self.btn_play, self.btn_prev, self.btn_stop,
                  self.btn_next, self.btn_repeat, self.btn_playlist, self.btn_shot):
            b.setFixedHeight(BTN_H)
            b.setMinimumWidth(50)
        self.vol.setFixedHeight(SLIDER_H)
        self.prog.setFixedHeight(SLIDER_H)
        self.lbl_time.setMinimumWidth(100)

        self.playlist_widget.hide()
        self._seeking_until = 0.0
        self._switching_track = False
        self._last_switch_ts = 0.0
        self._last_switch_index = 0

        # КРИТИЧНО: применяем входные данные ТОЛЬКО после инициализации движка
        if playlist:
            self.url.setText(playlist)
            # Отложенная загрузка - даём UI время на инициализацию
            QTimer.singleShot(150, lambda: self._deferred_playlist_load(playlist, title_id, skip_data))

        # Запускаем UI таймер только после полной готовности
        QTimer.singleShot(200, self.t.start)

    def _init_engine_wid(self):
        """
        КРИТИЧЕСКАЯ ФУНКЦИЯ: устанавливает WID синхронно
        Аналогия: подключаем проектор к плееру ДО нажатия Play
        """
        try:
            # Форсируем обработку событий Qt чтобы окно точно создалось
            from PyQt5.QtWidgets import QApplication
            QApplication.processEvents()

            win_id = self.video_window.win_id()
            self.logger.info(f"Setting video widget WID: {win_id}")

            self.engine.set_video_widget(win_id)
            self._engine_ready = True
            self.logger.info("Engine ready for playback")

        except Exception as e:
            self.logger.error(f"Failed to initialize engine WID: {e}", exc_info=True)
            self.on_error(f"Critical: Failed to initialize video output: {e}")
            self._engine_ready = False

    def _deferred_playlist_load(self, playlist: str, title_id: int | None, skip_data: str | None):
        """Отложенная загрузка плейлиста после готовности движка"""
        if not self._engine_ready:
            self.logger.warning("Engine not ready, delaying playlist load")
            QTimer.singleShot(200, lambda: self._deferred_playlist_load(playlist, title_id, skip_data))
            return

        self.logger.info(f"Loading playlist: {playlist}")
        self.load_playlist(playlist, title_id, skip_data=skip_data)

    # -------------------------
    # helpers (из vlc_player.py)
    # -------------------------
    def is_url(self, path: str) -> bool:
        return bool(re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", path))

    def _clean_int(self, s: str) -> int:
        try:
            return int(s)
        except Exception:
            digits = "".join(ch for ch in s if ch.isdigit())
            return int(digits) if digits else 0

    def extract_from_link(self, url: str) -> Optional[Tuple[int, int]]:
        """
        Взято по смыслу из твоего vlc_player.extract_from_link()
        Возвращает (episode_number, episode_quality) или None
        """
        try:
            # index.m3u8 формат
            # .../<episode>/<quality>/.../index.m3u8
            m = re.search(r"/(\d+)/(\d+)/(?:[^/]+/)*index\.m3u8", url)
            if m:
                return self._clean_int(m.group(1)), self._clean_int(m.group(2))

            # generic: .../<episode>/<quality>/...
            parts = [p for p in url.split("/") if p.isdigit()]
            if len(parts) >= 2:
                return self._clean_int(parts[-2]), self._clean_int(parts[-1])

            return None
        except Exception:
            return None

    def _decode_skip_data(self, skip_data: str) -> None:
        try:
            skip_data_json = base64.urlsafe_b64decode(skip_data.encode()).decode()
            self.skip_data_cache = json.loads(skip_data_json)
        except Exception:
            self.skip_data_cache = None

    def load_playlist(self, path: str, title_id: int | None, skip_data: str | None = None) -> None:
        self.title_id = title_id

        if skip_data is None:
            skip_data = self._skip_data_b64
        else:
            self._skip_data_b64 = skip_data  # обновили “источник истины”

        if skip_data:
            self._decode_skip_data(skip_data)
        else:
            self.skip_data_cache = None

        self.playlist_urls.clear()
        self.playlist_widget.clear()
        self.playlist_index = 0

        if self.is_url(path):
            self.load_playlist_from_url(path)
        else:
            self.load_playlist_from_file(path)

        if self.playlist_urls and self.autoplay:
            self.play_index(0)

    def load_playlist_from_url(self, url: str) -> None:
        # Одиночная ссылка — как один эпизод
        if not self.is_url(url):
            self.on_error(f"Expected full URL, got: {url}")
            return
        self.playlist_urls.append(url)
        self.playlist_widget.addItem(url)

    def load_playlist_from_file(self, file_path: str) -> None:
        p = Path(file_path)
        if not p.exists():
            self.on_error(f"Playlist file not found: {file_path}")
            return

        lines = p.read_text(encoding="utf-8", errors="ignore").splitlines()
        for line in lines:
            link = line.strip()
            if not link:
                continue
            if link.startswith("#"):
                continue  # #EXTM3U, #EXTINF, etc.
            if not self.is_url(link):
                self.on_error(f"Expected full URL, got: {link}")
                continue
            self.playlist_urls.append(link)
            self.playlist_widget.addItem(link)

    def load_source(self, src: str, title_id: int | None):
        src = src.strip()
        if not src:
            return

        # URL — оставляем как было (одиночная ссылка)
        if self.is_url(src):
            self.load_playlist(src, title_id, skip_data=None)  # оно само очистит urls/widget/index
            return

        p = Path(src)
        if not p.exists():
            self.on_error(f"File not found: {src}")
            return

        ext = p.suffix.lower()

        # плейлист
        if ext in (".m3u", ".m3u8"):
            self.load_playlist(src, title_id, skip_data=None)
            return

        # одиночный медиафайл (видео/аудио)
        self.playlist_urls = [str(p)]
        self.playlist_widget.clear()
        self.playlist_widget.addItem(str(p))
        self.playlist_index = 0
        if self.autoplay:
            self.play_index(0)

    # -------------------------
    # playback controls
    # -------------------------
    def on_load_clicked(self):
        self.load_source(self.url.text(), self.title_id)

    def on_open_file(self):
        fn, _ = QFileDialog.getOpenFileName(self, "Open playlist file", "playlists", "Media / Playlists (*.m3u *.m3u8 *.mp4 *.mkv *.avi *.mov *.webm *.mp3 *.m4a *.flac *.wav)")
        if fn:
            self.url.setText(fn)
            self.load_source(fn, self.title_id)

    def play_index(self, idx: int):
        if self._closing:
            return

        # показать видео-окно при старте воспроизведения
        if not self.video_window.isVisible():
            self.video_window.show()
            from PyQt5.QtWidgets import QApplication
            QApplication.processEvents()

        # если WID еще не ставили — ставим сейчас (после show)
        if not self._engine_ready:
            try:
                win_id = self.video_window.win_id()
                self.logger.info(f"Setting video widget WID (late): {win_id}")
                self.engine.set_video_widget(win_id)
                self._engine_ready = True
            except Exception as e:
                self.logger.error(f"Failed to init WID: {e}", exc_info=True)
                self.on_error(f"Critical: Failed to initialize video output: {e}")
                return

        if getattr(self, "_switch_in_progress", False):
            self.logger.warning("Switch already in progress, ignoring play_index(%s)", idx)
            return

        if not (0 <= idx < len(self.playlist_urls)):
            self.logger.warning(f"Invalid playlist index: {idx}")
            return

        self._switch_in_progress = True
        self._last_switch_ts = time.time()
        self._last_switch_index = idx

        self.playlist_index = idx
        self.update_playlist_highlight()
        self.playlist_widget.setCurrentRow(idx)
        self.playlist_widget.scrollToItem(self.playlist_widget.item(idx))

        url = self.playlist_urls[idx]

        # показать видео-окно при старте воспроизведения
        if not self.video_window.isVisible():
            self.video_window.show()

        self._set_controls_enabled(False)
        try:
            self.t.stop()
        except Exception:
            pass

        # Небольшая задержка для стабильности
        QTimer.singleShot(300, lambda u=url: self._do_load(u))

    def _do_load(self, url: str):
        """Загрузка и запуск воспроизведения"""
        if self._closing:
            return

        if not self._engine_ready:
            self.logger.error("Cannot load - engine not ready")
            self._clear_switch_flag()
            return

        try:
            self.logger.info(f"Loading URL: {url}")
            self.engine.load(url)

            # Даём движку время на загрузку метаданных
            QTimer.singleShot(300, lambda: self._start_playback())

        except Exception as e:
            self.logger.error(f"Load failed: {e}", exc_info=True)
            self.on_error(f"Failed to load: {e}")
            self._clear_switch_flag()

    def _start_playback(self):
        """Запуск воспроизведения после загрузки"""
        if self._closing:
            return

        try:
            self.engine.play()
            self._start_watchdog()
        except Exception as e:
            self.logger.error(f"Playback start failed: {e}", exc_info=True)
            self.on_error(f"Failed to start playback: {e}")
        finally:
            QTimer.singleShot(400, self._clear_switch_flag)

    def _clear_switch_flag(self):
        if self._closing:
            return
        self._switch_in_progress = False
        self._set_controls_enabled(True)
        try:
            if not self.t.isActive():
                self.t.start()
        except Exception:
            pass

    def on_playlist_double_click(self, item: QListWidgetItem):
        row = self.playlist_widget.row(item)
        self.playlist_widget.setCurrentRow(row)
        self.play_index(row)

    def next_media(self):
        self.logger.info(f"NEXT: cur={self.playlist_index} -> {self.playlist_index+1} len={len(self.playlist_urls)}")
        if not self.playlist_urls:
            return
        nxt = self.playlist_index + 1
        if nxt >= len(self.playlist_urls):
            if self._repeat_enabled:
                nxt = 0
            else:
                return
        self.play_index(nxt)

    def prev_media(self):
        if not self.playlist_urls:
            return
        prv = self.playlist_index - 1
        if prv < 0:
            prv = 0
        self.play_index(prv)

    def on_play_pause(self):
        self.engine.toggle_pause()
        st = self.engine.get_state()
        if st.is_playing:
            self.btn_play.setText("PAUSE")
            self._start_watchdog()
            self.video_window.show()
        else:
            self.btn_play.setText("PLAY")
            self._stop_watchdog()
            self.allow_sleep()

    def on_stop(self):
        self.engine.stop()
        self._stop_watchdog()
        self.allow_sleep()

    def _set_controls_enabled(self, enabled: bool):
        for w in (self.btn_prev, self.btn_next, self.btn_play, self.btn_stop,
                  self.btn_repeat, self.btn_skip, self.btn_shot, self.btn_playlist,
                  self.prog, self.vol, self.url):
            w.setEnabled(enabled)

    # -------------------------
    # repeat
    # -------------------------
    def toggle_repeat(self):
        self._repeat_enabled = not self._repeat_enabled
        if self._repeat_enabled:
            self.btn_repeat.setObjectName("ToggleOn")
        else:
            self.btn_repeat.setObjectName("")

        # пересчитать стиль для кнопки (иначе Qt не всегда обновляет)
        self.btn_repeat.style().unpolish(self.btn_repeat)
        self.btn_repeat.style().polish(self.btn_repeat)
        self.btn_repeat.update()

    # -------------------------
    # UI update
    # -------------------------
    def update_playlist_highlight(self):
        dark = bool(self._night)

        for i in range(self.playlist_widget.count()):
            item = self.playlist_widget.item(i)
            if i == self.playlist_index:
                item.setBackground(QColor("#3a3a3a") if dark else Qt.lightGray)
            else:
                item.setBackground(QColor("#222222") if dark else Qt.white)

    def _tick(self):
        if not self.isVisible():
            return

        st = self.engine.get_state()

        if hasattr(self.engine, "get_video_size"):
            sz = self.engine.get_video_size()
            if sz:
                w, h = sz
                # ограничим максимумом, чтобы не улетало на 4K
                w = min(w, 1920)
                h = min(h, 1080)
                self.video_window.resize(w, h)

        # volume reflect
        self.vol.blockSignals(True)
        self.vol.setValue(st.volume)
        self.vol.blockSignals(False)

        self.lbl_time.setText(f"{fmt_ms(st.time_ms)} / {fmt_ms(st.length_ms)}")

        if not self._dragging and st.length_ms > 0:
            ratio = st.time_ms / st.length_ms
            self.prog.setValue(int(ratio * 1000))

    def _on_seek_press(self):
        self._dragging = True

    def _on_seek_move(self, val: int):
        pass

    def _on_seek_release(self):
        val = self.prog.value()
        self._dragging = False

        if not self.engine.is_seekable():
            # поток не поддерживает seek (live HLS)
            return
        ok = self.engine.seek_ratio(val / 1000.0)

        self._mark_seeking(3000 if not ok else 2000)
        self._after_seek_reset_watchdog()
        self._pause_watchdog_temporarily(3000 if not ok else 1500)

    # -------------------------
    # EOF / errors
    # -------------------------
    def on_eof(self):
        QTimer.singleShot(0, self._on_eof_gui)

    def _on_eof_gui(self):
        if self._switching_track:
            return
        self._switching_track = True
        # EOF может прилететь от предыдущего трека после loadfile/stop (гонка).
        # Если EOF пришёл слишком быстро после смены трека — игнорируем.
        if time.time() - getattr(self, "_last_switch_ts", 0.0) < 0.7:
            self.logger.warning(
                f"Ignoring stale EOF right after switch: dt={time.time() - self._last_switch_ts:.3f}s "
                f"cur_idx={self.playlist_index} last_req={self._last_switch_index}"
            )
            self._switching_track = False
            return

        reason = getattr(self.engine, "last_end_reason", None)
        if reason is None:
            self.logger.warning("EOF reason is None -> treat as stale/ignore")
            self._switching_track = False
            return
        self.logger.info(f"EOF event: reason={reason} idx={self.playlist_index}")
        st = self.engine.get_state()
        played_ms = int(st.time_ms or 0)

        # ранний error: один раз пробуем перезагрузить текущий вместо next
        if reason == "error" and played_ms < 5000 and self.playlist_urls:
            idx = self.playlist_index
            cnt = self._early_error_retry.get(idx, 0)
            if cnt < 1:
                self._early_error_retry[idx] = cnt + 1
                self.logger.warning(f"Early end-file error on idx={idx}, played_ms={played_ms}: retry current")
                self._force_reload_current(resume_ms=0)  # без seek
                # отпускаем переключатель чуть раньше
                QTimer.singleShot(400, lambda: setattr(self, "_switching_track", False))
                return

        self.logger.info("EOF received, moving to next media")
        QTimer.singleShot(200, self._next_media_safe)

    def _next_media_safe(self):
        try:
            self.next_media()
        finally:
            # отпускаем через короткое время, чтобы mpv успел перейти
            QTimer.singleShot(400, lambda: setattr(self, "_switching_track", False))

    def on_error(self, msg: str):
        # пока просто print + messagebox (позже добавим fallback VLC)
        self.logger.error(msg)
        # не спамим messagebox на каждый чих — только по желанию
        # QMessageBox.warning(self, "Player error", msg)

    # -------------------------
    # Skip credits (почти 1:1 с VLC)
    # -------------------------
    def handle_skip_credits(self):
        self.perform_skip_credits()

    def get_episode_skips(self, episode_number: int):
        skip_opening, skip_ending = None, None
        if self.skip_data_cache:
            entries = self.skip_data_cache.get("episode_skips")
            if not entries:
                entries = [self.skip_data_cache]
            for skip_entry in entries:
                try:
                    epn = int(skip_entry.get("episode_number"))
                except Exception:
                    continue

                if epn == int(episode_number):
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

    def get_playing_episode_number(self) -> Optional[int]:
        # надежнее: берём текущий url и парсим как в extract_from_link
        if not self.playlist_urls:
            return None
        url = self.playlist_urls[self.playlist_index]
        parsed = self.extract_from_link(url)
        if parsed:
            ep, _q = parsed
            return int(ep)
        # fallback:
        m = re.search(r"/\d+/(\d+)/", url)
        if m:
            return int(m.group(1))
        return None

    def perform_skip_credits(self):
        def _norm_pair(val) -> Optional[Tuple[float, float]]:
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
                return

            self.get_episode_skips(episode_number)
            if (self.skip_opening is None and self.skip_ending is None) and self.playlist_urls:
                # fallback: плейлист обычно в порядке 1..N
                self.get_episode_skips(self.playlist_index + 1)
            st = self.engine.get_state()
            if not self.engine.is_seekable():
                return
            current_time = (st.time_ms or 0) / 1000.0
            total_length = max(((st.length_ms or 0) / 1000.0), 0.0)

            opening = _norm_pair(self.skip_opening)
            ending = _norm_pair(self.skip_ending)

            if opening:
                start_o, end_o = opening
                if current_time + EPS < end_o:
                    jump_to = min(end_o, max(total_length - TAIL_GUARD, 0.0))
                    ok = self.engine.seek_ms(int(jump_to * 1000))
                    self._mark_seeking(3500 if not ok else 2500)
                    self._after_seek_reset_watchdog()
                    self._pause_watchdog_temporarily(3500 if not ok else 1500)
                    return

            if ending:
                start_e, end_e = ending
                if end_e > current_time + EPS >= start_e:
                    jump_to = min(end_e, max(total_length - TAIL_GUARD, 0.0))
                    ok = self.engine.seek_ms(int(jump_to * 1000))
                    self._mark_seeking(3500 if not ok else 2500)
                    self._after_seek_reset_watchdog()
                    self._pause_watchdog_temporarily(3500 if not ok else 1500)
                    return

        except Exception:
            # не валим приложение
            return

    # -------------------------
    # Watchdog (детект "залипания" и перезагрузка текущего)
    # -------------------------
    def _start_watchdog(self):
        self.prevent_sleep()
        if not self._wd_timer.isActive():
            self._wd_last_time_ms = None
            self._wd_stuck_count = 0
            self._wd_timer.start()

    def _stop_watchdog(self):
        if self._wd_timer.isActive():
            self._wd_timer.stop()

    def _resume_watchdog_check(self):
        if time.time() < getattr(self, "_seeking_until", 0.0):
            return

        st = self.engine.get_state()
        if not st.is_playing:
            return
        cur = int(st.time_ms or 0)
        # если длины нет — не трогаем
        if int(st.length_ms or 0) <= 0:
            return

        if self._wd_last_time_ms is None:
            self._wd_last_time_ms = cur
            return

        if getattr(self.engine, "is_buffering_or_seeking", None):
            if self.engine.is_buffering_or_seeking():
                return

        # если время не двигается, считаем "залип"
        if abs(cur - self._wd_last_time_ms) < 50:
            self._wd_stuck_count += 1
        else:
            self._wd_stuck_count = 0
            self._wd_last_time_ms = cur
            return

        # 2-3 тика подряд без движения — пробуем перезагрузить текущий
        if self._wd_stuck_count >= 3:
            self._wd_stuck_count = 0
            self._force_reload_current(resume_ms=cur)

    def _force_reload_current(self, resume_ms: int):
        if not self.playlist_urls:
            return

        self._pause_watchdog_temporarily(2000)

        url = self.playlist_urls[self.playlist_index]
        self.engine.load(url)
        self.engine.play()

        QTimer.singleShot(900, lambda: (self.engine.seek_ms(resume_ms), self._after_seek_reset_watchdog()))

    # -------------------------
    # Screenshot (как в VLC по смыслу)
    # -------------------------
    def take_screenshot(self):
        try:
            out_dir = Path.cwd() / "screenshots"
            out_dir.mkdir(parents=True, exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H-%M-%S")
            tid = self.title_id if self.title_id is not None else "noid"
            path = out_dir / f"screenshot_{tid}_{ts}.png"
            # mpv_engine добавили screenshot()
            if hasattr(self.engine, "screenshot"):
                self.engine.screenshot(str(path))
        except Exception:
            pass

    # -------------------------
    # Prevent sleep (1:1 с VLC)
    # -------------------------
    def prevent_sleep(self):
        if os.name != "nt":
            return
        try:
            ctypes.windll.kernel32.SetThreadExecutionState(
                ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED
            )
        except Exception:
            pass

    def allow_sleep(self):
        if os.name != "nt":
            return
        try:
            ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS)
        except Exception:
            pass

    def closeEvent(self, event):
        self._closing = True
        try:
            self.allow_sleep()
            try:
                self.t.stop()
            except Exception:
                pass
            try:
                self._wd_timer.stop()
            except Exception:
                pass

            try:
                if getattr(self, "video_window", None):
                    # Чтобы callback не сработал и не было рекурсии:
                    self.video_window._on_user_close = None
                    self.video_window.close()
            except Exception:
                pass

            self.engine.shutdown()
        finally:
            super().closeEvent(event)

    def apply_template(self, template: str | None):
        night = (template or "").lower() in ("night", "dark", "no_background_night")

        if night:
            bg = "#151515"
            fg = "#eaeaea"
            panel = "#1f1f1f"
            btn_bg = "#2a2a2a"
            btn_bg_hover = "#343434"
            btn_bg_pressed = "#3c3c3c"
            border = "#3a3a3a"
            groove = "#3a3a3a"
            fill = "#cfcfcf"
            handle = "#f1f1f1"
        else:
            bg = "#f2f2f2"
            fg = "#111111"
            panel = "#e6e6e6"
            btn_bg = "#d7d7d7"
            btn_bg_hover = "#cfcfcf"
            btn_bg_pressed = "#c2c2c2"
            border = "#b8b8b8"
            groove = "#bdbdbd"
            fill = "#6b6b6b"
            handle = "#ffffff"

        qss = f"""
        QListWidget {{
            background: {panel};
            color: {fg};
            border: 1px solid {border};
            border-radius: 6px;
            padding: 2px;
            outline: 0;
        }}
        QListWidget::item {{
            background: transparent;
            padding: 6px 8px;
            border-radius: 4px;
        }}
        QListWidget::item:selected {{
            background: {btn_bg_pressed};
        }}
        QWidget {{
            background: {bg};
            color: {fg};
            font-size: 11pt;
        }}
        QFrame#RootPanel {{
            background: {panel};
            border: 1px solid {border};
            border-radius: 6px;
        }}
        QLineEdit {{
            background: {panel};
            color: {fg};
            border: 1px solid {border};
            border-radius: 6px;
            padding: 4px 8px;
            selection-background-color: {fill};
        }}
        QPushButton {{
            background: {btn_bg};
            border: 1px solid {border};
            border-radius: 6px;
            padding: 4px 10px;
            font-weight: 600;
        }}
        QPushButton:hover {{
            background: {btn_bg_hover};
        }}
        QPushButton:pressed {{
            background: {btn_bg_pressed};
        }}
        /* Активное состояние (например Repeat ON) */
        QPushButton#ToggleOn {{
            border: 2px solid {fill};
        }}
        QLabel {{
            background: transparent;
            font-weight: 600;
        }}
        /* Progress / Volume sliders - VLC-like */
        QSlider::groove:horizontal {{
            height: 25px;
            background: {groove};
        }}
        QSlider::sub-page:horizontal {{
            background: {fill};
        }}
        QSlider::add-page:horizontal {{
            background: {groove};
        }}
        QSlider::handle:horizontal {{
            width: 25px;
            margin: -1px 0;          /* делает "толстый" хэндл */
            background: {handle};
            border: 1px solid {border};
        }}
        QToolTip {{
            background: {panel};
            color: {fg};
            border: 1px solid {border};
        }}
        """
        self._night = night
        self.setStyleSheet(qss)

    def _after_seek_reset_watchdog(self):
        self._wd_last_time_ms = None
        self._wd_stuck_count = 0

    def _pause_watchdog_temporarily(self, ms=1500):
        if self._wd_timer.isActive():
            self._wd_timer.stop()
            QTimer.singleShot(ms, self._start_watchdog)

    def _mark_seeking(self, ms=2000):
        self._seeking_until = time.time() + (ms / 1000.0)

    def toggle_playlist_visibility(self):
        if self.playlist_widget.isVisible():
            self.playlist_widget.hide()
            self.resize(850, 100)
        else:
            self.playlist_widget.show()
            self.resize(850, 200)

    def _on_video_window_user_close(self):
        if self._closing:
            return
        QTimer.singleShot(10, self.close)
