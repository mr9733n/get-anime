# player/mpv_engine.py
from __future__ import annotations

import os
import sys
import threading
import time
import logging
from pathlib import Path
from typing import Callable, Optional
from urllib.parse import urlparse

from app.mpv.base_engine import PlaybackState
from utils.library_loader import verify_library, load_library

LIB_HASH = "fdb7a0b1f700b9eb9056e9ddc0a890c33f55fbb7ccbd9ff1d554ea088762ee0d"
LIB_NAME = "libmpv-2.dll"

lib_dir = os.path.join('libs')
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


def _normalize_proxy(proxy: str | None) -> str | None:
    if not proxy:
        return None

    p = proxy.strip()
    if not p:
        return None

    orig = p

    if "://" in p:
        u = urlparse(p)
        # urlparse("http://1.2.3.4:3128") -> netloc="1.2.3.4:3128"
        if u.netloc:
            p = u.netloc
        else:
            # на случай кривого ввода типа "http://1.2.3.4:3128/"
            p = p.split("://", 1)[1]

    # убрать возможный хвостовой слеш
    p = p.rstrip("/")

    if not p:
        return None

    if p != orig:
        logging.info(f"proxy normalised: '{orig}' -> '{p}'")
    return p


class MpvEngine:
    def __init__(self, *, proxy: str | None = None, loglevel: str = "warn", log_file: str | None = None):
        self.logger = logging.getLogger(__name__)
        self._lock = threading.RLock()
        self._alive = True
        self.on_eof: Optional[Callable[[], None]] = None
        self.on_error: Optional[Callable[[str], None]] = None

        self._log_file = log_file

        # КРИТИЧНО: инициализируем без wid, установим позже
        try:
            self._player = mpv.MPV(
                log_handler=self._on_mpv_log,
                loglevel=loglevel,
                ytdl=False,
                vo="gpu-next",  # попробовать
            )

        except Exception as e:
            self.logger.error(f"Failed to create MPV instance: {e}", exc_info=True)
            raise

        self._player["cache"] = "yes"
        self._player["demuxer-max-bytes"] = "100M"
        self._player["demuxer-readahead-secs"] = "20"

        self._alive = True

        # Прокси (опция работает если сборка mpv/ffmpeg поддерживает)
        proxy_norm = _normalize_proxy(proxy)
        if proxy_norm:
            try:
                self._player["http-proxy"] = proxy_norm
            except Exception as e:
                err_msg = f"mpv: не удалось применить proxy '{proxy_norm}': {e}"
                self.logger.warning(err_msg)
                if self.on_error:
                    self.on_error(err_msg)

        self._last_endfile_ts = 0.0
        self._wid_set = False
        self._current_url: str | None = None
        self.last_end_reason = None

        @self._player.event_callback("end-file")
        def _(event):
            reason = getattr(event, "reason", None)
            self.last_end_reason = reason

            if reason in ("stop", "quit"):
                return

            if reason == "error":
                if self.on_error:
                    self.on_error("mpv: end-file reason=error")
                if self.on_eof:
                    self.on_eof()
                return

            if reason == "eof":
                if self.on_eof:
                    self.on_eof()
                return

            return

    def _on_mpv_log(self, level, prefix, text):
        if not self._log_file:
            return
        try:
            Path(self._log_file).parent.mkdir(parents=True, exist_ok=True)
            with open(self._log_file, "a", encoding="utf-8", errors="ignore") as f:
                f.write(f"[{level}] {prefix}: {text}")
        except Exception:
            pass

    def set_video_widget(self, win_id: int) -> None:
        """ВАЖНО: должен быть вызван ДО первого load()"""
        if self._wid_set:
            self.logger.debug("WID already set, ignoring")
            return

        try:
            with self._lock:
                if not self._alive:
                    self.logger.warning("Cannot set WID - engine not alive")
                    return

                self._player.wid = int(win_id)
                self._wid_set = True
                self.logger.info(f"Video widget WID set to {win_id}")
        except Exception as e:
            self.logger.error(f"Failed to set video widget: {e}", exc_info=True)
            raise

    def shutdown(self) -> None:
        with self._lock:
            self._alive = False
            try:
                try:
                    self._player.command("stop")
                except Exception:
                    pass
                self._player.terminate()
            except Exception as e:
                self.logger.error(f"Error during shutdown: {e}")

    def _safe(self):
        return getattr(self, "_alive", True)

    def load(self, url: str) -> None:
        """Загружает URL. ТРЕБУЕТ предварительного вызова set_video_widget()"""
        if not self._safe():
            self.logger.warning("load() called but engine not alive")
            return

        with self._lock:
            if not self._safe():
                return

            # КРИТИЧНО: проверяем что WID установлен
            if not self._wid_set:
                err_msg = "Cannot load media: video widget not set. Call set_video_widget() first."
                self.logger.error(err_msg)
                if self.on_error:
                    self.on_error(err_msg)
                return

            try:
                self._current_url = url
                self._player.command("loadfile", url, "replace")
                self.logger.info(f"Loaded: {url}")
            except Exception as e:
                err_msg = f"Failed to load '{url}': {e}"
                self.logger.error(err_msg, exc_info=True)
                if self.on_error:
                    self.on_error(err_msg)

    def play(self) -> None:
        if not self._safe():
            return
        with self._lock:
            if not self._safe():
                return
            try:
                self._player.pause = False
            except Exception as e:
                self.logger.error(f"play() failed: {e}")

    def pause(self) -> None:
        if not self._safe():
            return
        with self._lock:
            if not self._safe():
                return
            try:
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
                self._player.pause = not bool(self._player.pause)
            except Exception as e:
                self.logger.error(f"toggle_pause() failed: {e}")

    def stop(self) -> None:
        if not self._safe():
            return
        with self._lock:
            if not self._safe():
                return
            try:
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
        sec = max(0.0, ms / 1000.0)
        try:
            self._player.command("seek", sec, "absolute+exact")
            return True
        except Exception:
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
                self._player.volume = max(0, min(100, int(volume)))
            except Exception as e:
                self.logger.error(f"set_volume({volume}) failed: {e}")

    def screenshot(self, path: str) -> None:
        if not self._safe():
            return
        with self._lock:
            if not self._safe():
                return
            try:
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