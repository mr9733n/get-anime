#animedia_client.py
import asyncio
import logging

from typing import Any, Dict, List
from app.animedia.animedia_client import AnimediaClient
from app.animedia.animedia_utils import (
    parse_title_page,
    uniq,
    sort_by_episode,
    to_timestamp,
    build_base_dict,
    episodes_dict,
    extract_video_host,
    map_status, replace_spaces,
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
                max_tries = 3
                for attempt in range(1, max_tries + 1):
                    try:
                        await page.goto(url, timeout=120000, wait_until="networkidle")
                        await page.wait_for_load_state("networkidle", timeout=120000)

                        if await page.query_selector("button#accept-cookies"):
                            await page.click("button#accept-cookies")

                        await page.wait_for_selector("header.pmovie__header", timeout=120000)
                        self.logger.info(f"safe_goto url was successfully...")
                        return
                    except Exception as e:
                        if attempt == max_tries:
                            self.logger.warning(f"Не удалось загрузить {url} после {max_tries} попыток: {e}")
                            raise
                        else:
                            self.logger.info(f"Попытка {attempt} не удалась, повторяем… ({e})")
                            await asyncio.sleep(2)

            async def process_one(url: str) -> Dict[str, Any]:
                # ---------- навигация ----------
                await safe_goto(page, url)

                # ---------- парсинг ----------
                html = await page.content()
                meta = parse_title_page(html, self.client.base_url)

                # ---------- статус ----------
                sanitized_code = replace_spaces(meta.get("name_en"))
                status_obj = map_status(meta.get("status"))

                # ---------- эпизоды ----------
                raw_files = await self.client._collect_episode_files(page, url)
                unique_files = uniq(raw_files)
                stream_video_host = extract_video_host(raw_files)
                sorted_links = sort_by_episode(unique_files)

                episodes = episodes_dict(sorted_links)

                # ---------- итоговый словарь ----------
                result = build_base_dict(
                    url=url,
                    stream_video_host=stream_video_host,
                    meta=meta,
                    episodes=episodes,
                    status=status_obj,
                    sanitized_code=sanitized_code,
                )
                return result

            results = await asyncio.gather(*[process_one(u) for u in title_urls])
            self.logger.info(f"Animedia scrapping was successfully. Was found {len(results)}.")
            return results
        finally:
            await browser.close()
            await playwright.stop()
