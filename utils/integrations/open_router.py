# core/open_router.py
from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from typing import Iterable, Optional


@dataclass(frozen=True)
class PlaylistTargets:
    streams_file: Optional[str] = None   # .m3u
    web_file: Optional[str] = None       # .urls or .json
    title_id: Optional[int] = None


class OpenRouter:
    """
    Роутер решает:
    - stream (.m3u8 / .m3u) -> player target (через методы App)
    - web (pages/urls) -> mini_browser
    """

    def __init__(self, app):
        self.app = app

    @staticmethod
    def is_stream_url(url: str) -> bool:
        return url.strip().lower().endswith(".m3u8")

    def open_one(self, url: str, *, title_id: int | None = None, skip_data=None):
        if self.is_stream_url(url):
            return self.app.play_link(url, title_id=title_id, skip_data=skip_data)
        return self.open_web_urls([url])

    def open_playlist(self, targets: PlaylistTargets, *, skip_data=None):
        if targets.streams_file:
            return self.app.play_playlist_wrapper(
                file_name=targets.streams_file,
                title_id=targets.title_id,
                skip_data=skip_data,
            )

        if targets.web_file:
            return self.open_web_file(targets.web_file)

        self.app.logger.error("OpenRouter: nothing to open (no streams_file/web_file).")

    # --- web openers ---

    def open_web_file(self, web_file: str):
        # гарантируем абсолютный путь
        if not os.path.isabs(web_file):
            web_file = os.path.abspath(web_file)

        cmd = self._mini_browser_cmd_base()
        cmd += ["--file", web_file]

        self.app.logger.info(f"Launching mini_browser: {' '.join(cmd)}")
        subprocess.Popen(cmd, close_fds=True)

    def open_web_urls(self, urls: Iterable[str]):
        urls = [u for u in (urls or []) if isinstance(u, str) and u.strip()]
        if not urls:
            self.app.logger.error("OpenRouter: open_web_urls called with empty list.")
            return

        cmd = self._mini_browser_cmd_base()
        cmd += list(urls)
        subprocess.Popen(cmd, close_fds=True)

    def _mini_browser_cmd_base(self) -> list[str]:
        """
        app должен предоставить:
          - get_mini_browser_command(): list[str]  (например [sys.executable, path_to_mini_browser_py])
          - proxy_enabled/proxy_url
        """
        cmd = self.app.get_mini_browser_command()



        if str(getattr(self.app, "proxy_enabled", "false")).lower() == "true":
            proxy = str(getattr(self.app, "proxy_url", "")).strip()
            if proxy:
                cmd += ["--socks", proxy]

        return cmd
