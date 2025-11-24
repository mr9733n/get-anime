import asyncio, re, json
from urllib.parse import urljoin, urlparse, urlunparse
from typing import Iterable, Union, Literal, Any, Coroutine
import logging
import requests
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright


class AnimediaAdapter:
    def __init__(self, base_url: str, title_name: str):
        self.logger = logging.getLogger(__name__)
        self.base_url = base_url
        self.title_name = title_name

    def safe_str(self, value: bytes | str) -> str:
        return value.decode('utf-8') if isinstance(value, (bytes, bytearray)) else value


    def uniq(self, seq: Iterable[Union[str, bytes]]) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for x in seq:
            s = self.safe_str(x)
            if s not in seen:
                seen.add(s)
                out.append(s)
        return out

    def sort_by_episode(self, urls: list[str]) -> list[str]:
        def _key(u: str) -> int:
            m = re.search(r"/(\d+)_", u)
            return int(m.group(1)) if m else 0
        return sorted(urls, key=_key)

    def add_720(self, url: str) -> Literal[b""]:
        p = urlparse(url)
        parts = p.path.split('/')
        try:
            idx = parts.index('hls')
            if idx + 1 < len(parts) and parts[idx + 1] != '720':
                parts.insert(idx + 1, '720')
        except ValueError:
            if len(parts) > 1:
                parts.insert(-1, '720')
        new_path = '/' + '/'.join(filter(None, parts))
        return urlunparse(p._replace(path=new_path))

    def extract_file_from_html(self, html: str, base_url: str) -> str | None:
        soup = BeautifulSoup(html, "html.parser")
        for script in soup.find_all("script"):
            txt = script.string or script.get_text()
            m = re.search(r'file\s*[:=]\s*["\']([^"\']+)["\']', txt)
            if m:
                return urljoin(base_url, m.group(1))
        return None

    async def search_anime_and_collect(
        self,
        anime_name: str,
        base_url: str,
        max_titles: int = 5,
    ) -> list[Any] | list[Literal[b""]]:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
            page = await browser.new_page()

            await page.goto(base_url)
            search_url = f"{base_url.rstrip('/')}/index.php?do=search&story={anime_name}"
            await page.goto(search_url)

            await page.wait_for_selector('div.content', timeout=5000)

            html = await page.content()
            soup = BeautifulSoup(html, "html.parser")
            content_div = soup.find('div', class_='content')
            if not content_div:
                await browser.close()
                return []

            title_links = []
            for poster in content_div.select('.poster'):
                link_tag = poster.select_one('a.poster__link')
                if not link_tag:
                    continue
                if poster.select_one('div.vysser'):
                    title_links.append(urljoin(base_url, link_tag['href']))

            title_links = title_links[:max_titles]

            all_files: list[str] = []

            for title_url in title_links:
                await page.goto(title_url)
                title_html = await page.content()
                title_soup = BeautifulSoup(title_html, "html.parser")

                episode_links = [
                    urljoin(title_url, a['data-vlnk'])
                    for a in title_soup.find_all('a', attrs={'data-vlnk': True})
                ]

                for ep_url in episode_links:
                    resp = requests.get(ep_url, timeout=15)
                    file_url = self.extract_file_from_html(resp.text, ep_url)
                    if file_url:
                        all_files.append(self.safe_str(file_url))

            await browser.close()

            unique_files = self.uniq(all_files)
            final_files = [self.add_720(u) for u in unique_files]
            return final_files


if __name__ == "__main__":

    animedia_adapter = AnimediaAdapter()
    anime = "Sanda"
    start = ""

    files = asyncio.run(animedia_adapter.search_anime_and_collect(anime, start))
    files = animedia_adapter.uniq(files)
    files = [animedia_adapter.add_720(u) for u in files]
    sorted_links = animedia_adapter.sort_by_episode(files)

    print("Найденные ссылки (уникальные, 720p):")
    for f in sorted_links:
        print(f)
