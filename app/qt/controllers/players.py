# app/qt/controllers/players.py
from __future__ import annotations

import os
import sys
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

# === Импорт VLC на уровне модуля (не lazy) ===
try:
    from app.vlc.vlc_player import VLCPlayer
    VLC_AVAILABLE = True
except ImportError:
    VLCPlayer = None
    VLC_AVAILABLE = False

from app.qt.app_constants import VLC_PLAYER_HASH, MPV_PLAYER_HASH
from app.qt.protocols import IDBManager
from utils.playlists.playlist_key import calc_bundle_key
from utils.security.library_loader import verify_library

if TYPE_CHECKING:
    from logging import Logger
    from app.qt.app_context import AppContext
    from utils.playlists.playlist_manager import PlaylistManager
    from utils.net.url_resolve_service import UrlResolveService


@dataclass
class PlayerControllerDeps:
    """Явные зависимости PlayerController"""
    logger: Logger
    db: IDBManager
    context: AppContext
    playlist_manager: PlaylistManager

    # Optional dependencies
    url_resolver: UrlResolveService | None = None

    # Config
    use_libvlc: bool = False
    use_mpv_player: bool = False
    proxy_enabled: bool = False
    proxy_url: str = ""
    log_enabled: bool = False
    verbose: str = "2"
    mpv_log_enabled: bool = False
    mpv_verbose: str = "info"
    mpv_player_executable_name: str = "mpv_player.exe"
    video_player_path: str = ""
    prod_key: str | None = None

    # Callbacks
    get_router: Callable[[], Any] | None = None  # для open_web


