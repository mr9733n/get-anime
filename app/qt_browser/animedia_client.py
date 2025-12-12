# animedia_client.py
import json
import httpx
import asyncio
import logging

from bs4 import BeautifulSoup
from pathlib import Path
from urllib.parse import urlparse
from typing import List, Dict, Any, Final, Optional, Coroutine
from animedia_utils import (
    safe_str,
    uniq,
    extract_file_from_html,
    urljoin, sort_by_episode,
    replace_spaces,
    text_or_none,
)

BATCH_SIZE = 30
CONCURRENCY = 8
INTER_BATCH_DELAY = 1.5
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".svg"}


class AnimediaClient:
    def __init__(self, base_url: str, net_client=None, cache_dir: str = "temp"):
        self.logger = logging.getLogger(__name__)
        self.base_url = base_url.rstrip("/")
        self.net_client = net_client
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
        self.cache_path = Path(cache_dir) / "animedia_vlnk.json"
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.sanitized_name = None
        # загрузка кеша из файла, если он существует
        if self.cache_path.is_file():
            try:
                self._file_cache = json.loads(self.cache_path.read_text())
            except Exception as exc:
                self.logger.warning(f"Failed to load cache: {exc}")
                self._file_cache = {}
        else:
            self._file_cache = {}

    def _save_cache(self) -> None:
        """Записывает текущий кеш в файл (вызывается после каждой успешной загрузки)."""
        try:
            self.cache_path.write_text(json.dumps(self._file_cache, ensure_ascii=False, indent=2))
        except Exception as exc:
            self.logger.error(f"Unable to write cache: {exc}")

    def _log_len(self, name: str, seq: list) -> None:
        n = len(seq)
        self.logger.info(f"{name}: {n} item{'s' if n != 1 else ''}")

    async def search_titles(self, anime_name: str, max_titles: int = 5) -> List[str]:
        url = f"{self.base_url}/index.php?do=search&story={anime_name}"
        async with self.net_client.create_async_httpx_client(headers=self.headers, timeout=30, follow_redirects=True) as client:
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

    @staticmethod
    def _extract_vlnks(soup: BeautifulSoup) -> List[str]:
        raw = [tag["data-vlnk"] for tag in soup.find_all("a", attrs={"data-vlnk": True})]
        # Приводим к абсолютному виду (base_url будет передан в клиент)
        return raw

    def _ensure_absolute_url(self, url: str) -> Optional[str]:
        parsed = urlparse(url)
        if parsed.scheme in ("http", "https"):
            return url
        if url.startswith("/"):
            return urljoin(self.base_url, url)
        self.logger.warning(f"Invalid vlnk URL, skipping: {url!r}")
        return None

    def _is_image_placeholder(self, url: str) -> bool:
        """
        Возвращает True, если URL выглядит как ссылка на изображение.
        """
        parsed = urlparse(url)
        path = parsed.path.lower()
        return any(path.endswith(ext) for ext in IMAGE_EXTS)

    async def _fetch_file_from_vlnk(self, vlnk_url: str) -> Optional[str]:
        # 1️⃣ Приводим к абсолютному виду
        vlnk_url = self._ensure_absolute_url(vlnk_url)
        if vlnk_url is None:
            return None

        # 2️⃣ Пропускаем заглушки‑картинки
        if self._is_image_placeholder(vlnk_url):
            self.logger.debug(f"Skipping image placeholder: {vlnk_url}")
            return None

        # 3️⃣ Кеш‑проверка
        if vlnk_url in self._file_cache:
            return self._file_cache[vlnk_url]

        max_tries = 5
        backoff = 1
        async with self.net_client.create_async_httpx_client(headers=self.headers, timeout=30, follow_redirects=True) as client:
            for attempt in range(1, max_tries + 1):
                try:
                    resp = await client.get(vlnk_url)
                    resp.raise_for_status()
                    file_url = extract_file_from_html(resp.text, vlnk_url)
                    if file_url:
                        self._file_cache[vlnk_url] = file_url
                        return file_url
                    raise ValueError("file not found in response")
                except httpx.HTTPStatusError as exc:
                    if exc.response.status_code == 429:
                        retry_after = exc.response.headers.get("Retry-After")
                        wait = float(retry_after) if retry_after and retry_after.isdigit() else backoff
                        self.logger.warning(
                            f"429 Too Many Requests – waiting {wait}s (attempt {attempt})"
                        )
                    elif exc.response.status_code < 500:
                        self.logger.warning(f"vlnk {vlnk_url} returned {exc.response.status_code}")
                        return None
                    else:
                        wait = backoff

                    if attempt == max_tries:
                        self.logger.error(
                            f"vlnk {vlnk_url} failed after {max_tries} attempts: {exc}"
                        )
                        return None

                    await asyncio.sleep(wait)
                    backoff *= 2
        return None

    async def collect_episode_files(self, html: str) -> None | list[Any] | list[str]:
        try:
            soup = BeautifulSoup(html, "html.parser")

            header = soup.select_one("header.pmovie__header")
            name_en = text_or_none(header.select_one("div.pmovie__main-info"))
            self.sanitized_name = replace_spaces(name_en)

            raw_vlnks = self._extract_vlnks(soup)

            vlnk_list = [self._ensure_absolute_url(v) for v in raw_vlnks]
            vlnk_list = [v for v in vlnk_list if v]

            if not vlnk_list:
                self.logger.warning("No data‑vlnk found on page")
                return []

            self.logger.info(f"Found {len(vlnk_list)} vlnk links – start fetching")

            results: List[str] = []
            try:
                for i in range(0, len(vlnk_list), BATCH_SIZE):
                    batch = vlnk_list[i:i + BATCH_SIZE]
                    self.logger.debug(
                        f"Processing batch {i // BATCH_SIZE + 1} ({len(batch)} items)"
                    )

                    results.extend(safe_str(url) for url in vlnk_list if url)

                self.logger.info(f"collect_episode_files: {len(results)} files collected")
                return results
            finally:
                # гарантируем запись кеша
                self._save_cache()
        except Exception as e:
            self.logger.error(f"Error collect_episode_files: {e}")


    async def search_anime_and_collect(
        self,
        anime_name: str,
        max_titles: int = 5,
    ) -> List[str]:
        try:
            title_urls = await self.search_titles(anime_name, max_titles)

            for url in title_urls:
                async with self.net_client.create_async_httpx_client(headers=self.headers, timeout=30, follow_redirects=True) as http:
                    page_resp = await http.get(url)
                    page_resp.raise_for_status()
                    html = page_resp.text

                # ---------- 3️⃣ Сбор файлов эпизодов ----------
                raw_files = await self.collect_episode_files(html)
                unique_files = uniq(raw_files)
                # sorted_links = sort_by_episode(unique_files)

            return unique_files, self.sanitized_name
        except Exception:
            pass


