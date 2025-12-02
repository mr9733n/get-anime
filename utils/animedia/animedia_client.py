# animedia_client.py
import logging
import httpx

from typing import Any, Literal, List, Dict, Optional, Final
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
from utils.animedia.animedia_utils import (
    safe_str,
    extract_file_from_html,
    urljoin,
)


async def block_unwanted(route, request):
    # список доменов/подстрок, которые не нужны для парсинга
    unwanted = ["googlesyndication", "adservice", "analytics", "doubleclick", "gtag"]
    if any(u in request.url for u in unwanted):
        await route.abort()  # отбрасываем запрос
    else:
        await route.continue_()  # пропускаем остальные


class AnimediaClient:
    def __init__(self, base_url: str):
        self.logger = logging.getLogger(__name__)
        self.pre: Final = "https://"
        cleaned = base_url.rstrip("/")
        self.base_url = (
            cleaned
            if cleaned.startswith(("http://", "https://"))
            else f"{self.pre}{cleaned}"
        )

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


    def _logging_length(self, result: Any) -> None:
        ln = len(result)
        if ln > 1:
            self.logger.info(f"Found {ln} items")
        else:
            self.logger.info(f"Found {ln} item")


    async def open_browser(self, headless: bool = False):
        """Создаёт браузер Playwright, закрывается автоматически."""
        try:
            playwright = await async_playwright().start()
            browser = await playwright.chromium.launch(headless=headless)
            page = await browser.new_page()
            await page.set_extra_http_headers(self.headers)
            self.logger.info(f"Playwright browser was opened.")
            return playwright, browser, page
        except Exception as e:
            self.logger.error(f"Playwright browser was not open: {e}")
            return None, None, None


    async def search_titles(self, page, anime_name: str, max_titles: int) -> List[str]:
        """Возвращает ссылки на карточки аниме (не более `max_titles`)."""
        try:
            search_url = f"{self.base_url}/index.php?do=search&story={anime_name}"
            await page.goto(search_url)
            await page.wait_for_selector("div.content", timeout=120000)

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

            self._logging_length(links[:max_titles])
            return links[:max_titles]
        except Exception as e:
            self.logger.error(f"search_titles not found titles. Error: {e}")
            return []


    async def collect_episode_files(self, page, title_url: str) -> List[str]:
        """Собирает ссылки на файлы всех эпизодов конкретного тайтла."""
        try:
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

            self._logging_length(files)
            return files
        except Exception as e:
            self.logger.error(f"collect_episode_files not found m3u8. Error: {e}")
            return []


