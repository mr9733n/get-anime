# utils/animedia/animedia_adapter.py
import asyncio
import logging
from typing import List, Dict, Any

import httpx

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

    def __init__(self, base_url: str):
        self.client = AnimediaClient(base_url)
        self.logger = logging.getLogger(__name__)

    async def _process_one(self, url: str) -> Dict[str, Any]:
        # ---------- 1️⃣ Получаем HTML страницы ----------
        async with httpx.AsyncClient(headers=self.client.headers, timeout=30) as http:
            page_resp = await http.get(url)
            page_resp.raise_for_status()
            html = page_resp.text

        # ---------- 2️⃣ Парсим метаданные ----------
        meta = parse_title_page(html, self.client.base_url)

        sanitized_code = replace_spaces(meta.get("name_en"))
        sanitized_name_ru = replace_brackets(meta.get("name_ru"))
        status_obj = map_status(meta.get("status"))

        # ---------- 3️⃣ Сбор файлов эпизодов ----------
        raw_files = await self.client.collect_episode_files(html)
        # unique_files = uniq(raw_files)
        stream_video_host = extract_video_host(raw_files)

        sorted_links = dedup_and_sort(raw_files)
        # проверка на дубликаты (дубли могут появиться из‑за разных CDN)
        assert len(sorted_links) == len(set(sorted_links)), "Дубликаты в sorted_links"

        episodes = episodes_dict(sorted_links)

        # ---------- 4️⃣ Формируем итоговый словарь ----------
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
        # 1️⃣ Поиск ссылок на тайтлы
        title_urls = await self.client.search_titles(anime_name, max_titles)

        semaphore = asyncio.Semaphore(MAX_CONCURRENT)

        async def limited_process(url: str) -> Dict[str, Any]:
            async with semaphore:
                return await self._process_one(url)

        results = await asyncio.gather(*[limited_process(u) for u in title_urls])
        self.logger.info(f"Found {len(results)} titles for '{anime_name}'")
        return results