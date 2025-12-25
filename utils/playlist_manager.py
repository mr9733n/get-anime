import re
import subprocess
import os
import logging
from dataclasses import dataclass
from typing import Iterable, List, Tuple


@dataclass(frozen=True)
class PlaylistBundle:
    """Результат сохранения: стримовый плейлист + веб-ссылки."""
    m3u_name: str
    m3u_path: str
    web_name: str
    web_path: str
    streams_count: int
    web_count: int


class PlaylistManager:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.playlist_path = "playlists/"
        os.makedirs(self.playlist_path, exist_ok=True)
        self.pre = "https://"

    @staticmethod
    def sanitize_filename(name):
        return re.sub(r'[<>:"/\\|?*]', '_', name)

    # ----------------------------
    # NEW: split + normalize helpers
    # ----------------------------
    @staticmethod
    def _is_stream_link(link: str) -> bool:
        if not isinstance(link, str):
            return False
        s = link.strip().lower()
        if not s:
            return False
        # допускаем query-string
        return ".m3u8" in s

    @staticmethod
    def _is_web_link(link: str) -> bool:
        """Всё, что похоже на URL/путь страницы (кроме .m3u8)"""
        if not isinstance(link, str):
            return False
        s = link.strip()
        if not s:
            return False
        if s.endswith(".m3u8"):
            return False
        # абсолютные URL
        if s.startswith(("http://", "https://")):
            return True
        # относительные пути (обычно страницы/плееры вида /player/.. или /release/..)
        if s.startswith("/"):
            return True
        # домен без схемы
        if "." in s and " " not in s:
            return True
        return False

    def split_links(self, links: Iterable[str]) -> Tuple[List[str], List[str]]:
        """Разделяет на stream и web. Ничего не нормализует, только классифицирует."""
        stream_links: List[str] = []
        web_links: List[str] = []
        for link in links or []:
            if self._is_stream_link(link):
                stream_links.append(link.strip())
            elif self._is_web_link(link):
                web_links.append(link.strip())
        return stream_links, web_links

    def make_full_url(self, link: str, host: str) -> str:
        """
        Нормализует ссылку в полный URL.
        - если уже http(s) → оставляем
        - если относительный путь (/...) → https://{host}{/path}
        - если домен без схемы → https://{domain}
        """
        s = (link or "").strip()
        if not s:
            return ""

        if s.startswith(("http://", "https://")):
            return s

        # домен без схемы
        if not s.startswith("/"):
            return "https://" + s

        # относительный путь
        host = (host or "").strip()
        # host иногда может прийти уже с https:// (на всякий)
        host = host.replace("http://", "").replace("https://", "")
        return f"{self.pre}{host}{s}"

    def _build_m3u_content(self, stream_links: List[str], host: str) -> str:
        lines = ["#EXTM3U"]
        for link in stream_links:
            full = self.make_full_url(link, host)
            if full:
                lines.append(full)
        return "\n".join(lines) + "\n"

    def _build_urls_content(self, web_links: List[str], host: str) -> str:
        # простой формат: одна ссылка на строку
        out: List[str] = []
        for link in web_links:
            full = self.make_full_url(link, host)
            if full:
                out.append(full)
        return "\n".join(out) + ("\n" if out else "")

    # ----------------------------
    # NEW: bundle saver (m3u + urls)
    # ----------------------------
    def save_playlist_bundle(self, sanitized_titles, links, stream_video_url) -> PlaylistBundle:
        """
        Сохраняет:
        - <title>.m3u  (только .m3u8)
        - <title>.urls (все остальные web-страницы)
        Возвращает информацию о двух файлах.
        """
        base_name = "".join(sanitized_titles)[:100]
        m3u_name = base_name + ".m3u"
        web_name = base_name + ".urls"

        m3u_path = os.path.join(self.playlist_path, m3u_name)
        web_path = os.path.join(self.playlist_path, web_name)

        stream_links, web_links = self.split_links(links)
        streams_count = len(stream_links)
        web_count = len(web_links)

        new_m3u = self._build_m3u_content(stream_links, stream_video_url) if streams_count else ""
        new_web = self._build_urls_content(web_links, stream_video_url) if web_count else ""

        def _write_if_changed(path: str, content: str, label: str):
            if os.path.exists(path):
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        if f.read() == content:
                            self.logger.info(f"{label} '{os.path.basename(path)}' is up-to-date.")
                            return
                except Exception as e:
                    self.logger.warning(f"Failed to read {label} for compare: {e}")
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as wf:
                wf.write(content)

        def _delete_if_exists(path: str, label: str):
            if os.path.exists(path):
                try:
                    os.remove(path)
                    self.logger.info(f"Removed empty {label}: {os.path.basename(path)}")
                except Exception as e:
                    self.logger.warning(f"Failed to remove {label} '{path}': {e}")

        # m3u
        if streams_count:
            _write_if_changed(m3u_path, new_m3u, "Playlist")
        else:
            _delete_if_exists(m3u_path, "m3u")

        # urls
        if web_count:
            _write_if_changed(web_path, new_web, "Web list")
        else:
            _delete_if_exists(web_path, "urls")

        return PlaylistBundle(
            m3u_name=m3u_name,
            m3u_path=m3u_path,
            web_name=web_name,
            web_path=web_path,
            streams_count=streams_count,
            web_count=web_count,
        )

    # ----------------------------
    # OLD API: keep compatibility (returns only .m3u name)
    # ----------------------------
    def save_playlist(self, sanitized_titles, links, stream_video_url):
        """
        СТАРОЕ поведение: возвращает только имя .m3u, чтобы не ломать текущий app.py.
        При этом теперь параллельно создаётся .urls рядом (через bundle).
        """
        bundle = self.save_playlist_bundle(sanitized_titles, links, stream_video_url)
        return bundle.m3u_name

    def save_single_stream_playlist(self, url: str, title_id: int | None = None) -> str:
        """
        Создаёт временный плейлист .m3u для одной серии (один URL).
        Возвращает ПУТЬ к файлу.
        """
        safe_tid = str(title_id) if title_id is not None else "noid"
        name = f"_single_{safe_tid}_{int(__import__('time').time())}.m3u"
        path = os.path.join(self.playlist_path, name)

        content = "#EXTM3U\n" + url.strip() + "\n"
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return path

    def play_playlist(self, file_name, video_player_path):
        file_path = os.path.join(self.playlist_path, file_name)
        try:
            if os.path.exists(file_path):
                media_player_command = [video_player_path, file_path]
                subprocess.Popen(media_player_command)
                self.logger.debug(f"Playing playlist: {file_path}.")
            else:
                print("Playlist file not found.")
        except Exception as e:
            self.logger.error(f"Failed to play playlist: {e}", exc_info=True)
