# utils/animedia/animedia_client.py
import httpx
import asyncio
import logging

from typing import List, Dict, Any, Final, Optional
from bs4 import BeautifulSoup

from utils.animedia.animedia_utils import (
    safe_str,
    extract_file_from_html,
    urljoin,
)

class AnimediaClient:
    def __init__(self, base_url: str):
        self.logger = logging.getLogger(__name__)
        self.base_url = base_url.rstrip("/")
        if not self.base_url.startswith(("http://", "https://")):
            self.base_url = f"https://{self.base_url}"
        self._file_cache: Dict[str, str] = {}
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/140.0.0.0 Safari/537.36 Edg/140.0.0.0"
            ),
            "Accept": "application/json",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
        }

    def _log_len(self, name: str, seq: list) -> None:
        n = len(seq)
        self.logger.info(f"{name}: {n} item{'s' if n != 1 else ''}")

    async def search_titles(self, anime_name: str, max_titles: int = 5) -> List[str]:
        url = f"{self.base_url}/index.php?do=search&story={anime_name}"
        async with httpx.AsyncClient(headers=self.headers, timeout=30) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
            container = soup.find("div", class_="content")
            if not container:
                return []

            links = [
                urljoin(self.base_url, a["href"])
                for a in container.select("a.poster__link")
            ]
            self._log_len("search_titles", links[:max_titles])
            return links[:max_titles]

    async def get_vlnks_from_title(self, soup) -> List[str]:
        """
        Возвращает список всех значений атрибута data‑vlnk,
        найденных в HTML‑странице `title_url`.
        """
        a_tags = soup.find_all("a", attrs={"data-vlnk": True})
        vlnks = [tag["data-vlnk"] for tag in a_tags]

        if not vlnks:
            self.logger.warning(f"data‑vlnk not found. ")

        return vlnks

    async def get_episode_file(self, vlnk_url: str) -> Optional[str]:
        async with httpx.AsyncClient(headers=self.headers, timeout=30) as client:
            resp = await client.get(vlnk_url)
            resp.raise_for_status()
            return extract_file_from_html(resp.text, vlnk_url)

    async def collect_episode_files(self, html: str) -> List[str]:
        """
        Возвращает список всех найденных файлов‑потоков
        (массив строк, уже готовых к использованию).
        """
        soup = BeautifulSoup(html, "html.parser")
        vlnk_list = await self.get_vlnks_from_title(soup)

        if not vlnk_list:
            return []

        async def fetch_one(vlnk: str) -> Optional[str]:
            return await self.get_episode_file(vlnk)

        semaphore = asyncio.Semaphore(5)

        async def limited_fetch(vlnk: str) -> Optional[str]:
            async with semaphore:
                return await fetch_one(vlnk)

        results = await asyncio.gather(*[limited_fetch(v) for v in vlnk_list])
        files = [safe_str(url) for url in results if url]
        self.logger.info(f"collect_episode_files: {len(files)} files")
        return files