class PlayerController:
    """
    Контроллер для работы с плеерами (VLC, MPV, внешние).
    Управляет воспроизведением и плейлистами.
    """

    def __init__(self, deps: PlayerControllerDeps):
        self._deps = deps
        self._vlc_window = None
        self._mpv_window = None

    # === Properties ===

    @property
    def log(self) -> Logger:
        return self._deps.logger

    @property
    def db(self) -> IDBManager:
        return self._deps.db

    @property
    def ctx(self) -> AppContext:
        return self._deps.context

    @property
    def playlist_manager(self) -> PlaylistManager:
        return self._deps.playlist_manager

    @property
    def url_resolver(self):
        return self._deps.url_resolver

    # === Public API: Playback ===

    def play_link(
            self,
            link: str,
            title_id: int | None = None,
            skip_data: str | None = None,
    ) -> None:
        """Воспроизводит ссылку на эпизод."""
        try:
            open_link = self._resolve_link(link, title_id)
            if not open_link:
                self.log.error("Empty open_link")
                return

            # Пробуем MPV
            if self._deps.use_mpv_player:
                if self._play_via_mpv(open_link, title_id, skip_data):
                    return
                self.log.warning("MPV failed, falling back to VLC...")

            # Пробуем VLC
            if self._deps.use_libvlc:
                self._play_via_vlc(open_link, title_id, skip_data)
            else:
                self._play_via_external(open_link)

            self.log.info(f"Playing: ...{open_link[-50:]}")

        except Exception as e:
            self.log.error(f"Error playing link: {e}", exc_info=True)

    def play_playlist_wrapper(
            self,
            file_name: str | None = None,
            title_id: int | None = None,
            skip_data: str | None = None,
    ) -> None:
        """Воспроизводит плейлист."""
        try:
            title_id = title_id or self.ctx.current_title_id
            file_name = file_name or self.ctx.playlist_filename

            if not file_name:
                self.log.error("No playlist filename available.")
                return

            file_path = os.path.join(self.playlist_manager.playlist_path, file_name)
            if not os.path.exists(file_path):
                self.log.error(f"Playlist file does not exist: {file_path}")
                return

            # Web playlist -> mini browser
            if str(file_name).lower().endswith(".urls"):
                self._play_web_playlist(file_path)
                return

            # MPV/VLC playlist
            self._play_media_playlist(file_path, title_id, skip_data)

        except Exception as e:
            self.log.error(f"Error in play_playlist_wrapper: {e}", exc_info=True)

    def open_web_link(
            self,
            link: str,
            title_id: int | None = None,
            skip_data: str | None = None,
    ) -> None:
        """Открывает ссылку в мини-браузере."""
        try:
            title_id = title_id or self.ctx.current_title_id

            host = None
            if title_id:
                host = self.db.get_player_host_by_title_id(title_id)
            if not host:
                host = self.ctx.stream_video_url

            full_url = self.playlist_manager.make_full_url(link, host)
            if not full_url:
                self.log.error(f"open_web_link: empty url from link={link!r}")
                return

            self.log.info(f"Opening web link in mini_browser: {full_url}")

            router = self._deps.get_router() if self._deps.get_router else None
            if router:
                router.open_web_urls([full_url])

        except Exception as e:
            self.log.error(f"open_web_link error: {e}", exc_info=True)

    # === Public API: Playlist Management ===

    def save_playlist_wrapper(self) -> None:
        """Сохраняет все обнаруженные плейлисты."""
        try:
            self.ctx.playlist_filename = None

            if not self.ctx.playlists:
                self.log.error("No playlists found to save.")
                return

            for title_id, playlist in self.ctx.playlists.items():
                self._save_single_playlist(title_id, playlist)

            self._save_combined_playlist()

        except Exception as e:
            self.log.exception(f"Failed while saving playlists: {e}")

    def ensure_playlist_bundle(self, title_id: int) -> dict | None:
        """
        Гарантирует, что bundle для title_id создан.
        Пересоздаёт только если изменились links или host.
        """
        playlist = (self.ctx.playlists or {}).get(title_id)
        if not playlist:
            return None

        links = playlist.get("links") or []
        if not links:
            return self._empty_bundle(playlist)

        host = self.db.get_player_host_by_title_id(title_id)
        key = calc_bundle_key(title_id, links, host)
        prev_key = playlist.get("bundle_key")

        # Если ключ не изменился — bundle актуален
        if prev_key == key and (playlist.get("streams_file") or playlist.get("web_file")):
            return playlist

        # Создаём bundle
        sanitized_title = playlist.get("sanitized_title") or str(title_id)
        bundle = self.playlist_manager.save_playlist_bundle(
            [sanitized_title], links, host
        )

        # Сохраняем метаданные
        playlist["bundle_key"] = key
        playlist["streams_count"] = bundle.streams_count
        playlist["web_count"] = bundle.web_count
        playlist["streams_file"] = bundle.m3u_name if bundle.streams_count > 0 else None
        playlist["web_file"] = bundle.web_name if bundle.web_count > 0 else None

        return playlist

    def get_mini_browser_command(self) -> list[str]:
        """Возвращает команду для запуска мини-браузера (DEV mode)."""
        app_dir = Path(__file__).resolve().parents[2]
        mini_browser_py = app_dir / "qt_browser" / "mini_browser.py"
        return [sys.executable, str(mini_browser_py)]

    # === Private: Link Resolution ===

    def _resolve_link(self, link: str, title_id: int | None) -> str | None:
        """Преобразует ссылку в полный URL."""
        if link.startswith(("http://", "https://")):
            return link

        host = self.db.get_player_host_by_title_id(title_id) if title_id else None
        if not host:
            host = self.ctx.stream_video_url

        if not link.startswith('/'):
            link = '/' + link

        return self.playlist_manager.make_full_url(link, host)

    def _resolve_url_with_proxy(self, url: str) -> str:
        """Резолвит URL через прокси если нужно."""
        if not self._deps.proxy_enabled:
            return url
        if not url.startswith(("http://", "https://")):
            return url
        if not self.url_resolver:
            return url

        result = self.url_resolver.resolve(url)
        if result and getattr(result, "final_url", None):
            return result.final_url
        return url

    # === Private: Player Implementations ===

    def _play_via_mpv(
            self,
            url: str,
            title_id: int | None,
            skip_data: str | None,
    ) -> bool:
        """Воспроизводит через MPV. Возвращает True если успешно."""
        try:
            if getattr(sys, 'frozen', False):
                return self._play_mpv_standalone(url, title_id, skip_data)
            else:
                self._play_mpv_embedded(url, title_id, skip_data)
                return True
        except Exception as e:
            self.log.error(f"MPV playback failed: {e}", exc_info=True)
            return False

    def _play_mpv_standalone(
            self,
            url: str,
            title_id: int | None,
            skip_data: str | None,
    ) -> bool:
        """Запускает MPV как отдельный процесс (PROD)."""
        mpv_exe = os.path.join(
            os.path.dirname(sys.executable),
            self._deps.mpv_player_executable_name
        )

        if not os.path.exists(mpv_exe):
            self.log.error(f"MPV executable not found: {mpv_exe}")
            return False

        cmd = [
            mpv_exe,
            "--playlist", str(url),
            "--title_id", str(title_id or ""),
            "--template", str(self.ctx.current_template),
        ]

        if skip_data:
            cmd.extend(["--skip_data", skip_data])
        if self._deps.prod_key:
            cmd.extend(["--prod_key", str(self._deps.prod_key)])
        if self._deps.mpv_log_enabled:
            cmd.extend(["--log", str(Path("logs") / "mpv.log")])
        if str(self._deps.mpv_verbose).lower() in ("info", "debug"):
            cmd.extend(["--verbose"])

        subprocess.Popen(cmd, close_fds=True)
        self.log.info(f"Launched standalone MPV for title_id: {title_id}")
        return True

    def _play_mpv_embedded(
            self,
            url: str,
            title_id: int | None,
            skip_data: str | None,
    ) -> None:
        """Запускает MPV встроенно (DEV)."""
        from app.mpv.mpv_engine import MpvEngine
        from app.mpv.player_window import PlayerWindow

        log_file = str(Path("logs") / "mpv.log") if self._deps.mpv_log_enabled else None
        loglevel = "info" if str(self._deps.mpv_verbose).lower() in ("info", "debug") else "warn"

        engine = MpvEngine(proxy=None, loglevel=loglevel, log_file=log_file)

        self._mpv_window = PlayerWindow(
            engine,
            playlist=url,
            title_id=title_id,
            skip_data=skip_data,
            proxy=self._deps.proxy_url if self._deps.proxy_enabled else None,
            resolver=self.url_resolver,
            autoplay=True,
            template=self.ctx.current_template,
        )
        self._mpv_window.show()

    def _play_via_vlc(
            self,
            url: str,
            title_id: int | None,
            skip_data: str | None,
    ) -> None:
        """Воспроизводит через VLC."""
        final_url = self._resolve_url_with_proxy(url)

        if getattr(sys, 'frozen', False):
            self._play_vlc_standalone(final_url, title_id, skip_data)
        else:
            self._play_vlc_embedded(final_url, title_id, skip_data)

    def _play_vlc_standalone(
            self,
            url: str,
            title_id: int | None,
            skip_data: str | None,
    ) -> None:
        """Запускает VLC как отдельный процесс."""
        # Получаем путь к VLC exe (нужен метод из config)
        vlc_exe = self._get_vlc_executable_path()

        if VLC_PLAYER_HASH:
            if not verify_library(vlc_exe, VLC_PLAYER_HASH):
                self.log.error("VLC player hash mismatch!")
                return

        cmd = [
            vlc_exe,
            "--playlist", url,
            "--title_id", str(title_id or ""),
            "--template", self.ctx.current_template,
        ]

        if skip_data:
            cmd.extend(["--skip_data", skip_data])
        if self._deps.prod_key:
            cmd.extend(["--prod_key", str(self._deps.prod_key)])
        if self._deps.log_enabled:
            cmd.extend(["--log", str(self._deps.log_enabled)])
            cmd.extend(["--verbose", str(self._deps.verbose)])

        subprocess.Popen(cmd, close_fds=True)

    def _play_vlc_embedded(
            self,
            url: str,
            title_id: int | None,
            skip_data: str | None,
    ) -> None:
        """Запускает VLC встроенно."""
        if not VLC_AVAILABLE or VLCPlayer is None:
            self.log.error("VLC not available")
            return

        vlc_kwargs = {"current_template": self.ctx.current_template}
        if self._deps.log_enabled:
            vlc_kwargs["log"] = self._deps.log_enabled
            vlc_kwargs["log_level"] = self._deps.verbose

        self._vlc_window = VLCPlayer(**vlc_kwargs)
        self._vlc_window.load_playlist(url, title_id, skip_data)
        self._vlc_window.show()
        self._vlc_window.timer.start()

    def _play_via_external(self, url: str) -> None:
        """Воспроизводит через внешний плеер."""
        subprocess.Popen([self._deps.video_player_path, url])

    def _get_vlc_executable_path(self) -> str:
        """Возвращает путь к VLC executable."""
        # Этот метод нужно адаптировать под вашу структуру
        return os.path.join(os.path.dirname(sys.executable), "vlc_player.exe")

    # === Private: Playlist Helpers ===

    def _play_web_playlist(self, file_path: str) -> None:
        """Открывает web playlist в мини-браузере."""
        self.log.info(f"Opening web playlist: {file_path}")
        router = self._deps.get_router() if self._deps.get_router else None
        if router:
            router.open_web_file(file_path)

    def _play_media_playlist(
            self,
            file_path: str,
            title_id: int | None,
            skip_data: str | None,
    ) -> None:
        """Воспроизводит медиа плейлист."""
        if self._deps.use_mpv_player:
            if self._play_via_mpv(file_path, title_id, skip_data):
                return
            self.log.warning("MPV failed for playlist, falling back to VLC.")

        if self._deps.use_libvlc:
            self._play_via_vlc(file_path, title_id, skip_data)
        else:
            self.playlist_manager.play_playlist(
                os.path.basename(file_path),
                self._deps.video_player_path
            )

    def _save_single_playlist(self, title_id: int, playlist: dict) -> None:
        """Сохраняет один плейлист."""
        sanitized_title = playlist.get("sanitized_title")
        links = playlist.get("links") or []

        if not links:
            self.log.error(f"No links for title {sanitized_title}, skipping.")
            return

        host = self.db.get_player_host_by_title_id(title_id)
        bundle = self.playlist_manager.save_playlist_bundle(
            [sanitized_title], links, host
        )

        playlist["streams_file"] = bundle.m3u_name if bundle.streams_count > 0 else None
        playlist["web_file"] = bundle.web_name if bundle.web_count > 0 else None

        self.log.debug(f"Playlist for {sanitized_title} saved: {bundle}")

    def _save_combined_playlist(self) -> None:
        """Сохраняет объединённый плейлист."""
        filename = self._generate_combined_filename()
        path = os.path.join("playlists", filename)

        lines = ["#EXTM3U"]
        total = 0

        for title_id, playlist in self.ctx.playlists.items():
            links = playlist.get("links") or []
            host = self.db.get_player_host_by_title_id(title_id) or ""

            for link in links:
                if isinstance(link, str) and link.endswith(".m3u8"):
                    lines.append(f"https://{host}{link}")
                    total += 1

        if total == 0:
            self.log.error("No valid links for combined playlist.")
            return

        content = "\n".join(lines) + "\n"

        # Проверяем, изменилось ли содержимое
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    if f.read() == content:
                        self.log.info(f"Combined playlist up-to-date: {filename}")
                        self.ctx.playlist_filename = filename
                        return
            except Exception:
                pass

        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

        self.log.info(f"Combined playlist saved: {filename} ({total} links)")
        self.ctx.playlist_filename = filename

    def _generate_combined_filename(self) -> str:
        """Генерирует имя для объединённого плейлиста."""
        names = [info["sanitized_title"] for info in self.ctx.playlists.values()]
        base = "_".join(names)[:100]
        filename = f"{base}.m3u"

        path = os.path.join("playlists", filename)
        if os.path.exists(path):
            filename = f"{base}_{int(datetime.now().timestamp())}.m3u"

        return filename

    def _empty_bundle(self, playlist: dict) -> dict:
        """Возвращает пустой bundle."""
        playlist["streams_file"] = None
        playlist["web_file"] = None
        playlist["streams_count"] = 0
        playlist["web_count"] = 0
        playlist["bundle_key"] = None
        return playlist