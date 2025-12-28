# app/qt/app_players.py
from __future__ import annotations
"""Player/playlist related methods extracted from app.py.

These functions are intended to be attached to AnimePlayerAppVer3 as methods:
    AnimePlayerAppVer3.play_link = play_link
etc.

Keep bodies 1:1 to minimize refactor risk.
"""

import os
import sys
import json
import subprocess
from pathlib import Path
from datetime import datetime

from app.vlc.vlc_player import VLCPlayer
from utils.playlists.playlist_key import calc_bundle_key
from utils.security.library_loader import verify_library
from app.qt.app_constants import VLC_PLAYER_HASH, MPV_PLAYER_HASH, MINI_BROWSER_HASH


def open_mpv_player(self, playlist_path, title_id, skip_data=None):
    """
    DEV-версия: открываем окно mpv прямо в текущем процессе (без бинарника).
    """
    try:
        from app.mpv.mpv_engine import MpvEngine
        from app.mpv.player_window import PlayerWindow

        mpv_kwargs = {}
        # прокси
        if self.proxy_enabled == "true":
            mpv_kwargs["proxy"] = self.proxy_url

        # логирование (опционально)
        log_file = None
        if self.mpv_log_enabled == "true":
            # можно положить рядом с temp/logs
            log_file = str(Path("logs") / "mpv.log")

        self.logger.info(f"DEV mpv player launch : {self.proxy_url} {self.mpv_log_enabled}")

        engine = MpvEngine(
            proxy=None,
            loglevel=("info" if str(self.mpv_verbose).lower() in ("info", "debug") else "warn"),
            log_file=log_file
        )

        w = PlayerWindow(
            engine,
            playlist=playlist_path,
            title_id=title_id,
            skip_data=skip_data,
            proxy=mpv_kwargs.get("proxy"),
            resolver=self.url_resolver,
            autoplay=True,
            template=self.current_template,  # важно!
        )
        w.show()

        # держим ссылку, чтобы окно не убилось GC
        self.mpv_window = w

    except Exception as e:
        self.logger.error(f"DEV mpv player launch failed: {e}", exc_info=True)
        raise

def open_standalone_mpv_player(self, playlist_path, title_id, skip_data=None) -> bool:
    """
    PROD-версия: запускаем mpv-плеер как отдельный процесс.
    Возвращает True если удалось запустить, иначе False.
    """
    try:
        if getattr(sys, 'frozen', False):
            mpv_executable = os.path.join(os.path.dirname(sys.executable), self.mpv_player_executable_name)

            if not os.path.exists(mpv_executable):
                self.logger.error(f"mpv player executable not found: {mpv_executable}")
                return False

            cmd = [
                mpv_executable,
                "--playlist", str(playlist_path),
                "--title_id", str(title_id),
                "--template", str(self.current_template),
            ]

            if skip_data:
                cmd.extend(["--skip_data", skip_data])

            if self.prod_key is not None:
                cmd.extend(["--prod_key", str(self.prod_key)])

            # mpv лог/verbose (опционально)
            if self.mpv_log_enabled == "true":
                cmd.extend(["--log", str(Path("logs") / "mpv.log")])
            if str(self.mpv_verbose).lower() in ("info", "debug"):
                cmd.extend(["--verbose"])

            subprocess.Popen(cmd, close_fds=True)
            self.logger.info(f"Launched standalone MPV player for title_id: {title_id}")
            return True

        # DEV
        self.open_mpv_player(playlist_path, title_id, skip_data)
        return True

    except Exception as e:
        self.logger.error(f"open_standalone_mpv_player failed: {e}", exc_info=True)
        return False

def open_vlc_player(self, playlist_path, title_id, skip_data=None):
    """
    Создаёт и открывает окно VLC‑плеера.
    Параметры `proxy`, `log` и `log_level` передаются только если они включены.
    """
    vlc_kwargs = {"current_template": self.current_template}

    if self.log_enabled == "true":
        vlc_kwargs["log"] = self.log_enabled
        vlc_kwargs["log_level"] = self.verbose

    self.vlc_window = VLCPlayer(**vlc_kwargs)

    final_path = playlist_path
    if self.proxy_enabled == "true" and isinstance(playlist_path, str) and playlist_path.startswith(
            ("http://", "https://")):
        rr = self.url_resolver.resolve(playlist_path)
        if rr and getattr(rr, "final_url", None):
            final_path = rr.final_url

    self.logger.debug(
        f"title_id: {title_id}, playlist_path: {playlist_path}, skip_data: {skip_data}"
    )
    self.vlc_window.load_playlist(final_path, title_id, skip_data)
    self.vlc_window.show()
    self.vlc_window.timer.start()

