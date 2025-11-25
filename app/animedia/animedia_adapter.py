# animedia_adapter.py
import asyncio
import logging
import re
from typing import Any, Dict, List

from animedia_client import AnimediaClient
from animedia_utils import parse_title_page


class AnimediaAdapter:
    """
    Адаптер, который **расширяет** существующие записи новыми полями
    (animedia_*), но не меняет уже сохранённые данные.
    """

    ID_OFFSET = 30_000          # диапазон новых ID
    ORIGINAL_ID_FIELD = "animedia_original_id"

    def __init__(self, base_url: str):
        self.client = AnimediaClient(base_url)
        self.logger = logging.getLogger(__name__)

    # -----------------------------------------------------------------
    # Внутренние утилиты
    # -----------------------------------------------------------------
    @staticmethod
    def _extract_id_from_url(url: str) -> int:
        """
        Возвращает числовой ID, который находится в конце URL.
        Пример: https://site.com/anime/12345‑yano‑kun → 12345
        """
        try:
            last = url.rstrip("/").split("/")[-1]
            num = "".join(ch for ch in last if ch.isdigit())
            return int(num) if num else 0
        except Exception:
            return 0

    @staticmethod
    def _make_new_id(original_id: int) -> int:
        """Генерирует новый ID, добавляя фиксированный офсет."""
        return AnimediaAdapter.ID_OFFSET + original_id

    @staticmethod
    def _episode_number(url: str) -> str:
        """Извлекает номер эпизода из пути /<num>_/."""
        m = re.search(r"/(\d+)_", url)
        return m.group(1) if m else "0"

    @staticmethod
    def _split_quality(url: str) -> Dict[str, str | None]:
        """
        Делит URL‑файла на HD (720) и SD (480) варианты.
        В оригинальном списке могут быть оба, один или ни одного.
        """
        # 720p уже гарантировано в `add_720`, 480p – ищем «480» в пути
        hd = url
        sd = None
        if "/480_" in url:
            sd = url.replace("/720_", "/480_")
        return {"animedia_hls_hd": hd, "animedia_hls_sd": sd}

    # -----------------------------------------------------------------
    # Публичный метод
    # -----------------------------------------------------------------
    async def get_by_title(self, anime_name: str, max_titles: int = 5) -> List[Dict[str, Any]]:
        """
        Возвращает список словарей, готовых к сохранению.
        Формат полностью совместим со старым процессором, но
        добавлены новые поля с префиксом ``animedia_``.
        """
        page = await self.client._open_browser()
        try:
            title_urls = await self.client._search_titles(page, anime_name, max_titles)

            results: List[Dict[str, Any]] = []
            for url in title_urls:
                # 1️⃣ HTML‑страница уже загружена в браузер
                html = await page.content()
                meta = parse_title_page(html, self.client.base_url)

                # 2️⃣ Сбор файлов‑эпизодов
                raw_files = await self.client._collect_episode_files(page, url)
                unique_files = self.client.uniq(raw_files)
                sorted_links = self.client.sort_by_episode(unique_files)
                hd_links = [self.client.add_720(u) for u in sorted_links]

                # 3️⃣ Формируем структуру эпизодов
                episodes: Dict[str, Dict[str, Any]] = {}
                for link in hd_links:
                    ep_num = self._episode_number(link)
                    episodes[ep_num] = self._split_quality(link)

                # 4️⃣ Формируем итоговый словарь
                original_id = self._extract_id_from_url(url)
                new_id = self._make_new_id(original_id)

                results.append(
                    {
                        "id": new_id,                                 # новый уникальный ID
                        self.ORIGINAL_ID_FIELD: original_id,          # сохраняем оригинальный ID
                        "names": {
                            "ru": meta.get("name_ru") or "",
                            "en": meta.get("name_en") or "",
                        },
                        "description": meta.get("description") or "",
                        "year": meta.get("year") or "",
                        "season": meta.get("season") or "",
                        "status": meta.get("status") or "",
                        "type": meta.get("type") or "",
                        "studio": meta.get("studio") or "",
                        "rating": meta.get("rating") or "",
                        "genres": meta.get("genres") or [],
                        "poster": meta.get("poster") or "",
                        # эпизоды – словарь { "1": {"animedia_hls_hd": "...", "animedia_hls_sd": "..."} }
                        "episode_links": episodes,
                    }
                )
            return results
        finally:
            await page.context.close()
