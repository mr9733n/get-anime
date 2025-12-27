# providers/animedia/v0/repository.py
import logging
from typing import Optional, Any

from .cache_manager import AniMediaCacheManager, AniMediaCacheConfig, AniMediaCacheStatus
from .client import AniMediaHttpClient
from .parser import AniMediaParser
from .models import Title, Episode, TitleStatus
from .legacy_mapper import (
    extract_id_from_url,
    extract_video_host,
    dedup_and_sort,
    dedup_urls,
)


class AniMediaRepository:
    """
    Data access layer: cache-aside pattern.
    Отвечает за: получить данные (из кэша или сети) + распарсить.
    НЕ отвечает за: concurrency, business policies.
    """

    def __init__(
            self,
            http_client: AniMediaHttpClient,
            cache: AniMediaCacheManager,
            parser: AniMediaParser,
            cache_cfg: AniMediaCacheConfig,
            logger: logging.Logger | None = None,
    ):
        self._http = http_client
        self._cache = cache
        self._parser = parser
        self._cfg = cache_cfg
        self._logger = logger or logging.getLogger(__name__)

    # ══════════════════════════════════════════════════════════
    # Title operations
    # ══════════════════════════════════════════════════════════

    async def search_title_urls(self, query: str, limit: int = 5) -> list[str]:
        """Поиск URL'ов тайтлов по названию."""
        html = await self._http.get_search_page(query)
        urls = self._parser.parse_poster_links(html)
        self._logger.info(f"search_title_urls: found {len(urls[:limit])} URLs")
        return urls[:limit]

    async def fetch_title(self, url: str) -> Title:
        """Получить полные данные тайтла."""
        html = await self._http.get_page(url)
        meta = self._parser.parse_title_page(html, self._http.base_url)

        original_id = self._extract_id(url)
        episodes, video_host = await self._fetch_episodes(html, original_id)

        return self._build_title(url, meta, episodes, video_host)

    async def _fetch_episodes(
            self, html: str, original_id: str
    ) -> tuple[list[Episode], str]:
        """Получить эпизоды: сначала кэш, потом сеть."""
        # Try cache
        cached = self._cache.load_vlink(original_id)
        if cached:
            self._logger.info(f"Episodes loaded from cache for {original_id}")
            file_urls = list(cached.values())
        else:
            # Fetch from network
            vlnk_urls = self._parser.parse_episode_files(html)
            if not vlnk_urls:
                self._logger.warning("No vlnk URLs found on page")
                return [], ""

            file_urls = await self._http.resolve_vlnks(vlnk_urls)

            # Save to cache
            if file_urls and original_id:
                cache_dict = {v: f for v, f in zip(vlnk_urls, file_urls) if f}
                self._cache.save_vlink(original_id, cache_dict)

        video_host = extract_video_host(file_urls)
        episodes = self._build_episodes(file_urls)
        return episodes, video_host

    def _build_episodes(self, file_urls: list[str]) -> list[Episode]:
        """Построить список Episode из URL'ов файлов."""
        # Сортировка и дедупликация
        m3u8_links = [u for u in file_urls if u.endswith(".m3u8")]
        other_links = [u for u in file_urls if not u.endswith(".m3u8")]

        sorted_m3u8 = dedup_and_sort(m3u8_links) if m3u8_links else []
        other_links = dedup_urls(other_links)
        sorted_links = sorted_m3u8 + other_links

        episodes = []
        for idx, link in enumerate(sorted_links, start=1):
            ep = Episode(
                number=idx,
                name=f"Серия {idx}",
            )
            if link.endswith(".m3u8"):
                ep.hls_sd = self._strip_host(link)
                ep.hls_hd = self._strip_host(self._add_720(link))
            else:
                ep.hls_fhd = link
            episodes.append(ep)

        return episodes

    # ══════════════════════════════════════════════════════════
    # Schedule operations
    # ══════════════════════════════════════════════════════════

    async def fetch_first_page(self) -> str:
        """Raw HTML главной страницы."""
        return await self._http.get_page(self._http.base_url)

    async def fetch_schedule_page(self, page: int) -> str:
        """Raw HTML страницы расписания через AJAX."""
        return await self._http.get_ajax_page(page)

    async def get_total_ajax_pages(self) -> int:
        """Количество страниц в AJAX-пагинации."""
        html = await self.fetch_schedule_page(1)
        pages = self._parser.parse_ajax_total_pages(html)
        return max(pages) if pages else 1

    async def parse_announce_titles(self, html: str, max_titles: int) -> list[str]:
        """Парсинг анонсов с главной страницы."""
        return await self._parser.parse_page_for_announce_titles(html, max_titles)

    async def parse_new_titles(self, html: str, max_titles: int) -> list[str]:
        """Парсинг новых тайтлов со страницы расписания."""
        return await self._parser.parse_page_for_new_titles(html, max_titles)

    def load_schedule_cache(self) -> Optional[list[dict]]:
        """Загрузить расписание из кэша."""
        status, data = self._cache.load(self._cfg.schedule_key, self._cfg.schedule_ttl)
        if status == AniMediaCacheStatus.VALID and self._cache.is_nonempty(data):
            return data
        if status == AniMediaCacheStatus.EXPIRED:
            self._logger.info("Schedule cache expired — will be refreshed")
            self._cache.invalidate_cache(self._cfg.schedule_key)
        return None

    def save_schedule_cache(self, data: list[dict]) -> None:
        """Сохранить расписание в кэш."""
        status = self._cache.save(self._cfg.schedule_key, data)
        if status == AniMediaCacheStatus.SAVED:
            self._logger.debug("Schedule cache saved")

    # ══════════════════════════════════════════════════════════
    # All titles operations
    # ══════════════════════════════════════════════════════════

    async def fetch_catalog_page(self, page: int) -> str:
        """Raw HTML страницы каталога."""
        return await self._http.get_catalog_page(page)

    async def get_total_catalog_pages(self) -> int:
        """Количество страниц в каталоге."""
        html = await self.fetch_catalog_page(1)
        pages = self._parser.parse_total_pages(html)
        return max(pages) if pages else 1

    async def parse_catalog_titles(self, html: str, max_titles: int) -> list[str]:
        """Парсинг тайтлов со страницы каталога."""
        return await self._parser.parse_all_titles_page(html, max_titles)

    def load_all_titles_cache(self) -> Optional[list[dict]]:
        """Загрузить каталог из кэша."""
        status, data = self._cache.load(
            self._cfg.all_titles_key, self._cfg.all_titles_ttl
        )
        if status == AniMediaCacheStatus.VALID and self._cache.is_nonempty(data):
            return data
        if status == AniMediaCacheStatus.EXPIRED:
            self._logger.info("All titles cache expired — will be refreshed")
            self._cache.invalidate_cache(self._cfg.all_titles_key)
        return None

    def save_all_titles_cache(self, data: list[dict]) -> None:
        """Сохранить каталог в кэш."""
        status = self._cache.save(self._cfg.all_titles_key, data)
        if status == AniMediaCacheStatus.SAVED:
            self._logger.debug("All titles cache saved")

    def get_cached_all_titles_stats(self) -> tuple[int, int]:
        """
        Получить статистику кэшированного каталога.
        Returns: (collected_count, last_page)
        """
        cached = self.load_all_titles_cache()
        if not cached:
            return 0, 0

        collected = sum(len(e.get("titles", [])) for e in cached)
        last_page = max((e.get("page", 0) for e in cached), default=0)
        return collected, last_page

    # ══════════════════════════════════════════════════════════
    # Private helpers
    # ══════════════════════════════════════════════════════════

    @staticmethod
    def _extract_id(url: str) -> str:
        return str(extract_id_from_url(url))

    @staticmethod
    def _strip_host(url: str) -> str:
        """Убрать scheme и host, оставить только path."""
        from urllib.parse import urlparse
        parsed = urlparse(url)
        path = parsed.path
        return path if path.startswith("/") else f"/{path}"

    @staticmethod
    def _add_720(url: str) -> str:
        """Вставить качество 720 в URL."""
        from urllib.parse import urlparse, urlunparse
        parsed = urlparse(url)
        parts = parsed.path.split("/")
        try:
            idx = parts.index("hls")
            if idx + 1 < len(parts) and parts[idx + 1] != "720":
                parts.insert(idx + 1, "720")
        except ValueError:
            if len(parts) > 1:
                parts.insert(-1, "720")
        new_path = "/" + "/".join(filter(None, parts))
        return urlunparse(parsed._replace(path=new_path))

    def _build_title(
            self,
            url: str,
            meta: dict[str, Any],
            episodes: list[Episode],
            video_host: str,
    ) -> Title:
        """Собрать domain model Title из распарсенных данных."""
        status_str = meta.get("status", "")
        status_map = {
            "завершён": TitleStatus.FINISHED,
            "в работе": TitleStatus.ONGOING,
            "анонс": TitleStatus.ANNOUNCED,
        }
        status = status_map.get(status_str.lower(), TitleStatus.FINISHED)

        return Title(
            external_id=int(self._extract_id(url)) or 0,
            name_ru=meta.get("name_ru") or "",
            name_en=meta.get("name_en") or "",
            name_alt=meta.get("alternative") or "",
            description=meta.get("description") or "",
            poster_url=meta.get("poster") or "",
            status=status,
            year=meta.get("year") or 0,
            season=meta.get("season") or "",
            genres=meta.get("genres") or [],
            episodes=episodes,
            studio=meta.get("studio") or "",
            rating=meta.get("rating") or 0.0,
            video_host=video_host,
            updated_timestamp=meta.get("updated") or 0,
            # Дополнительные поля из meta
            type_string=meta.get("type") or "",
            type_full=meta.get("type_full") or "",
            episodes_count=meta.get("episodes") or 0,
            episode_length=meta.get("length"),
        )