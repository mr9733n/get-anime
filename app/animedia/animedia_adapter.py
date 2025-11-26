import asyncio
import logging
import re
from typing import Any, Dict, List

from animedia_client import AnimediaClient
from animedia_utils import (
    parse_title_page,
    uniq,
    sort_by_episode,
    add_720,
)

class AnimediaAdapter:
    """Адаптер, который расширяет существующие записи новыми полями."""
    ID_OFFSET = 30_000
    ORIGINAL_ID_FIELD = "animedia_original_id"

    def __init__(self, base_url: str):
        self.client = AnimediaClient(base_url)
        self.logger = logging.getLogger(__name__)

    @staticmethod
    def _extract_id_from_url(url: str) -> int:
        try:
            last = url.rstrip("/").split("/")[-1]
            num = "".join(ch for ch in last if ch.isdigit())
            return int(num) if num else 0
        except Exception:
            return 0

    @staticmethod
    def _make_new_id(original_id: int) -> int:
        return AnimediaAdapter.ID_OFFSET + original_id

    @staticmethod
    def _episode_number(url: str) -> str:
        m = re.search(r"/(\d+)_", url)
        return m.group(1) if m else "0"

    @staticmethod
    def _split_quality(url: str) -> Dict[str, str | None]:
        hd = url
        sd = url

        return {"animedia_hls_hd": hd, "animedia_hls_sd": sd}

    async def get_by_title(self, anime_name: str, max_titles: int = 5) -> List[Dict[str, Any]]:
        playwright, browser, page = await self.client._open_browser()
        try:
            title_urls = await self.client._search_titles(page, anime_name, max_titles)

            async def safe_goto(page, url):
                try:
                    await page.goto(url, timeout=60_000)
                    await page.wait_for_load_state("networkidle", timeout=60_000)
                    await page.wait_for_selector("header.pmovie__header", timeout=60_000)
                except Exception as e:
                    self.logger.warning(f"Не удалось загрузить {url}: {e}")
                    raise
            async def process_one(url: str) -> Dict[str, Any]:
                # ------------------- навигация -------------------
                await safe_goto(page, url)


                # ------------------- парсинг --------------------
                html = await page.content()
                meta = parse_title_page(html, self.client.base_url)

                # ------------------- эпизоды --------------------
                raw_files = await self.client._collect_episode_files(page, url)
                unique_files = uniq(raw_files)
                sorted_links = sort_by_episode(unique_files)
                hd_links = [add_720(u) for u in sorted_links]
                sd_links = [u for u in sorted_links]

                # ------------------- формирование ----------------
                episodes = {
                    self._episode_number(link): self._split_quality(link)
                    for link in hd_links and sd_links
                }

                original_id = self._extract_id_from_url(url)
                new_id = self._make_new_id(original_id)

                return {
                    "id": new_id,
                    self.ORIGINAL_ID_FIELD: original_id,
                    "names": {"ru": meta.get("name_ru") or "", "en": meta.get("name_en") or ""},
                    "description": meta.get("description") or "",
                    "year": meta.get("year") or "",
                    "season": meta.get("season") or "",
                    "status": meta.get("status") or "",
                    "type": meta.get("type") or "",
                    "studio": meta.get("studio") or "",
                    "rating": meta.get("rating") or "",
                    "genres": meta.get("genres") or [],
                    "poster": meta.get("poster") or "",
                    "episode_links": episodes,
                }

            results = await asyncio.gather(*[process_one(u) for u in title_urls])
            return results
        finally:
            await browser.close()
            await playwright.stop()
