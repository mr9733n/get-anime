# service.py
from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, Iterable, Optional, Sequence, Tuple

from providers.animedia.v0.parser import AniMediaParser


class AniMediaService:
    """
    Service layer: orchestration & policies.
    - может делать сеть через api_client
    - может делать параллельность (threads)
    - может содержать правила fallback / 404 episodes / prefer-embedded

    ВАЖНО: service НЕ строит legacy-структуру. Он возвращает raw-enriched release.
    """

    def __init__(self, base_url: str, client: Any, logger: Any):
        self.logger = logger
        self.client = client
        self.parser = AniMediaParser(base_url=base_url, logger=self.logger)

    def load_schedule_cache(self):
        return self.client.load_schedule_cache()


    def load_all_titles_cache(self):
        return self.client.load_all_titles_cache()


    def save_schedule_cache(self, results):
        return self.client.save_schedule_cache(results)


    def save_all_titles_cache(self, all_results):
        return self.client.save_all_titles_cache(all_results)


    # Title data processing ----

    async def search_titles(self, anime_name, max_titles):
        return await self.client.search_titles(anime_name, max_titles)


    async def process_one_title(self, url):
        return await self.client.process_one_title(url)


    # Schedule data processing ----

    async def get_first_page(self):
        return await self.client.get_first_page()


    async def get_ajax_total_pages(self) -> int:
        return await self.client.get_ajax_total_pages()


    async def fetch_new_titles_html(self, page):
        return await self.client.fetch_new_titles_html(page)


    async def parse_page_for_announce_titles(self, first_html, max_titles):
        return await self.parser.parse_page_for_announce_titles(first_html, max_titles)


    async def parse_page_for_new_titles(self, html, remaining):
        return await self.parser.parse_page_for_new_titles(html, remaining)


    # All titles data processing ----

    async def get_total_pages(self):
        return await self.client.get_total_pages()


    async def get_page_titles(self, page):
        return await self.client.get_page_titles(page)


    async def parse_all_titles_page(self, html, remaining):
        return await self.parser.parse_all_titles_page(html, remaining)