def open_standalone_vlc_player(self, playlist_path, title_id, skip_data=None):
    """Launch VLC player as a separate process."""
    final_path = playlist_path
    if self.proxy_enabled == "true" and isinstance(playlist_path, str) and playlist_path.startswith(
            ("http://", "https://")):
        rr = self.url_resolver.resolve(playlist_path)
        if rr and getattr(rr, "final_url", None):
            final_path = rr.final_url

    if getattr(sys, 'frozen', False):
        # TODO: add other platforms
        vlc_player_executable_name = self.config_manager.get_vlc_player_executable_name()
        vlc_player_executable = os.path.join(os.path.dirname(sys.executable), vlc_player_executable_name)

        if VLC_PLAYER_HASH:
            status = verify_library(vlc_player_executable, VLC_PLAYER_HASH)

            if not status:
                self.logger.error(f"VLC player executable hash mismatch! Security risk detected.")
                self.show_error_notification("Security Error", "VLC player executable verification failed.")
                sys.exit(1)

        cmd = [vlc_player_executable,
               "--playlist", final_path,
               "--title_id", str(title_id),
               "--template", self.current_template]

        if skip_data:
            cmd.extend(["--skip_data", skip_data])
        if self.prod_key is not None:
            cmd.extend(["--prod_key", str(self.prod_key)])

        if self.log_enabled == "true":
            cmd.extend(["--log", str(self.log_enabled)])
            cmd.extend(["--verbose", str(self.verbose)])

        subprocess.Popen(cmd, close_fds=True)
        self.logger.info(f"Launched standalone VLC player for title_id: {title_id}")
    else:
        # TODO: DEVELOPMENT Version
        self.open_vlc_player(final_path, title_id, skip_data)

def open_web_link(self, link: str, title_id: int | None = None, skip_data=None):
    try:
        if not title_id:
            title_id = self.current_title_id

        host = None
        if title_id:
            host = self.db_manager.get_player_host_by_title_id(title_id)
        if not host:
            host = self.stream_video_url  # fallback

        full = self.playlist_manager.make_full_url(link, host)
        if not full:
            self.logger.error(f"open_web_link: empty url from link={link!r} host={host!r}")
            return

        self.logger.info(f"Opening web link in mini_browser: {full}")
        self.router.open_web_urls([full])

    except Exception as e:
        self.logger.error(f"open_web_link error: {e}", exc_info=True)

def play_link(self, link, title_id=None, skip_data=None):
    """
    Воспроизводит ссылку на эпизод.

    Логика:
    1. Если link уже полный URL (https://...) - используем как есть
    2. Если link это путь (/videos/...) - получаем host из БД и строим URL
    """
    try:
        if link.startswith(("http://", "https://")):
            open_link = link
            self.logger.debug("Using full URL from link")
        else:
            host = self.stream_video_url
            if title_id:
                host = self.db_manager.get_player_host_by_title_id(title_id) if title_id else self.stream_video_url
                self.logger.debug(f"Using host from DB: {host}")

            if not link.startswith('/'):
                link = '/' + link

            open_link = self.playlist_manager.make_full_url(link, host)

        if not open_link:
            self.logger.error("Empty open_link ...")
            return

        # 1) mpv (если включен)
        if getattr(self, "use_mpv_player", "false") == "true":
            ok = self.open_standalone_mpv_player(open_link, str(title_id), skip_data)
            if ok:
                self.logger.info(f"Playing via MPV: {open_link[-50:]}")
                return

            # mpv не смог стартовать -> fallback на VLC
            self.logger.warning("MPV failed to launch, falling back to VLC...")

        # 2) VLC (как было)
        if self.use_libvlc == "true":
            self.open_standalone_vlc_player(open_link, str(title_id), skip_data)
        else:
            # внешний плеер
            subprocess.Popen([self.video_player_path, open_link])

        self.logger.info(f"Playing: {open_link[-50:]}")

    except Exception as e:
        self.logger.error(f"Error playing link: {e}", exc_info=True)

def play_playlist_wrapper(self, file_name=None, title_id=None, skip_data=None):
    """
    Wrapper function to handle playing the playlist.
    Determines the file name and passes it to play_playlist.
    """
    try:
        if not title_id:
            title_id = self.current_title_id

        if not file_name:
            file_name = self.playlist_filename
            if not file_name:
                self.logger.error("No playlist filename available. Please save a playlist first.")
                return

        file_path = os.path.join(self.playlist_manager.playlist_path, file_name)
        if not os.path.exists(file_path):
            self.logger.error(f"Playlist file does not exist: {file_path}")
            return

        # ✅ НОВОЕ: web playlist -> mini browser
        if str(file_name).lower().endswith(".urls"):
            self.logger.info(f"Opening web playlist via mini_browser: {file_path}")
            # напрямую, без open_playlist(), чтобы не было циклов
            self.router.open_web_file(file_path)
            return

        # дальше — твоя старая логика mpv/vlc
        self.logger.debug(f"Playing playlist '{file_name}' for title_id: {title_id}")

        if getattr(self, "use_mpv_player", "false") == "true":
            ok = self.open_standalone_mpv_player(file_path, title_id, skip_data)
            if ok:
                self.logger.debug("Playlist launched via MPV successfully")
                return
            self.logger.warning("MPV failed to launch playlist, falling back to VLC.")

        if self.use_libvlc == "true":
            self.open_standalone_vlc_player(file_path, title_id, skip_data)
        else:
            self.playlist_manager.play_playlist(file_name, self.video_player_path)

        self.logger.debug("Video player launched successfully")
    except Exception as e:
        self.logger.error(f"Error in play_playlist_wrapper: {e}", exc_info=True)

