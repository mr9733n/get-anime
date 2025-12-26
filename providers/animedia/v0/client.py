# providers/animedia/v0/animedia_client.py
import json
import httpx
import asyncio
import logging

from urllib.parse import urlparse
from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup
from providers.animedia.v0.cache_manager import AniMediaCacheManager, AniMediaCacheStatus, AniMediaCacheConfig
from providers.animedia.v0.legacy_mapper import (
    safe_str,
    extract_file_from_html,
    extract_id_from_url,
    urljoin,
)


BATCH_SIZE = 30
CONCURRENCY = 8
INTER_BATCH_DELAY = 1.5
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".svg"}


class AnimediaClient:
    def __init__(self, base_url: str, net_client=None, cache: AniMediaCacheManager | None = None, cache_cfg: AniMediaCacheConfig | None = None):
        self.net_client = net_client
        self.logger = logging.getLogger(__name__)
        self.base_url = base_url.rstrip("/")
        if not self.base_url.startswith(("http://", "https://")):
            self.base_url = f"https://{self.base_url}"
        self.ajax_url = f"{self.base_url}/engine/mods/custom/ajax.php"
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
        self.cfg = cache_cfg
        self.cache = cache

        self._cache_lock = asyncio.Lock()
        # in‑memory кэш
        status, payload = self.cache.load(self.cfg.vlink_key, self.cfg.vlink_ttl)

        if status is AniMediaCacheStatus.MISSING:
            self.logger.debug("vlink‑кеш отсутствует")
            self._file_cache = {}
        elif status is AniMediaCacheStatus.EXPIRED:
            self.logger.info("vlink‑кеш просрочен – будет перезаписан при следующем запросе")
            self._file_cache = payload.get("data", {}) if isinstance(payload, dict) else {}
        else:
            self._file_cache = payload.get("data", {}) if isinstance(payload, dict) else {}

        if not isinstance(self._file_cache, dict):
            self._file_cache = {}

        status, data = self.cache.load(self.cfg.schedule_key, self.cfg.schedule_ttl)
        self._schedule_cache = data if status is not AniMediaCacheStatus.MISSING and self.cache.is_nonempty(data) else []
        if status is not AniMediaCacheStatus.MISSING and self.cache.is_nonempty(data):
            self._schedule_cache = data
        elif status is AniMediaCacheStatus.EXPIRED:
            self.logger.info("schedule‑кеш просрочен – будет сброшен")
            self.cache.invalidate_cache(self.cfg.schedule_key)
        else:
            self.logger.debug("schedule‑кеш пустой или повреждён")

    def load_schedule_cache(self) -> Optional[List[dict]]:
        """Возвращает уже загруженный в память кеш‑расписание."""
        status, data = self.cache.load(self.cfg.schedule_key, self.cfg.schedule_ttl)
        if status is AniMediaCacheStatus.VALID:
            return self._schedule_cache
        else:
            return None

    def load_vlink_cache(self, original_id: str) -> Optional[dict[str, str]]:
        """Обёртка над CacheManager.load_vlink."""
        return self.cache.load_vlink(original_id)

    def save_schedule_cache(self, data: List[dict]) -> None:
        """Сохраняет в файл и обновляет in‑memory кеш."""
        status = self.cache.save(self.cfg.schedule_key, data)
        if status is AniMediaCacheStatus.SAVED:
            self.logger.debug("schedule cache is %s", status)
        self._schedule_cache = data

    def _log_len(self, name: str, seq: list) -> None:
        self.logger.info(f"{name}: {len(seq)} item{'s' if len(seq) != 1 else ''}")

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

    async def _cache_get_or_set(
        self, key: str, value_factory: Optional[callable] = None
    ) -> Optional[str]:
        """
        Возвращает значение из кеша по `key`.
        Если его нет и передан `value_factory`, вызывается фабрика,
        полученный результат сохраняется в кеш и возвращается.
        Фабрика может быть `None` – тогда просто возвращается `None`.
        Операция защищена `self._cache_lock`.
        """
        async with self._cache_lock:
            if key in self._file_cache:
                return self._file_cache[key]

        if value_factory is None:
            return None

        new_value = await value_factory()
        if new_value is None:
            return None

        async with self._cache_lock:
            if key not in self._file_cache:
                self._file_cache[key] = new_value
        return new_value

    async def _fetch_file_from_vlnk(self, vlnk_url: str) -> Optional[str]:
        """
        Скачивает файл по vlnk‑ссылке и кэширует результат.
        Возвращает URL/путь к реальному файлу или None.
        """
        vlnk_url = self._ensure_absolute_url(vlnk_url)
        if not vlnk_url:
            return None

        if self._is_image_placeholder(vlnk_url):
            self.logger.debug(f"Skipping image placeholder: {vlnk_url}")
            return None

        async def _download() -> Optional[str]:
            """Фабрика, вызываемая только если значения нет в кеше."""
            max_tries = 5
            backoff = 1

            async with self.net_client.create_async_httpx_client(
                headers=self.headers, timeout=30, follow_redirects=True
            ) as client:
                for attempt in range(1, max_tries + 1):
                    try:
                        resp = await client.get(vlnk_url)
                        resp.raise_for_status()
                        file_url = extract_file_from_html(resp.text, vlnk_url)
                        if file_url:
                            return file_url
                        raise ValueError("file not found in response")
                    except httpx.HTTPStatusError as exc:
                        if exc.response.status_code == 429:
                            retry_after = exc.response.headers.get("Retry-After")
                            wait = (
                                float(retry_after)
                                if retry_after and retry_after.isdigit()
                                else backoff
                            )
                            self.logger.warning(
                                f"429 Too Many Requests – waiting {wait}s (attempt {attempt})"
                            )
                        elif exc.response.status_code < 500:
                            self.logger.warning(
                                f"vlnk {vlnk_url} returned {exc.response.status_code}"
                            )
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

        return await self._cache_get_or_set(vlnk_url, _download)

    async def collect_episode_files(
            self, html: str, original_id: Optional[str]
    ) -> List[str]:
        """
        Сканирует страницу, собирает ссылки и кэширует их.
        Возвращает список готовых URL‑ов (строк).
        """
        self._file_cache = {}
        try:
            soup = BeautifulSoup(html, "html.parser")
            raw_vlnks = self._extract_vlnks(soup)
            vlnk_list = [self._ensure_absolute_url(v) for v in raw_vlnks if v]

            if not vlnk_list:
                self.logger.warning("No data‑vlnk found on page")
                return []

            self.logger.info(f"Found {len(vlnk_list)} vlnk links – start fetching")
            semaphore = asyncio.Semaphore(CONCURRENCY)

            async def limited_fetch(vlnk: str) -> Optional[str]:
                """Обёртка, ограничивающая количество одновременных запросов."""
                async with semaphore:
                    return await self._fetch_file_from_vlnk(vlnk)

            results: List[str] = []

            for i in range(0, len(vlnk_list), BATCH_SIZE):
                batch = vlnk_list[i: i + BATCH_SIZE]
                self.logger.debug(
                    f"Processing batch {i // BATCH_SIZE + 1} ({len(batch)} items)"
                )

                batch = [v for v in batch if not self._is_image_placeholder(v)]
                m3u8_batch = [v for v in batch if v.startswith("https://aser.pro")]
                other_batch = [v for v in batch if not v.startswith("https://aser.pro")]

                if m3u8_batch:
                    batch_results = await asyncio.gather(
                        *(limited_fetch(v) for v in m3u8_batch), return_exceptions=False
                    )
                    results.extend(safe_str(url) for url in batch_results if url)

                for v in other_batch:
                    cached = await self._cache_get_or_set(v, lambda: asyncio.sleep(0, result=v))
                    if cached:
                        results.append(safe_str(cached))

                await asyncio.sleep(INTER_BATCH_DELAY)

            self.logger.info(f"collect_episode_files: {len(results)} files collected")

            if original_id:
                status = self.cache.save_vlink(original_id, self._file_cache)
                if status is AniMediaCacheStatus.SAVED:
                    self.logger.debug("vlink cache for id %s saved", original_id)

            return results
        except Exception as exc:  # pragma: no cover
            self.logger.error(f"Error collect_episode_files: {exc}")
            return []
        finally:
            self._file_cache = {}

    #-- New titles and announces
    async def _fetch_schedule(self, url: str, payload: dict[str, str] | None) -> str:
        async with self.net_client.create_async_httpx_client(
            headers=self.headers, timeout=30, follow_redirects=True
        ) as client:
            if payload:
                resp = await client.post(url, data=payload)
            else:
                resp = await client.get(url)
            resp.raise_for_status()
            try:
                html = resp.json().get("html", "")
            except json.JSONDecodeError:
                html = resp.text
        return html

    async def fetch_new_titles_html(self, page: int) -> str:
        """Возвращает HTML‑текст страницы `page`."""
        payload = {"name": "poslednie-serii", "cstart": str(page), "action": "getpage"}
        html = await self._fetch_schedule(self.ajax_url, payload=payload)

        return html

    async def get_new_titles(self) -> Optional[str]:
        html = await self._fetch_schedule(self.base_url, payload=None)
        return html

    def _build_titles(self, items: List[BeautifulSoup], max_titles: int) -> List[str]:
        results: List[str] = []
        separator = "\u00B7"

        for a in items[:max_titles]:
            link_tag = None
            if a.has_attr("href"):
                link_tag = urljoin(self.base_url, a["href"])

            title_id = str(extract_id_from_url(link_tag))

            title_tag = a.select_one("div.ftop-item__title")
            title = title_tag.get_text(strip=True) if title_tag else "—"

            meta_tag = a.select_one("div.ftop-item__meta")
            meta = meta_tag.get_text(strip=False) if meta_tag else "—"

            ep_tag = a.select_one("div.animseri > span")
            episode = ep_tag.get_text(strip=True) if ep_tag else None

            poster_img = a.select_one("div.ftop-item__img img")
            if poster_img and poster_img.has_attr("src"):
                poster_url = urljoin(self.base_url, poster_img["src"])
            else:
                poster_url = None

            parts = [title, meta]
            if episode:
                parts.append(f"{episode} серия")
            if title_id:
                parts.append(title_id)
            if poster_url:
                parts.append(poster_url)
            if link_tag:
                parts.append(link_tag)

            results.append(separator.join(parts))

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
