#animedia_client.py
import asyncio
import logging

from typing import Any, Dict, List
from animedia_client import AnimediaClient
from animedia_utils import (
    parse_title_page,
    uniq,
    sort_by_episode,
    to_timestamp,
    build_base_dict,
    episodes_dict,
    extract_video_host,
)

class AnimediaAdapter:
    """Адаптер, который расширяет существующие записи новыми полями."""
    def __init__(self, base_url: str):
        self.client = AnimediaClient(base_url)
        self.logger = logging.getLogger(__name__)


    async def get_by_title(self, anime_name: str, max_titles: int = 5) -> List[Dict[str, Any]]:
        playwright, browser, page = await self.client._open_browser()
        try:
            title_urls = await self.client._search_titles(page, anime_name, max_titles)

            async def safe_goto(page, url):
                try:
                    await page.goto(url, timeout=60000)
                    await page.wait_for_load_state("networkidle", timeout=60000)
                    await page.wait_for_selector("header.pmovie__header", timeout=60000)
                except Exception as e:
                    self.logger.warning(f"Не удалось загрузить {url}: {e}")
                    raise

            async def process_one(url: str) -> Dict[str, Any]:
                # ---------- навигация ----------
                await safe_goto(page, url)

                # ---------- парсинг ----------
                html = await page.content()
                meta = parse_title_page(html, self.client.base_url)

                # ---------- эпизоды ----------
                raw_files = await self.client._collect_episode_files(page, url)
                unique_files = uniq(raw_files)
                sorted_links = sort_by_episode(unique_files)
                stream_video_host = extract_video_host(raw_files)
                episodes = episodes_dict(sorted_links)

                # ---------- дата создания ----------
                created_ts = to_timestamp(meta.get("updated"))

                # ---------- итоговый словарь ----------
                result = build_base_dict(
                    url=url,
                    stream_video_host=stream_video_host,
                    meta=meta,
                    episodes=episodes,
                    created_ts=created_ts,
                )
                return result

            results = await asyncio.gather(*[process_one(u) for u in title_urls])
            return results
        finally:
            await browser.close()
            await playwright.stop()
