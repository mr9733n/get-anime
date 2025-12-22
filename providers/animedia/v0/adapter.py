# providers/animedia/v0/adapter.py
import asyncio
import logging
from typing import List, Dict, Any, Tuple
from providers.animedia.v0.client import AnimediaClient
from providers.animedia.v0.cache_manager import AniMediaCacheStatus, AniMediaCacheManager, AniMediaCacheConfig
from providers.animedia.v0.legacy_mapper import (
    parse_title_page,
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
)

MAX_CONCURRENT = 3


class AnimediaAdapter:
    def __init__(self, base_url: str, net_client=None, cache: AniMediaCacheManager | None = None, cache_cfg: AniMediaCacheConfig | None = None):
        self.logger = logging.getLogger(__name__)
        self.net_client = net_client
        self.client = AnimediaClient(base_url, net_client, cache, cache_cfg)


    async def get_by_title(self, anime_name: str, max_titles: int = 5) -> List[Dict[str, Any]]:
        """ Returns data title from AniMedia for saving in DB.
            Saving local cache.
        """
        title_urls = await self.client.search_titles(anime_name, max_titles)
        semaphore = asyncio.Semaphore(MAX_CONCURRENT)

        async def limited_process(url: str) -> Dict[str, Any]:
            async with semaphore:
                return await self._process_one(url)

        results = await asyncio.gather(*[limited_process(u) for u in title_urls])
        self.logger.info(f"Found {len(results)} titles for '{anime_name}'")
        return results


    async def _process_one(self, url: str) -> Dict[str, Any]:
        async with self.net_client.create_async_httpx_client(headers=self.client.headers, timeout=30, follow_redirects=True) as http:
            page_resp = await http.get(url)
            page_resp.raise_for_status()
            html = page_resp.text

        meta = parse_title_page(html, self.client.base_url)
        original_id = str(extract_id_from_url(url))
        sanitized_code = replace_spaces_to_hyphen(meta.get("name_en"))
        sanitized_name_ru = replace_brackets(meta.get("name_ru"))
        status_obj = map_status(meta.get("status"))
        cached = None

        if original_id:
            cached = self.client.load_vlink_cache(original_id)
        if cached:
            self.logger.info(f"Load vlinks from cache")
            raw_files = list(cached.values())
        else:
            raw_files = await self.client.collect_episode_files(html=html, original_id=original_id)

        stream_video_host = extract_video_host(raw_files)
        sorted_links = dedup_and_sort(raw_files)
        assert len(sorted_links) == len(set(sorted_links)), "Дубликаты в sorted_links"
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


    async def get_all_titles(self, max_titles: int = 60) -> List[Dict[str, Any]]:
        """ Return schedule data from AniMedia.
            Without saving in DB.
            Only local cache.
        """
        total_pages = await self.client.get_total_pages()
        semaphore = asyncio.Semaphore(MAX_CONCURRENT)

        cached = self.client.load_schedule_cache()
        if cached:
           return cached

        results: List[Dict[str, Any]] = []
        collected = 0

        first_html = await self.client.get_new_titles()
        announce_titles = await self.client.parse_page_for_announce_titles(first_html, max_titles)
        if announce_titles:
            results.append({"page": 0, "titles": announce_titles})
            collected += len(announce_titles)

        async def fetch(page: int) -> Tuple[int, List[str]]:
            async with semaphore:
                remaining = max_titles - collected
                if remaining <= 0:
                    return page, []
                html = await self.client.fetch_new_titles_html(page)
                titles = await self.client.parse_page_for_new_titles(html, remaining)
                return page, titles

        tasks = [fetch(p) for p in range(1, total_pages + 1)]

        for coro in asyncio.as_completed(tasks):
            page, titles = await coro
            if titles:
                results.append({"page": page, "titles": titles})
                collected += len(titles)
                if collected >= max_titles:
                    break

        for entry in results:
            entry["titles"] = self._unique_preserve_order(entry["titles"])

        results.sort(key=lambda x: x["page"])

        self.client.save_schedule_cache(results)
        return results


    @staticmethod
    def _unique_preserve_order(seq: List[str]) -> List[str]:
        seen: set[str] = set()
        uniq: List[str] = []
        for item in seq:
            if item not in seen:
                seen.add(item)
                uniq.append(item)
        return uniq