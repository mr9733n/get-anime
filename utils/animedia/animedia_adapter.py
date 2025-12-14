# utils/animedia/animedia_adapter.py
import asyncio
import logging
from typing import List, Dict, Any, Tuple
from utils.animedia.animedia_client import AnimediaClient
from utils.animedia.animedia_utils import (
    parse_title_page,
    uniq,
    dedup_and_sort,
    episodes_dict,
    extract_video_host,
    map_status,
    replace_spaces,
    replace_brackets,
    build_base_dict,
)

MAX_CONCURRENT = 3


class AnimediaAdapter:
    """Обёртка, которая собирает полную структуру тайтла."""

    def __init__(self, base_url: str, net_client=None):
        self.net_client = net_client
        self.logger = logging.getLogger(__name__)
        self.client = AnimediaClient(base_url, net_client)


    async def _process_one(self, url: str) -> Dict[str, Any]:
        async with self.net_client.create_async_httpx_client(headers=self.client.headers, timeout=30, follow_redirects=True) as http:
            page_resp = await http.get(url)
            page_resp.raise_for_status()
            html = page_resp.text

        meta = parse_title_page(html, self.client.base_url)
        sanitized_code = replace_spaces(meta.get("name_en"))
        sanitized_name_ru = replace_brackets(meta.get("name_ru"))
        status_obj = map_status(meta.get("status"))

        raw_files = await self.client.collect_episode_files(html)
        # unique_files = uniq(raw_files)
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

    async def get_by_title(self, anime_name: str, max_titles: int = 5) -> List[Dict[str, Any]]:
        title_urls = await self.client.search_titles(anime_name, max_titles)
        semaphore = asyncio.Semaphore(MAX_CONCURRENT)

        async def limited_process(url: str) -> Dict[str, Any]:
            async with semaphore:
                return await self._process_one(url)

        results = await asyncio.gather(*[limited_process(u) for u in title_urls])
        self.logger.info(f"Found {len(results)} titles for '{anime_name}'")
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

    async def get_all_titles(self, max_titles: int = 10) -> List[Dict[str, Any]]:
        total_pages = await self.client.get_total_pages()
        semaphore = asyncio.Semaphore(MAX_CONCURRENT)

        collected = 0
        results: List[Dict[str, Any]] = []

        first_html = await self.client.get_new_titles()  # обычный GET главной страницы
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
        return results
