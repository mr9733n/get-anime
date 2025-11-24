# adapter.py
import asyncio
import logging
from typing import Any, Literal, List
import requests
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

from animedia_utils import (
    safe_str,
    uniq,
    add_720,
    extract_file_from_html,
    urljoin, sort_by_episode,
)


class AnimediaAdapter:
    def __init__(self, base_url: str):
        self.logger = logging.getLogger(__name__)
        self.base_url = base_url.rstrip("/")

    async def _open_browser(self):
        """Создаёт браузер Playwright, закрывается автоматически."""
        playwright = await async_playwright().start()
        browser = await playwright.chromium.launch(headless=False)
        page = await browser.new_page()
        return playwright, browser, page

    async def _search_titles(self, page, anime_name: str, max_titles: int) -> List[str]:
        """Возвращает ссылки на карточки аниме (не более `max_titles`)."""
        search_url = f"{self.base_url}/index.php?do=search&story={anime_name}"
        await page.goto(search_url)
        await page.wait_for_selector("div.content", timeout=5000)

        html = await page.content()
        soup = BeautifulSoup(html, "html.parser")
        content_div = soup.find("div", class_="content")
        if not content_div:
            return []

        links = []
        for poster in content_div.select(".poster"):
            a = poster.select_one("a.poster__link")
            if a and poster.select_one("div.vysser"):
                links.append(urljoin(self.base_url, a["href"]))
        return links[:max_titles]

    async def _collect_episode_files(self, page, title_url: str) -> List[str]:
        """Собирает ссылки на файлы всех эпизодов конкретного тайтла."""
        await page.goto(title_url)
        html = await page.content()
        soup = BeautifulSoup(html, "html.parser")

        episode_links = [
            urljoin(title_url, a["data-vlnk"])
            for a in soup.find_all("a", attrs={"data-vlnk": True})
        ]

        files: List[str] = []
        for ep_url in episode_links:
            resp = requests.get(ep_url, timeout=15)
            file_url = extract_file_from_html(resp.text, ep_url)
            if file_url:
                files.append(safe_str(file_url))
        return files

    async def search_anime_and_collect(
        self,
        anime_name: str,
        max_titles: int = 5,
    ) -> List[Literal[b""]]:
        """Главный публичный метод – ищет аниме и возвращает уникальные ссылки 720p."""
        playwright, browser, page = await self._open_browser()
        try:
            title_urls = await self._search_titles(page, anime_name, max_titles)

            all_files: List[str] = []
            for url in title_urls:
                all_files.extend(await self._collect_episode_files(page, url))

            unique_files = uniq(all_files)
            sorted_links = sort_by_episode(unique_files)
            return [add_720(u) for u in sorted_links]
        finally:
            await browser.close()
            await playwright.stop()

