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


    async def get_all_titles(self, max_titles: int = 10) -> List[Dict[str, Any]]:
        soup = await self.client.get_new_titles()
        first_page_titles = await self.client.parse_page_for_new_titles(
            self.client.base_url, max_titles
        )
        all_results = [{"page": 1, "titles": first_page_titles}]
        collected = len(first_page_titles)

        if collected >= max_titles:
            return all_results

        page_links = self.client.extract_pagination_for_new_titles(soup)

        semaphore = asyncio.Semaphore(MAX_CONCURRENT)

        async def fetch(page_num: int, url: str) -> Tuple[int, List[str]]:
            async with semaphore:
                remaining = max_titles - collected
                if remaining <= 0:
                    return page_num, []
                titles = await self.client.parse_page_for_new_titles(url, remaining)
                return page_num, titles

        tasks = [fetch(num, url) for num, url in page_links]
        for coro in asyncio.as_completed(tasks):
            page_num, titles = await coro
            if titles:
                all_results.append({"page": page_num, "titles": titles})
                collected += len(titles)
                if collected >= max_titles:
                    break
        return all_results
