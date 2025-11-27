# animedia_client.py
import asyncio
import logging
import httpx
import requests
from typing import Any, Literal, List, Dict, Optional

from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

from animedia_utils import (
    safe_str,
    uniq,
    add_720,
    extract_file_from_html,
    urljoin,
    sort_by_episode,
    parse_title_page,
)


class AnimediaClient:
    def __init__(self, base_url: str):
        self.logger = logging.getLogger(__name__)
        self.base_url = base_url.rstrip("/")

        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/140.0.0.0 Safari/537.36 Edg/140.0.0.0"
            ),
            "Accept": "application/json",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
        }

    async def _open_browser(self):
        """Создаёт браузер Playwright, закрывается автоматически."""
        playwright = await async_playwright().start()
        browser = await playwright.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.set_extra_http_headers(self.headers)
        return playwright, browser, page

    async def _search_titles(self, page, anime_name: str, max_titles: int) -> List[str]:
        """Возвращает ссылки на карточки аниме (не более `max_titles`)."""
        search_url = f"{self.base_url}/index.php?do=search&story={anime_name}"
        await page.goto(search_url)
        await page.wait_for_selector("div.content", timeout=60000)

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
        async with httpx.AsyncClient(timeout=30) as client:
            for ep_url in episode_links:
                resp = await client.get(ep_url)
                file_url = extract_file_from_html(resp.text, ep_url)
                if file_url:
                    files.append(safe_str(file_url))
        return files


