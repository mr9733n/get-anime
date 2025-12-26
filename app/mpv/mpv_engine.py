# player/mpv_engine.py
from __future__ import annotations

import os
import sys
import threading
import time
import logging
import traceback
from pathlib import Path
from typing import Callable, Optional
from urllib.parse import urlparse

from app.mpv.base_engine import PlaybackState
from utils.library_loader import verify_library, load_library

LIB_HASH = "fdb7a0b1f700b9eb9056e9ddc0a890c33f55fbb7ccbd9ff1d554ea088762ee0d"
LIB_NAME = "libmpv-2.dll"

lib_dir = str(Path(__file__).resolve().parents[2] / "libs")
try:
    expected_hash = LIB_HASH
    lib_file_path = load_library(lib_dir, LIB_NAME)
    status = verify_library(lib_file_path, expected_hash)
    if not status:
        sys.exit(1)
except Exception as e:
    logging.error(f"Failed to initialize library: {e}", exc_info=True)

os.environ["PATH"] = str(lib_dir) + os.pathsep + os.environ.get("PATH", "")
import mpv  # python-mpv

class MpvEngine:
    def __init__(self, *, proxy: str | None = None, loglevel: str = "warn", log_file: str | None = None):
        self.logger = logging.getLogger(__name__)
        self._lock = threading.RLock()
        self._alive = True
        self.on_eof: Optional[Callable[[], None]] = None
        self.on_error: Optional[Callable[[str], None]] = None
        self._log_file = log_file

        # КРИТИЧНО: создаём MPV с защитными настройками
        try:
            # Базовые опции для стабильности
            init_options = {
                'log_handler': self._on_mpv_log,
                'loglevel': loglevel,
                'ytdl': False,
                # ЗАЩИТА ОТ КРАШЕЙ GPU:
                'vo': 'gpu',  # Можно попробовать: 'direct3d', 'x11', 'sdl'
                'hwdec': 'no',  # ОТКЛЮЧАЕМ hardware decode - часто источник крашей
                'gpu-context': 'auto',
                # ЗАЩИТА ОТ КРАШЕЙ АУДИО:
                'ao': 'wasapi',  # Windows audio
                'audio-fallback-to-null': 'yes',
                # ЗАЩИТА ОТ ПРОБЛЕМ С КЭШЕМ:
                'cache': 'yes',
                'demuxer-max-bytes': '150M',  # Уменьшил с 100M
                'demuxer-readahead-secs': '20',  # Уменьшил с 20
                # ЗАЩИТА ОТ THREADING ISSUES:
                'input-terminal': 'no',
                'terminal': 'no',
            }

            self.logger.info(f"Creating MPV with options: {init_options}")
            self._player = mpv.MPV(**init_options)
            self.logger.info("MPV instance created successfully")

        except Exception as e:
            self.logger.error(f"Failed to create MPV instance: {e}", exc_info=True)
            self.logger.error(f"Stack trace: {traceback.format_exc()}")
            raise
        self._player["http-header-fields"] = "Connection: close"
        self._player["user-agent"] = "Mozilla/5.0"
        self._player["network-timeout"] = "10"
        self._player["demuxer-hysteresis-secs"] = "10"

        self._alive = True

        self._last_endfile_ts = 0.0
        self._wid_set = False
        self._current_url: str | None = None
        self.last_end_reason = None

        # ЗАЩИТА: счётчик крашей для fallback
        self._crash_count = 0
        self._last_crash_time = 0.0

        # Event callback с защитой от exceptions
        @self._player.event_callback("end-file")
        def _safe_end_file(event):
            try:
                self._handle_end_file(event)
            except Exception as e:
                self.logger.error(f"Exception in end-file handler: {e}", exc_info=True)

    def _handle_end_file(self, event):
        """Обработчик end-file с логированием"""
        reason = getattr(event, "reason", None)
        self.last_end_reason = reason

        self.logger.info(f"end-file event: reason={reason}")

        if reason in ("stop", "quit"):
            self.logger.debug("end-file: stop/quit - ignoring")
            return

        if reason == "error":
            self.logger.error("end-file: ERROR occurred during playback")
            if self.on_error:
                try:
                    self.on_error("mpv: end-file reason=error")
                except Exception as e:
                    self.logger.error(f"Exception in on_error callback: {e}")
            if self.on_eof:
                try:
                    self.on_eof()
                except Exception as e:
                    self.logger.error(f"Exception in on_eof callback: {e}")
            return

        if reason == "eof":
            self.logger.info("end-file: EOF - media finished")
            if self.on_eof:
                try:
                    self.on_eof()
                except Exception as e:
                    self.logger.error(f"Exception in on_eof callback: {e}")
            return

        self.logger.debug(f"end-file: reason={reason} - ignoring")

    def _on_mpv_log(self, level, prefix, text):
        """MPV log handler с детальным выводом"""
        # Всегда пишем в основной лог
        text = (text or "").rstrip("\r\n")
        log_line = f"[MPV:{level}] {prefix}: {text}"

        if level == 'fatal' or level == 'error':
            self.logger.error(log_line)
        elif level == 'warn':
            self.logger.warning(log_line)
        elif level == 'info':
            self.logger.info(log_line)
        else:
            self.logger.debug(log_line)

        # В файл (если указан)
        if self._log_file:
            try:
                Path(self._log_file).parent.mkdir(parents=True, exist_ok=True)
                with open(self._log_file, "a", encoding="utf-8", errors="ignore") as f:
                    f.write(log_line + "\n")
            except Exception as e:
                self.logger.debug(f"Failed to write to log file: {e}")

    def set_video_widget(self, win_id: int) -> None:
        """КРИТИЧНО: установка WID с проверками"""
        if self._wid_set:
            self.logger.warning("WID already set, ignoring")
            return

        try:
            with self._lock:
                if not self._alive:
                    self.logger.error("Cannot set WID - engine not alive")
                    return

                self.logger.info(f"Setting WID: {win_id} (type: {type(win_id)})")

                # ПРОВЕРКА: валидный ли WID
                if win_id <= 0:
                    raise ValueError(f"Invalid WID: {win_id}")

                # Устанавливаем с логированием
                self._player.wid = int(win_id)
                self._wid_set = True

                # ПРОВЕРКА: действительно ли установился
                actual_wid = self._player.wid
                self.logger.info(f"WID set successfully. Actual value: {actual_wid}")

                if actual_wid != win_id:
                    self.logger.error(f"WID mismatch! Set {win_id}, got {actual_wid}")

        except Exception as e:
            self.logger.error(f"CRITICAL: Failed to set video widget: {e}", exc_info=True)
            self.logger.error(f"Stack trace: {traceback.format_exc()}")
            raise

    def shutdown(self) -> None:
        """Безопасное завершение"""
        self.logger.info("Shutting down MPV engine")
        with self._lock:
            self._alive = False
            try:
                try:
                    self.logger.debug("Sending stop command")
                    self._player.command("stop")
                except Exception as e:
                    self.logger.debug(f"Stop command failed: {e}")

                self.logger.debug("Terminating MPV")
                self._player.terminate()
                self.logger.info("MPV terminated successfully")
            except Exception as e:
                self.logger.error(f"Error during shutdown: {e}", exc_info=True)

    def _safe(self):
        return getattr(self, "_alive", True)

    def load(self, url: str) -> None:
        """Загрузка с детальными проверками"""
        if not self._safe():
            self.logger.warning("load() called but engine not alive")
            return

        with self._lock:
            if not self._safe():
                return

            # КРИТИЧНО: WID проверка
            if not self._wid_set:
                err_msg = "CRITICAL: Cannot load - WID not set!"
                self.logger.error(err_msg)
                if self.on_error:
                    self.on_error(err_msg)
                return

            try:
                self.logger.info(f"=" * 60)
                self.logger.info(f"Loading URL: {url}")
                self.logger.info(f"Current WID: {self._player.wid}")
                self.logger.info(f"=" * 60)

                self._current_url = url

                # ЗАЩИТА: проверяем что player ещё жив
                try:
                    _ = self._player.pause  # Тестовое обращение
                except Exception as e:
                    self.logger.error(f"MPV player appears dead: {e}")
                    raise

                # Загружаем
                self.logger.info("Executing loadfile command...")
                self._player.command("loadfile", url, "replace")
                self.logger.info("loadfile command sent successfully")

                # ДИАГНОСТИКА: проверяем что загрузка началась
                import time
                time.sleep(0.1)

                try:
                    idle = self._player.core_idle
                    self.logger.info(f"After load: core_idle={idle}")
                except Exception as e:
                    self.logger.warning(f"Cannot check core_idle: {e}")

            except Exception as e:
                err_msg = f"LOAD FAILED: {e}"
                self.logger.error(err_msg, exc_info=True)
                self.logger.error(f"Stack trace: {traceback.format_exc()}")

                # Увеличиваем счётчик крашей
                self._crash_count += 1
                self._last_crash_time = time.time()

                if self.on_error:
                    self.on_error(err_msg)
                raise

    def play(self) -> None:
        """Запуск воспроизведения с логированием"""
        if not self._safe():
            return
        with self._lock:
            if not self._safe():
                return
            try:
                self.logger.info("Setting pause=False (starting playback)")
                self._player.pause = False
                self.logger.info("Playback started")
            except Exception as e:
                self.logger.error(f"play() failed: {e}", exc_info=True)
                raise

    def pause(self) -> None:
        if not self._safe():
            return
        with self._lock:
            if not self._safe():
                return
            try:
                self.logger.info("Pausing playback")
                self._player.pause = True
            except Exception as e:
                self.logger.error(f"pause() failed: {e}")

    def toggle_pause(self) -> None:
        if not self._safe():
            return
        with self._lock:
            if not self._safe():
                return
            try:
                current = bool(self._player.pause)
                self._player.pause = not current
                self.logger.info(f"Toggled pause: {current} -> {not current}")
            except Exception as e:
                self.logger.error(f"toggle_pause() failed: {e}")

    def stop(self) -> None:
        if not self._safe():
            return
        with self._lock:
            if not self._safe():
                return
            try:
                self.logger.info("Stopping playback")
                self._player.command("stop")
            except Exception as e:
                self.logger.error(f"stop() failed: {e}")

    def seek_ratio(self, ratio: float) -> bool:
        st = self.get_state()
        if st.length_ms <= 0:
            return False
        target = int(st.length_ms * max(0.0, min(1.0, ratio)))
        return self.seek_ms(target)

    def seek_ms(self, ms: int) -> bool:
        if not getattr(self, "_alive", True):
            return False

        if not self.is_seekable():
            return False

        sec = max(0.0, ms / 1000.0)
        try:
            self._player.command("seek", sec, "absolute")
            return True
        except Exception as e:
            self.logger.error(f"seek_ms({ms}) failed: {e}")
            return False

    def set_volume(self, volume: int) -> None:
        if not self._safe():
            return
        with self._lock:
            if not self._safe():
                return
            try:
                vol = max(0, min(100, int(volume)))
                self._player.volume = vol
                self.logger.debug(f"Volume set to {vol}")
            except Exception as e:
                self.logger.error(f"set_volume({volume}) failed: {e}")

    def screenshot(self, path: str) -> None:
        if not self._safe():
            return
        with self._lock:
            if not self._safe():
                return
            try:
                self.logger.info(f"Taking screenshot: {path}")
                self._player.command("screenshot-to-file", path, "video")
            except Exception as e:
                self.logger.error(f"screenshot() failed: {e}")

    def get_state(self) -> PlaybackState:
        if not self._safe():
            return PlaybackState(False, 0, 0, 0, self._current_url)

        with self._lock:
            if not self._safe():
                return PlaybackState(False, 0, 0, 0, self._current_url)
            try:
                time_pos = self._player.time_pos
                duration = self._player.duration
                volume = self._player.volume
                paused = bool(self._player.pause)
            except mpv.ShutdownError:
                self._alive = False
                return PlaybackState(False, 0, 0, 0, self._current_url)
            except Exception as e:
                self.logger.debug(f"get_state() property access failed: {e}")
                return PlaybackState(False, 0, 0, 0, self._current_url)

        def _sec_to_ms(x) -> int:
            try:
                return int(float(x) * 1000)
            except Exception:
                return 0

        return PlaybackState(
            is_playing=not paused,
            time_ms=_sec_to_ms(time_pos),
            length_ms=_sec_to_ms(duration),
            volume=int(volume or 0),
            mrl=self._current_url,
        )

    def is_seekable(self) -> bool:
        if not self._safe():
            return False
        with self._lock:
            if not self._safe():
                return False
            try:
                return bool(self._player.seekable)
            except Exception:
                return False

    def seek_seconds_relative(self, sec: float) -> None:
        try:
            self._player.command("seek", float(sec), "relative")
        except Exception as e:
            self.logger.error(f"seek_seconds_relative({sec}) failed: {e}")

    def is_buffering_or_seeking(self) -> bool:
        try:
            return bool(self._player.core_idle) is False and (
                        bool(self._player.seeking) or bool(self._player.paused_for_cache))
        except Exception:
            return False

    def get_video_size(self) -> tuple[int, int] | None:
        try:
            w = int(self._player.dwidth or 0)
            h = int(self._player.dheight or 0)
            if w > 0 and h > 0:
                return w, h
        except Exception:
            pass
        return None

    def get_diagnostics(self) -> dict:
        """Получить диагностическую информацию"""
        info = {
            "alive": self._alive,
            "wid_set": self._wid_set,
            "current_url": self._current_url,
            "crash_count": self._crash_count,
        }

        try:
            info["mpv_version"] = mpv._mpv_client_api_version()
        except:
            info["mpv_version"] = "unknown"

        try:
            info["wid_value"] = self._player.wid if self._wid_set else None
        except:
            info["wid_value"] = "error"

        return info