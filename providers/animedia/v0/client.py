# providers/animedia/v0/animedia_client.py
import json
import httpx
import asyncio
import logging

from urllib.parse import urlparse
from typing import List, Dict, Any, Optional, Callable, Awaitable, TypeVar
from providers.animedia.v0.cache_manager import AniMediaCacheManager, AniMediaCacheStatus, AniMediaCacheConfig
from providers.animedia.v0.legacy_mapper import (
    uniq,
    dedup_and_sort,
    episodes_dict,
    extract_video_host,
    map_status,
    replace_spaces_to_hyphen,
    replace_spaces_to_underline,
    replace_brackets,
    build_base_dict,
    extract_id_from_url,
    dedup_urls,
    safe_str,
    urljoin,
)
from providers.animedia.v0.parser import AniMediaParser
from providers.animedia.v0.retry_manager import retry_async
from providers.animedia.v0.transport import HttpxTransport

BATCH_SIZE = 30
CONCURRENCY = 8
INTER_BATCH_DELAY = 1.5
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".svg"}


class AniMediaClient:
    def __init__(self, base_url: str, net_client=None, cache: AniMediaCacheManager | None = None, cache_cfg: AniMediaCacheConfig | None = None,logger: logging.Logger | None = None,):
        self.net_client = net_client
        self.logger = logger or logging.getLogger(__name__)
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
        self.timeout = 30
        self.follow_redirects = True
        # Transport
        self.transport = HttpxTransport(
            net_client=net_client,
            headers=self.headers,
            timeout=self.timeout,
            follow_redirects=self.follow_redirects,
            logger=logger,
        )

        # Parser
        self.parser = AniMediaParser(base_url=base_url, logger=self.logger)

        # Cache
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

        status, data = self.cache.load(self.cfg.all_titles_key, self.cfg.all_titles_ttl)
        self._all_titles_cache = data if status is not AniMediaCacheStatus.MISSING and self.cache.is_nonempty(data) else []
        if status is not AniMediaCacheStatus.MISSING and self.cache.is_nonempty(data):
            self._all_titles_cache = data
        elif status is AniMediaCacheStatus.EXPIRED:
            self.logger.info("schedule‑кеш просрочен – будет сброшен")
            self.cache.invalidate_cache(self.cfg.all_titles_key)
        else:
            self.logger.debug("schedule‑кеш пустой или повреждён")

    def load_schedule_cache(self) -> Optional[List[dict]]:
        """Возвращает уже загруженный в память кеш schedule."""
        status, data = self.cache.load(self.cfg.schedule_key, self.cfg.schedule_ttl)
        if status is AniMediaCacheStatus.VALID:
            return self._schedule_cache
        else:
            return None

    def load_all_titles_cache(self) -> Optional[List[dict]]:
        """Возвращает уже загруженный в память кеш all_titles."""
        status, data = self.cache.load(self.cfg.all_titles_key, self.cfg.all_titles_ttl)
        if status is AniMediaCacheStatus.VALID:
            return self._all_titles_cache
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

    def save_all_titles_cache(self, data: List[dict]) -> None:
        """Сохраняет в файл и обновляет in‑memory кеш."""
        status = self.cache.save(self.cfg.all_titles_key, data)
        if status is AniMediaCacheStatus.SAVED:
            self.logger.debug("schedule cache is %s", status)
        self._all_titles_cache = data

    def _log_len(self, name: str, seq: list) -> None:
        self.logger.info(f"{name}: {len(seq)} item{'s' if len(seq) != 1 else ''}")

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

    async def search_titles(self, anime_name: str, max_titles: int = 5) -> List[str]:
        url = f"{self.base_url}/index.php?do=search&story={anime_name}"

        resp = await self.transport.get(url)
        links = self.parser.parse_poster_links(resp)
        self._log_len("search_titles", links[:max_titles])
        return links[:max_titles]

    async def process_one_title(self, url: str) -> Dict[str, Any]:
        page_resp = await self.transport.get(url)
        html = page_resp

        meta = self.parser.parse_title_page(html, self.base_url)
        original_id = str(extract_id_from_url(url))
        sanitized_code = replace_spaces_to_hyphen(meta.get("name_en"))
        sanitized_name_ru = replace_brackets(meta.get("name_ru"))
        status_obj = map_status(meta.get("status"))
        cached = None

        if original_id:
            cached = self.load_vlink_cache(original_id)
        if cached:
            self.logger.info(f"Load vlinks from cache")
            raw_files = list(cached.values())
        else:
            raw_files = await self.collect_episode_files(html=html, original_id=original_id)

        stream_video_host = extract_video_host(raw_files)

        m3u8_links: List[str] = [lnk for lnk in raw_files if lnk.endswith(".m3u8")]
        other_links: List[str] = [lnk for lnk in raw_files if not lnk.endswith(".m3u8")]

        sorted_m3u8 = dedup_and_sort(m3u8_links) if m3u8_links else []
        other_links = dedup_urls(other_links)

        sorted_links = sorted_m3u8 + other_links

        episodes = episodes_dict(sorted_links)

        return build_base_dict(
            url=url,
            stream_video_host=stream_video_host,
            meta=meta,
            episodes=episodes,
            status=status_obj,
            sanitized_code=sanitized_code,
            sanitized_name_ru=sanitized_name_ru,
        )

    @retry_async(max_tries=5, base_delay=2.0)
    async def _download_vlnk(self, vlnk_url: str) -> Optional[str]:
        """
        Непосредственно скачивает файл по vlnk‑ссылке.
        Выделен в отдельный метод, чтобы декоратор `retry_async`
        мог его обернуть.
        """
        resp = await self.transport.get(vlnk_url)
        file_url = self.parser.extract_file_from_html(resp, vlnk_url)
        if not file_url:
            raise ValueError("file not found in response")
        return file_url

    def _ensure_absolute_url(self, url: str) -> Optional[str]:
        parsed = urlparse(url)
        if parsed.scheme in ("http", "https"):
            return url
        if url.startswith("/"):
            return urljoin(self.base_url, url)
        self.logger.warning(f"Invalid vlnk URL, skipping: {url!r}")
        return None

    @staticmethod
    def _is_image_placeholder(url: str) -> bool:
        """
        Возвращает True, если URL выглядит как ссылка на изображение.
        """
        parsed = urlparse(url)
        path = parsed.path.lower()
        return any(path.endswith(ext) for ext in IMAGE_EXTS)

    async def _fetch_file_from_vlnk(self, vlnk_url: str) -> Optional[str]:
        """
        Обёртка над кэшем + защищённый загрузчик.
        """
        vlnk_url = self._ensure_absolute_url(vlnk_url)
        if not vlnk_url or self._is_image_placeholder(vlnk_url):
            return None

        # кэш‑логика без изменений
        return await self._cache_get_or_set(vlnk_url, lambda: self._download_vlnk(vlnk_url))

    async def collect_episode_files(
            self, html: str, original_id: Optional[str]
    ) -> List[str]:
        """
        Сканирует страницу, собирает ссылки и кэширует их.
        Возвращает список готовых URL‑ов (строк).
        """
        self._file_cache = {}
        try:
            raw_vlnks = self.parser.parse_episode_files(html)
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
    @retry_async(max_tries=5, base_delay=2.0)
    async def _fetch_page(self, url: str, payload: dict[str, str] | None) -> str:
        if payload:
            resp = await self.transport.post(url, data=payload)
        else:
            resp = await self.transport.get(url)
        try:
            html = resp
        except json.JSONDecodeError:
            html = resp
        return html

    async def get_first_page(self) -> Optional[str]:
        html = await self._fetch_page(self.base_url, payload=None)
        return html

    async def fetch_new_titles_html(self, page: int) -> str:
        """Возвращает HTML‑текст страницы `page`."""
        payload = {"name": "poslednie-serii", "cstart": str(page), "action": "getpage"}
        html = await self._fetch_page(self.ajax_url, payload=payload)
        return html

    async def get_ajax_total_pages(self) -> int:
        """Определяет количество страниц, используя первую страницу."""
        first_html = await self.fetch_new_titles_html(1)
        pages = self.parser.parse_ajax_total_pages(first_html)
        return max(pages) if pages else 1

    # All titles
    async def get_total_pages(self) -> int:
        """Определяет количество страниц, используя первую страницу."""
        first_html = await self.get_page_titles(1)
        pages = self.parser.parse_total_pages(first_html)
        return max(pages) if pages else 1

    async def get_page_titles(self, page: int) -> str:
        """
        Страницы «всех» тайтлов находятся по шаблону
        https://amd.online/page/<n>/ .
        Для первой страницы (page==1) можно использовать base_url без /page/1/.
        """
        if page == 1:
            url = self.base_url  # главная страница уже содержит список
        else:
            url = f"{self.base_url}/page/{page}/"
        html = await self._fetch_page(url, payload=None)
        return html

