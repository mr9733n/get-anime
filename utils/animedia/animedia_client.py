# utils/animedia/animedia_client.py
import json
import httpx
import asyncio
import logging
from pathlib import Path
from urllib.parse import urlparse
from typing import List, Dict, Any, Final, Optional, Coroutine, Tuple
from bs4 import BeautifulSoup
from utils.animedia.animedia_utils import (
    safe_str,
    extract_file_from_html,
    urljoin,
)

BATCH_SIZE = 30
CONCURRENCY = 8
INTER_BATCH_DELAY = 1.5
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".svg"}

class AnimediaClient:
    def __init__(self, base_url: str, net_client=None, cache_dir: str = "temp"):
        self.net_client = net_client
        self.logger = logging.getLogger(__name__)
        self.base_url = base_url.rstrip("/")
        self.ajax_url = f"{self.base_url}/engine/mods/custom/ajax.php"
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
        vlnk_url = self._ensure_absolute_url(vlnk_url)
        if vlnk_url is None:
            return None

        if self._is_image_placeholder(vlnk_url):
            self.logger.debug(f"Skipping image placeholder: {vlnk_url}")
            return None

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
            raw_vlnks = self._extract_vlnks(soup)
            vlnk_list = [self._ensure_absolute_url(v) for v in raw_vlnks]
            vlnk_list = [v for v in vlnk_list if v]

            if not vlnk_list:
                self.logger.warning("No data‑vlnk found on page")
                return []

            self.logger.info(f"Found {len(vlnk_list)} vlnk links – start fetching")
            semaphore = asyncio.Semaphore(CONCURRENCY)

            async def limited_fetch(vlnk: str) -> Optional[str]:
                async with semaphore:
                    return await self._fetch_file_from_vlnk(vlnk)

            results: List[str] = []
            try:
                for i in range(0, len(vlnk_list), BATCH_SIZE):
                    batch = vlnk_list[i:i + BATCH_SIZE]
                    self.logger.debug(
                        f"Processing batch {i // BATCH_SIZE + 1} ({len(batch)} items)"
                    )
                    batch_results = await asyncio.gather(
                        *[limited_fetch(v) for v in batch],
                        return_exceptions=False,
                    )
                    results.extend(safe_str(url) for url in batch_results if url)
                    await asyncio.sleep(INTER_BATCH_DELAY)
                self.logger.info(f"collect_episode_files: {len(results)} files collected")
                return results
            finally:
                self._save_cache()
        except Exception as e:
            self.logger.error(f"Error collect_episode_files: {e}")

    #-- New titles and anounces

    async def fetch_new_titles_html(self, page: int) -> str:
        """Возвращает HTML‑текст страницы `page`."""
        data = {
            "name": "poslednie-serii",
            "cstart": str(page),
            "action": "getpage",
        }
        async with self.net_client.create_async_httpx_client(
            headers=self.headers, timeout=30, follow_redirects=True
        ) as client:
            resp = await client.post(self.ajax_url, data=data)
            resp.raise_for_status()
            try:
                data = resp.json()
                return data.get("html", "")
            except json.JSONDecodeError:
                return resp.text

    def _build_titles(self, items: List[BeautifulSoup], max_titles: int) -> List[str]:
        results: List[str] = []
        for a in items[:max_titles]:
            title = (
                a.select_one("div.ftop-item__title").get_text(strip=True)
                if a.select_one("div.ftop-item__title")
                else "—"
            )
            meta = (
                a.select_one("div.ftop-item__meta").get_text(strip=True)
                if a.select_one("div.ftop-item__meta")
                else "—"
            )
            ep_tag = a.select_one("div.animseri > span")
            episode = ep_tag.get_text(strip=True) if ep_tag else None

            parts = [title, meta]
            if episode:
                parts.append(f"{episode} серия")
            results.append(" – ".join(parts))
        return results

    async def parse_page_for_announce_titles(self, html: str, max_titles: int) -> List[str]:
        soup = BeautifulSoup(html, "html.parser")
        amd_blocks = soup.select("div.amd")
        announce_items: List[BeautifulSoup] = []
        for blk in amd_blocks:
            if blk.select_one("div.js-custom-content"):
                continue
            announce_items.extend(self._extract_items(blk))
        return self._build_titles(announce_items, max_titles)

    async def parse_page_for_new_titles(self, html: str, max_titles: int) -> List[str]:
        soup = BeautifulSoup(html, "html.parser")
        main_block = soup.select_one("div.js-custom-content")
        if not main_block:
            return []
        items = self._extract_items(main_block)
        return self._build_titles(items, max_titles)

    def _extract_items(self, container: BeautifulSoup) -> List[BeautifulSoup]:
        """Возвращает список <a class="ftop-item"> внутри переданного контейнера."""
        return container.select("a.ftop-item")

    async def get_total_pages(self) -> int:
        """Определяет количество страниц, используя первую страницу."""
        first_html = await self.fetch_new_titles_html(1)
        soup = BeautifulSoup(first_html, "html.parser")
        nav = soup.find("div", class_="ac-navigation")
        if not nav:
            return 1
        pages = [int(a["data-page"]) for a in nav.select("a[data-page]")]
        return max(pages) if pages else 1

    async def get_new_titles(self) -> str | None:
        async with self.net_client.create_async_httpx_client(
            headers=self.headers, timeout=30, follow_redirects=True
        ) as client:
            resp = await client.get(self.base_url)
            resp.raise_for_status()
            try:
                data = resp.json()
                return data.get("html", "")
            except json.JSONDecodeError:
                return resp.text

