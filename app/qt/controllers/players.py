# app/qt/controllers/players.py
from __future__ import annotations

import os
import sys
import subprocess

from pathlib import Path
from datetime import datetime
from typing import Any, Union, List, Dict

from app.vlc.vlc_player import VLCPlayer
from utils.playlists.playlist_key import calc_bundle_key
from utils.security.library_loader import verify_library
from app.qt.app_constants import VLC_PLAYER_HASH, MPV_PLAYER_HASH, MINI_BROWSER_HASH


class PlayerController:
    """
    Переходный контроллер (stage-2/3):
    - svc: доступ к db/api/ui/logger/config/playlist
    - app: доступ к orchestration-методам (display_titles, show_error_notification, invoke_database_save, ...)
    """

    def __init__(self, app: Any, svc: Any):
        self.app = app
        self.svc = svc

    @property
    def db(self):
        return self.svc.db

    @property
    def ui(self):
        return self.svc.ui

    @property
    def log(self):
        return self.svc.logger

    @property
    def api(self):
        return self.svc.api

    def open_mpv_player(self, playlist_path, title_id, skip_data=None):
        """
        DEV-версия: открываем окно mpv прямо в текущем процессе (без бинарника).
        """
        try:
            from app.mpv.mpv_engine import MpvEngine
            from app.mpv.player_window import PlayerWindow

            mpv_kwargs = {}
            # прокси
            if self.app.proxy_enabled:
                mpv_kwargs["proxy"] = self.app.proxy_url

            # логирование (опционально)
            log_file = None
            if self.app.mpv_log_enabled:
                # можно положить рядом с temp/logs
                log_file = str(Path("logs") / "mpv.log")

            self.log.info(f"DEV mpv player launch : {self.app.proxy_url} {self.app.mpv_log_enabled}")

            engine = MpvEngine(
                proxy=None,
                loglevel=("info" if str(self.app.mpv_verbose).lower() in ("info", "debug") else "warn"),
                log_file=log_file
            )

            w = PlayerWindow(
                engine,
                playlist=playlist_path,
                title_id=title_id,
                skip_data=skip_data,
                proxy=mpv_kwargs.get("proxy"),
                resolver=self.app.url_resolver,
                autoplay=True,
                template=self.app.current_template,  # важно!
            )
            w.show()

            # держим ссылку, чтобы окно не убилось GC
            self.app.mpv_window = w

        except Exception as e:
            self.log.error(f"DEV mpv player launch failed: {e}", exc_info=True)
            raise

    def open_standalone_mpv_player(self, playlist_path, title_id, skip_data=None) -> bool:
        """
        PROD-версия: запускаем mpv-плеер как отдельный процесс.
        Возвращает True если удалось запустить, иначе False.
        """
        try:
            if getattr(sys, 'frozen', False):
                mpv_executable = os.path.join(os.path.dirname(sys.executable), self.app.mpv_player_executable_name)

                if not os.path.exists(mpv_executable):
                    self.log.error(f"mpv player executable not found: {mpv_executable}")
                    return False

                cmd = [
                    mpv_executable,
                    "--playlist", str(playlist_path),
                    "--title_id", str(title_id),
                    "--template", str(self.app.current_template),
                ]

                if skip_data:
                    cmd.extend(["--skip_data", skip_data])

                if self.app.prod_key is not None:
                    cmd.extend(["--prod_key", str(self.app.prod_key)])

                # mpv лог/verbose (опционально)
                if self.app.mpv_log_enabled:
                    cmd.extend(["--log", str(Path("logs") / "mpv.log")])
                if str(self.app.mpv_verbose).lower() in ("info", "debug"):
                    cmd.extend(["--verbose"])

                subprocess.Popen(cmd, close_fds=True)
                self.log.info(f"Launched standalone MPV player for title_id: {title_id}")
                return True

            # DEV
            self.open_mpv_player(playlist_path, title_id, skip_data)
            return True

        except Exception as e:
            self.log.error(f"open_standalone_mpv_player failed: {e}", exc_info=True)
            return False

    def open_vlc_player(self, playlist_path, title_id, skip_data=None):
        """
        Создаёт и открывает окно VLC‑плеера.
        Параметры `proxy`, `log` и `log_level` передаются только если они включены.
        """
        vlc_kwargs = {"current_template": self.app.current_template}

        if self.app.log_enabled:
            vlc_kwargs["log"] = self.app.log_enabled
            vlc_kwargs["log_level"] = self.app.verbose

        self.app.vlc_window = VLCPlayer(**vlc_kwargs)

        final_path = playlist_path
        if self.app.proxy_enabled and isinstance(playlist_path, str) and playlist_path.startswith(
                ("http://", "https://")):
            rr = self.app.url_resolver.resolve(playlist_path)
            if rr and getattr(rr, "final_url", None):
                final_path = rr.final_url

        self.log.debug(
            f"title_id: {title_id}, playlist_path: {playlist_path}, skip_data: {skip_data}"
        )
        self.app.vlc_window.load_playlist(final_path, title_id, skip_data)
        self.app.vlc_window.show()
        self.app.vlc_window.timer.start()

    def open_standalone_vlc_player(self, playlist_path, title_id, skip_data=None):
        """Launch VLC player as a separate process."""
        final_path = playlist_path
        if self.app.proxy_enabled and isinstance(playlist_path, str) and playlist_path.startswith(
                ("http://", "https://")):
            rr = self.app.url_resolver.resolve(playlist_path)
            if rr and getattr(rr, "final_url", None):
                final_path = rr.final_url

        if getattr(sys, 'frozen', False):
            # TODO: add other platforms
            vlc_player_executable_name = self.app.config_manager.get_vlc_player_executable_name()
            vlc_player_executable = os.path.join(os.path.dirname(sys.executable), vlc_player_executable_name)

            if VLC_PLAYER_HASH:
                status = verify_library(vlc_player_executable, VLC_PLAYER_HASH)

                if not status:
                    self.log.error(f"VLC player executable hash mismatch! Security risk detected.")
                    self.app.show_error_notification("Security Error", "VLC player executable verification failed.")
                    sys.exit(1)

            cmd = [vlc_player_executable,
                   "--playlist", final_path,
                   "--title_id", str(title_id),
                   "--template", self.app.current_template]

            if skip_data:
                cmd.extend(["--skip_data", skip_data])
            if self.app.prod_key is not None:
                cmd.extend(["--prod_key", str(self.app.prod_key)])

            if self.app.log_enabled:
                cmd.extend(["--log", str(self.app.log_enabled)])
                cmd.extend(["--verbose", str(self.app.verbose)])

            subprocess.Popen(cmd, close_fds=True)
            self.log.info(f"Launched standalone VLC player for title_id: {title_id}")
        else:
            # TODO: DEVELOPMENT Version
            self.open_vlc_player(final_path, title_id, skip_data)

    def open_web_link(self, link: str, title_id: int | None = None, skip_data=None):
        try:
            if not title_id:
                title_id = self.app.current_title_id

            host = None
            if title_id:
                host = self.db.get_player_host_by_title_id(title_id)
            if not host:
                host = self.app.stream_video_url  # fallback

            full = self.app.playlist_manager.make_full_url(link, host)
            if not full:
                self.log.error(f"open_web_link: empty url from link={link!r} host={host!r}")
                return

            self.log.info(f"Opening web link in mini_browser: {full}")
            self.app.router.open_web_urls([full])

        except Exception as e:
            self.log.error(f"open_web_link error: {e}", exc_info=True)

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
                self.log.debug("Using full URL from link")
            else:
                host = self.app.stream_video_url
                if title_id:
                    host = self.db.get_player_host_by_title_id(title_id) if title_id else self.app.stream_video_url
                    self.log.debug(f"Using host from DB: {host}")

                if not link.startswith('/'):
                    link = '/' + link

                open_link = self.app.playlist_manager.make_full_url(link, host)

            if not open_link:
                self.log.error("Empty open_link ...")
                return

            # 1) mpv (если включен)
            if self.app.use_mpv_player:
                ok = self.open_standalone_mpv_player(open_link, str(title_id), skip_data)
                if ok:
                    self.log.info(f"Playing via MPV: {open_link[-50:]}")
                    return

                # mpv не смог стартовать -> fallback на VLC
                self.log.warning("MPV failed to launch, falling back to VLC...")

            # 2) VLC (как было)
            if self.app.use_libvlc:
                self.open_standalone_vlc_player(open_link, str(title_id), skip_data)
            else:
                # внешний плеер
                subprocess.Popen([self.app.video_player_path, open_link])

            self.log.info(f"Playing: {open_link[-50:]}")

        except Exception as e:
            self.log.error(f"Error playing link: {e}", exc_info=True)

    def play_playlist_wrapper(self, file_name=None, title_id=None, skip_data=None):
        """
        Wrapper function to handle playing the playlist.
        Determines the file name and passes it to play_playlist.
        """
        try:
            if not title_id:
                title_id = self.app.current_title_id

            if not file_name:
                file_name = self.app.playlist_filename
                if not file_name:
                    self.log.error("No playlist filename available. Please save a playlist first.")
                    return

            file_path = os.path.join(self.app.playlist_manager.playlist_path, file_name)
            if not os.path.exists(file_path):
                self.log.error(f"Playlist file does not exist: {file_path}")
                return

            # ✅ НОВОЕ: web playlist -> mini browser
            if str(file_name).lower().endswith(".urls"):
                self.log.info(f"Opening web playlist via mini_browser: {file_path}")
                # напрямую, без open_playlist(), чтобы не было циклов
                self.app.router.open_web_file(file_path)
                return

            # дальше — твоя старая логика mpv/vlc
            self.log.debug(f"Playing playlist '{file_name}' for title_id: {title_id}")

            if self.app.use_mpv_player:
                ok = self.open_standalone_mpv_player(file_path, title_id, skip_data)
                if ok:
                    self.log.debug("Playlist launched via MPV successfully")
                    return
                self.log.warning("MPV failed to launch playlist, falling back to VLC.")

            if self.app.use_libvlc:
                self.open_standalone_vlc_player(file_path, title_id, skip_data)
            else:
                self.app.playlist_manager.play_playlist(file_name, self.app.video_player_path)

            self.log.debug("Video player launched successfully")
        except Exception as e:
            self.log.error(f"Error in play_playlist_wrapper: {e}", exc_info=True)

    def get_mini_browser_command(self) -> list[str]:
        """
        DEV: запускаем app/qt_browser/mini_browser.py через текущий интерпретатор
        """
        app_dir = Path(__file__).resolve().parents[2]  # .../app
        mini_browser_py = app_dir / "qt_browser" / "mini_browser.py"
        return [sys.executable, str(mini_browser_py)]

    def ensure_playlist_bundle(self, title_id: int):
        """
        Гарантирует, что для title_id bundle создан, но НЕ пересоздаёт каждый рендер.
        Пересоздаёт только если изменились links или host.
        """
        playlist = (self.app.playlists or {}).get(title_id)
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

        host = self.db.get_player_host_by_title_id(title_id)
        key = calc_bundle_key(title_id, links, host)
        prev_key = playlist.get("bundle_key")

        # если ключ не изменился — bundle уже актуален, ничего не делаем
        if prev_key == key:
            if playlist.get("streams_file") is not None or playlist.get("web_file") is not None:
                return playlist

        sanitized_title = playlist.get("sanitized_title") or str(title_id)

        bundle = self.app.playlist_manager.save_playlist_bundle(
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
            self.app.playlist_filename = None
            if not self.app.playlists:
                self.log.error("No playlists found to save.")
                return

            for title_id, playlist in self.app.playlists.items():
                sanitized_title = playlist.get("sanitized_title")
                discovered_links = playlist.get("links") or []

                stream_video_url = self.db.get_player_host_by_title_id(title_id)
                if discovered_links:
                    bundle = self.app.playlist_manager.save_playlist_bundle([sanitized_title], discovered_links,
                                                                        stream_video_url)

                    # сохраним в структуре плейлистов для роутера
                    playlist["streams_file"] = bundle.m3u_name if bundle.streams_count > 0 else None
                    playlist["web_file"] = bundle.web_name if bundle.web_count > 0 else None

                    self.log.debug(
                        f"Playlist for title {sanitized_title} was sent for saving with filename; {bundle}."
                    )
                else:
                    self.log.error(f"No links found for title {sanitized_title}, skipping saving.")

            self.save_combined_playlist_wrapper()

        except Exception as e:
            self.log.exception(f"Failed while saving playlists. {e}")

    def save_combined_playlist_wrapper(self):
        combined_playlist_filename = (
            "_".join([info["sanitized_title"] for info in self.app.playlists.values()])[:100] + ".m3u"
        )

        combined_path = os.path.join("playlists", combined_playlist_filename)
        if os.path.exists(combined_path):
            base, ext = os.path.splitext(combined_playlist_filename)
            combined_playlist_filename = f"{base}_{int(datetime.now().timestamp())}{ext}"
            combined_path = os.path.join("playlists", combined_playlist_filename)

        lines = ["#EXTM3U"]
        total = 0

        for title_id, playlist in self.app.playlists.items():
            links = playlist.get("links") or []
            if not links:
                continue

            host = self.db.get_player_host_by_title_id(title_id) or ""

            for link in links:
                if not isinstance(link, str) or not link.endswith(".m3u8"):
                    continue

                full_url = f"{self.app.pre}{host}{link}"
                lines.append(full_url)
                total += 1

        if total == 0:
            self.log.error("No valid links found for saving the combined playlist.")
            return

        new_content = "\n".join(lines) + "\n"

        if os.path.exists(combined_path):
            try:
                with open(combined_path, "r", encoding="utf-8") as f:
                    existing_content = f.read()
                if existing_content == new_content:
                    self.log.info(f"Combined playlist '{combined_playlist_filename}' is up-to-date.")
                    self.app.playlist_filename = combined_playlist_filename
                    return
            except Exception as e:
                self.log.error(f"Failed to read existing combined playlist: {e}")

        try:
            os.makedirs(os.path.dirname(combined_path), exist_ok=True)
            with open(combined_path, "w", encoding="utf-8") as f:
                f.write(new_content)

            self.log.info(f"Combined playlist '{combined_playlist_filename}' saved with {total} links.")
            self.app.playlist_filename = combined_playlist_filename
        except Exception as e:
            self.log.error(f"Failed to save the combined playlist: {e}")

