# providers/animedia/v0/adapter.py
import asyncio
import logging
from typing import List, Dict, Any, Tuple

from providers.animedia.v0.service import AniMediaService

MAX_CONCURRENT = 3


class AniMediaAdapter:
    def __init__(self, base_url: str, client, logger: logging.Logger | None = None,):
        self.logger = logger or logging.getLogger(__name__)
        self.client = client
        self.service = AniMediaService(base_url=base_url, client=client, logger=logger)


    async def get_by_title(self, anime_name: str, max_titles: int = 5) -> List[Dict[str, Any]]:
        """ Returns data title from AniMedia for saving in DB.
            Saving local cache.
        """
        title_urls = await self.service.search_titles(anime_name, max_titles)
        semaphore = asyncio.Semaphore(MAX_CONCURRENT)

        async def limited_process(url: str) -> Dict[str, Any]:
            async with semaphore:
                return await self.service.process_one_title(url)

        results = await asyncio.gather(*[limited_process(u) for u in title_urls])
        self.logger.info(f"Found {len(results)} titles for '{anime_name}'")
        return results


    async def get_new_titles(self, max_titles: int = 60) -> List[Dict[str, Any]]:
        """ Return schedule data from AniMedia.
            Without saving in DB.
            Only local cache.
        """
        total_pages = await self.service.get_ajax_total_pages()
        semaphore = asyncio.Semaphore(MAX_CONCURRENT)

        cached = self.service.load_schedule_cache()
        if cached:
           return cached

        results: List[Dict[str, Any]] = []
        collected = 0

        first_html = await self.service.get_first_page()
        announce_titles = await self.service.parse_page_for_announce_titles(first_html, max_titles)
        if announce_titles:
            results.append({"page": 0, "titles": announce_titles})
            collected += len(announce_titles)

        async def fetch(page: int) -> Tuple[int, List[str]]:
            async with semaphore:
                remaining = max_titles - collected
                if remaining <= 0:
                    return page, []
                html = await self.service.fetch_new_titles_html(page)
                titles = await self.service.parse_page_for_new_titles(html, remaining)
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

        self.service.save_schedule_cache(results)
        return results


    async def get_all_titles(self, max_titles: int = 60, pages: int = 5) -> List[Dict[str, Any]]:
        """
        Возвращает «все» тайтлы (не только новинки) в том же формате,
        что и get_new_titles.
        """
        total_pages = await self.service.get_total_pages()
        titles_per_page = max_titles // pages

        cached = self.service.load_all_titles_cache()
        if cached:
            cached_pages = {e["page"] for e in cached}
            last_page = max(cached_pages) if cached_pages else 0
        else:
            cached = []
            last_page = 0

        collected = sum(len(e["titles"]) for e in cached)

        if collected >= max_titles:
            return cached

        start_page = (collected // titles_per_page) + 1
        end_page = min(start_page + pages - 1, total_pages)

        semaphore = asyncio.Semaphore(MAX_CONCURRENT)

        async def fetch(page: int):
            async with semaphore:
                html = await self.service.get_page_titles(page)
                remaining = max_titles - collected
                titles = await self.service.parse_all_titles_page(html, remaining)
                return {"page": page, "titles": titles}

        tasks = [fetch(p) for p in range(start_page, end_page + 1)]
        new_results = await asyncio.gather(*tasks)

        all_results = cached + [r for r in new_results if r["titles"]]
        for entry in all_results:
            entry["titles"] = self._unique_preserve_order(entry["titles"])
        all_results.sort(key=lambda x: x["page"])

        self.service.save_all_titles_cache(all_results)
        return all_results


    @staticmethod
    def _unique_preserve_order(seq: List[str]) -> List[str]:
        seen: set[str] = set()
        uniq: List[str] = []
        for item in seq:
            if item not in seen:
                seen.add(item)
                uniq.append(item)
        return uniq