def get_mini_browser_command(self) -> list[str]:
    """
    DEV: запускаем app/qt_browser/mini_browser.py через текущий интерпретатор
    """
    app_dir = os.path.dirname(os.path.dirname(__file__))  # app/
    mini_browser_py = os.path.join(app_dir, "qt_browser", "mini_browser.py")
    return [sys.executable, mini_browser_py]

def ensure_playlist_bundle(self, title_id: int):
    """
    Гарантирует, что для title_id bundle создан, но НЕ пересоздаёт каждый рендер.
    Пересоздаёт только если изменились links или host.
    """
    playlist = (self.playlists or {}).get(title_id)
    if not playlist:
        return None

    links = playlist.get("links") or []
    if not links:
        playlist["streams_file"] = None
        playlist["web_file"] = None
        playlist["streams_count"] = 0
        playlist["web_count"] = 0
        playlist["bundle_key"] = None
        return playlist

    host = self.db_manager.get_player_host_by_title_id(title_id)
    key = calc_bundle_key(title_id, links, host)
    prev_key = playlist.get("bundle_key")

    # если ключ не изменился — bundle уже актуален, ничего не делаем
    if prev_key == key:
        if playlist.get("streams_file") is not None or playlist.get("web_file") is not None:
            return playlist

    sanitized_title = playlist.get("sanitized_title") or str(title_id)

    bundle = self.playlist_manager.save_playlist_bundle(
        [sanitized_title],
        links,
        host
    )

    # сохраняем в playlist кэш + метаданные
    playlist["bundle_key"] = key
    playlist["streams_count"] = bundle.streams_count
    playlist["web_count"] = bundle.web_count

    # если файл реально создан (count > 0) — сохраняем имя, иначе None
    playlist["streams_file"] = bundle.m3u_name if bundle.streams_count > 0 else None
    playlist["web_file"] = bundle.web_name if bundle.web_count > 0 else None

    return playlist

def save_playlist_wrapper(self):
    """
    Wrapper function to handle saving the playlists.
    Iterates through all discovered playlists and saves them.
    """
    try:
        self.playlist_filename = None
        if not self.playlists:
            self.logger.error("No playlists found to save.")
            return

        for title_id, playlist in self.playlists.items():
            sanitized_title = playlist.get("sanitized_title")
            discovered_links = playlist.get("links") or []

            stream_video_url = self.db_manager.get_player_host_by_title_id(title_id)
            if discovered_links:
                bundle = self.playlist_manager.save_playlist_bundle([sanitized_title], discovered_links,
                                                                    stream_video_url)

                # сохраним в структуре плейлистов для роутера
                playlist["streams_file"] = bundle.m3u_name if bundle.streams_count > 0 else None
                playlist["web_file"] = bundle.web_name if bundle.web_count > 0 else None

                self.logger.debug(
                    f"Playlist for title {sanitized_title} was sent for saving with filename; {bundle}."
                )
            else:
                self.logger.error(f"No links found for title {sanitized_title}, skipping saving.")

        self.save_combined_playlist_wrapper()

    except Exception:
        self.logger.exception("Failed while saving playlists.")

def save_combined_playlist_wrapper(self):
    combined_playlist_filename = (
        "_".join([info["sanitized_title"] for info in self.playlists.values()])[:100] + ".m3u"
    )

    combined_path = os.path.join("playlists", combined_playlist_filename)
    if os.path.exists(combined_path):
        base, ext = os.path.splitext(combined_playlist_filename)
        combined_playlist_filename = f"{base}_{int(datetime.now().timestamp())}{ext}"
        combined_path = os.path.join("playlists", combined_playlist_filename)

    lines = ["#EXTM3U"]
    total = 0

    for title_id, playlist in self.playlists.items():
        links = playlist.get("links") or []
        if not links:
            continue

        host = self.db_manager.get_player_host_by_title_id(title_id) or ""

        for link in links:
            if not isinstance(link, str) or not link.endswith(".m3u8"):
                continue

            full_url = f"{self.pre}{host}{link}"
            lines.append(full_url)
            total += 1

    if total == 0:
        self.logger.error("No valid links found for saving the combined playlist.")
        return

    new_content = "\n".join(lines) + "\n"

    if os.path.exists(combined_path):
        try:
            with open(combined_path, "r", encoding="utf-8") as f:
                existing_content = f.read()
            if existing_content == new_content:
                self.logger.info(f"Combined playlist '{combined_playlist_filename}' is up-to-date.")
                self.playlist_filename = combined_playlist_filename
                return
        except Exception as e:
            self.logger.error(f"Failed to read existing combined playlist: {e}")

    try:
        os.makedirs(os.path.dirname(combined_path), exist_ok=True)
        with open(combined_path, "w", encoding="utf-8") as f:
            f.write(new_content)

        self.logger.info(f"Combined playlist '{combined_playlist_filename}' saved with {total} links.")
        self.playlist_filename = combined_playlist_filename
    except Exception as e:
        self.logger.error(f"Failed to save the combined playlist: {e}")

