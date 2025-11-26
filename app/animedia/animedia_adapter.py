import asyncio
import logging
import re
from typing import Any, Dict, List

from animedia_client import AnimediaClient
from animedia_utils import (
    parse_title_page,
    uniq,
    sort_by_episode,
    add_1080, add_720,
    to_timestamp,
    extract_video_host,
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
        fhd = url
        hd = url
        sd = url

        return {"fhd_animedia": fhd, "hd_animedia": hd, "sd_animedia": sd}

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
                # … (парсинг, сбор raw_files и т.д.) …
                # ------------------- навигация -------------------
                await safe_goto(page, url)


                # ------------------- парсинг --------------------
                html = await page.content()
                meta = parse_title_page(html, self.client.base_url)

                # ------------------- эпизоды --------------------
                raw_files = await self.client._collect_episode_files(page, url)
                self.stream_video_host = extract_video_host(raw_files)
                unique_files = uniq(raw_files)
                sorted_links = sort_by_episode(unique_files)
                original_id = self._extract_id_from_url(url)
                new_id = self._make_new_id(original_id)

                # 1️⃣ Формируем ссылки для каждой серии
                fhd_links = [add_1080(u) for u in sorted_links] # 1080p if exist
                hd_links = [add_720(u) for u in sorted_links]  # 720p‑версия
                sd_links = sorted_links  # оригинальная 480p‑версия

                episodes: Dict[str, Dict[str, str | None]] = {}
                for fhd, hd, sd in zip(fhd_links, hd_links, sd_links):
                    ep_num = self._episode_number(hd)

                    # базовые ссылки
                    base = self._split_quality(hd)  # {'animedia_hls_hd': hd, 'animedia_hls_sd': sd}
                    # добавляем пусто – потому что может быть заполнено из апи
                    base.update({
                        "fhd": "",
                        "hd": "",
                        "sd": "",
                    })
                    # добавляем новые поля
                    episodes[ep_num] = base

                # 2️⃣ Дата создания эпизода – берём из meta['updated'] (если есть)
                created_ts = to_timestamp(meta.get("updated"))

                # 3️⃣ Собираем окончательный словарь
                result = {
                    "id": new_id,
                    self.ORIGINAL_ID_FIELD: original_id,
                    "code": meta.get("code", ""),
                    "announce": meta.get("announce", ""),
                    "names": {
                        "ru": meta.get("name_ru") or "",
                        "en": meta.get("name_en") or "",
                        "alternative": meta.get("name_alternative") or ""
                    },
                    "description": meta.get("description") or "",
                    "year": meta.get("year") or "",
                    "season": {
                        "code": 0,
                        "string": meta.get("season") or "",
                        "year": meta.get("year") or "",
                        "week_day": meta.get("week_day") or ""
                    },
                    "status": {
                        "code": meta.get("status_code", 0),
                        "string": meta.get("status") or ""
                    },
                    "type": {
                        "code": 0,
                        "string": meta.get("type") or "",
                        "full_string": meta.get("type_full") or "",
                        "episodes": meta.get("episodes_total") or 0,
                        "length": str(meta.get("average_duration_of_episode", ""))
                    },
                    "studio": meta.get("studio") or "",
                    "rating": meta.get("rating") or "",
                    "genres": meta.get("genres") or [],
                    "posters": {
                        "small": {"url": meta.get("poster_small") or ""},
                        "medium": {"url": meta.get("poster_medium") or ""},
                        "original": {"url": meta.get("poster") or ""}
                    },
                    "updated": to_timestamp(meta.get("updated")),
                    "last_change": to_timestamp(meta.get("updated")),
                    "in_favorites": meta.get("in_favorites", 0),
                    "blocked": {
                        "copyrights": False,
                        "geoip": False,
                        "geoip_list": []
                    },
                    "player": {
                        "host": self.stream_video_host,
                        "alternative_player": "",
                        "list": episodes
                    },
                    "team": {
                        "voice": [],
                        "translator": [],
                        "timing": []
                    },
                    "franchises": [],
                    "torrents": {"list": []},
                    "episode_links": episodes,  # совместимый алиас
                    "created_timestamp": created_ts  # если нужен глобальный таймстамп
                }
                return result

            results = await asyncio.gather(*[process_one(u) for u in title_urls])
            return results
        finally:
            await browser.close()
            await playwright.stop()
