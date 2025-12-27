# providers/animedia/v0/parser.py
import re
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Callable, Awaitable, TypeVar
from bs4 import BeautifulSoup

from providers.animedia.v0.legacy_mapper import (
    extract_id_from_url,
    urljoin,
)

class AniMediaParser:
    def __init__(self, base_url: str, logger: logging.Logger | None = None,):
        self.logger = logger or logging.getLogger(__name__)
        self.base_url = base_url

    # full title data
    def parse_poster_links(self, html):
        soup = BeautifulSoup(html, "html.parser")
        container = soup.find("div", class_="content")
        if not container:
            return []

        links = [
            urljoin(self.base_url, a["href"])
            for a in container.select("a.poster__link")
        ]
        return links

    @staticmethod
    def _extract_vlnks(soup: BeautifulSoup) -> List[str]:
        raw = [tag["data-vlnk"] for tag in soup.find_all("a", attrs={"data-vlnk": True})]
        return raw

    def parse_episode_files(self, html):
        soup = BeautifulSoup(html, "html.parser")
        raw_vlnks = self._extract_vlnks(soup)

        if not raw_vlnks:
            self.logger.warning("No raw_vlnks found on page")
            return []

        return raw_vlnks

    @staticmethod
    def extract_file_from_html(html: str, base_url: str) -> Optional[str]:
        """Ищет в HTML строку `file = "..."` и возвращает абсолютный URL."""
        soup = BeautifulSoup(html, "html.parser")
        for script in soup.find_all("script"):
            txt = script.string or script.get_text()
            m = re.search(r'file\s*[:=]\s*["\']([^"\']+)["\']', txt)
            if m:
                return urljoin(base_url, m.group(1))
        return None

    def _build_new_titles(self, items: List[BeautifulSoup], max_titles: int) -> List[str]:
        results: List[str] = []
        separator = "\u00B7"

        for a in items[:max_titles]:
            link_tag = None
            if a.has_attr("href"):
                link_tag = urljoin(self.base_url, a["href"])

            title_id = str(extract_id_from_url(link_tag))

            title_tag = a.select_one("div.ftop-item__title")
            title = title_tag.get_text(strip=True) if title_tag else "—"

            meta_tag = a.select_one("div.ftop-item__meta")
            meta = meta_tag.get_text(strip=False) if meta_tag else "—"

            ep_tag = a.select_one("div.animseri > span")
            episode = ep_tag.get_text(strip=True) if ep_tag else None

            poster_img = a.select_one("div.ftop-item__img img")
            if poster_img and poster_img.has_attr("src"):
                poster_url = urljoin(self.base_url, poster_img["src"])
            else:
                poster_url = None

            parts = [title, meta]
            if episode:
                parts.append(f"{episode} серия")
            if title_id:
                parts.append(title_id)
            if poster_url:
                parts.append(poster_url)
            if link_tag:
                parts.append(link_tag)

            results.append(separator.join(parts))

        return results

    @staticmethod
    def _parse_type_info(soup) -> dict:
        """
        Извлекает:
        - full_string  → «ТВ (12 эп.), 24 мин.»
        - episodes → 12
        - lenght → 24
        """
        result = {
            "type_full": None,
            "episodes": 0,
            "length": None,
        }

        # <div class="spanser"><span>9</span> <i>из</i> 12+</div>
        spanser = soup.select_one("div.spanser")
        if spanser:
            txt = spanser.get_text(separator=" ", strip=True)
            m = re.search(r"из\s+(\d+)\+?", txt)
            total = int(m.group(1)) if m else 0
            result["episodes"] = total
            result["type_full"] = f"ТВ ({total} эп.)"

        # Длительность эпизода – не отдается
        # lenght = int(0)
        # result["lenght"] = lenght
        # result["type_full"] += f", {lenght} мин."
        return result

    @staticmethod
    def _text_or_none(tag) -> Optional[str]:
        return tag.get_text(strip=True) if tag else None

    @staticmethod
    def _parse_season_and_updated(li_tag) -> tuple[Optional[str], int]:
        """
        Принимает <li>‑элемент «Сезон года: …», возвращает:
        - season_name – только название сезона в нижнем регистре,
        - updated_ts – timestamp даты выхода (если есть).
        """
        if not li_tag:
            return None, 0

        season_a = li_tag.select_one("a")
        season_full = season_a.get_text(strip=True) if season_a else ""
        season_name = season_full.split()[0].lower() if season_full else None

        # пример: "Осень 2025, выходит с 2 октября 2025"
        raw = li_tag.get_text(separator=" ", strip=True)
        m = re.search(r"выходит с\s+(\d{1,2}\s+\w+\s+\d{4})", raw, re.IGNORECASE)
        if not m:
            return season_name, 0

        date_str = m.group(1)  # "2 октября 2025"
        months = {
            "января": "01", "февраля": "02", "марта": "03",
            "апреля": "04", "мая": "05", "июня": "06",
            "июля": "07", "августа": "08", "сентября": "09",
            "октября": "10", "ноября": "11", "декабря": "12",
        }
        day, month_ru, year = date_str.split()
        month = months.get(month_ru.lower())
        if not month:
            return season_name, 0
        iso = f"{year}-{month}-{day.zfill(2)}T00:00:00+00:00"
        try:
            ts = int(datetime.fromisoformat(iso).timestamp())
        except Exception:
            ts = 0
        return season_name, ts

    def parse_title_page(self, html: str, base_url: str) -> Dict[str, Optional[str]]:
        """Извлекает все требуемые поля из HTML страницы тайтла."""
        soup = BeautifulSoup(html, "html.parser")

        # ── названия ──
        header = soup.select_one("header.pmovie__header")
        name_ru = self._text_or_none(header.select_one("h1"))
        name_en = self._text_or_none(header.select_one("div.pmovie__main-info"))
        name_alter = self._text_or_none(header.select_one("div.courssp"))

        # ── жанры ──
        genres = [
            a.get_text(strip=True)
            for a in soup.select("div.animli a")
        ]

        # ── список <ul> с метаданными ──
        meta = {  # ключ → CSS‑селектор внутри <li>
            "year": "li:has(span:-soup-contains('Год')) a",
            "status": "li:has(span:-soup-contains('Статус')) a",
            "type": "li:has(span:-soup-contains('Тип')) a",
            "studio": "li:has(span:-soup-contains('Студия')) a",
        }
        extracted = {}
        for field, selector in meta.items():
            extracted[field] = self._text_or_none(soup.select_one(selector))

        # ── рейтинг ──
        rating = self._text_or_none(soup.select_one(
            "div.item-slide__ext-rating.item-slide__ext-rating--imdb"
        ))
        # TODO: add Chinese rating. But it displays not for every title
        # rating_kp = _text_or_none(soup.select_one(
        #    "div.item-slide__ext-rating.item-slide__ext-rating--kp"
        # ))

        # ── описание ──
        description = self._text_or_none(soup.select_one(
            "div.pmovie__text.full-text.clearfix p"
        ))

        # ── постер ──
        poster_tag = soup.select_one("div.pmovie__img img")
        poster = urljoin(base_url, poster_tag["src"]) if poster_tag else None

        # ── сезон и дата выхода ──
        season_li = soup.select_one("li:has(span:-soup-contains('Сезон года'))")
        season_name, updated_ts = self._parse_season_and_updated(season_li)

        # ── типовая информация (эпизоды, длительность) ──
        type_info = self._parse_type_info(soup)

        return {
            "name_ru": name_ru,
            "name_en": name_en,
            "alternative": name_alter,
            "genres": genres,
            "season": season_name,
            "updated": updated_ts,
            "year": int(extracted["year"]),
            "status": extracted["status"],
            "type": extracted["type"],
            "studio": extracted["studio"],
            "rating": float(rating),
            "description": description,
            "poster": poster,
            "type_full": type_info["type_full"],
            "episodes": type_info["episodes"],
            "length": type_info["length"],
        }

    # Schedule
    async def parse_page_for_announce_titles(self, html: str, max_titles: int) -> List[str]:
        soup = BeautifulSoup(html, "html.parser")
        amd_blocks = soup.select("div.amd")
        announce_items: List[BeautifulSoup] = []
        for blk in amd_blocks:
            if blk.select_one("div.js-custom-content"):
                continue
            announce_items.extend(self._extract_items(blk))
        return self._build_new_titles(announce_items, max_titles)

    async def parse_page_for_new_titles(self, html: str, max_titles: int) -> List[str]:
        soup = BeautifulSoup(html, "html.parser")
        main_block = soup.select_one("div.js-custom-content")
        if not main_block:
            return []
        items = self._extract_items(main_block)
        return self._build_new_titles(items, max_titles)

    @staticmethod
    def _extract_items(container: BeautifulSoup) -> List[BeautifulSoup]:
        """Возвращает список <a class="ftop-item"> внутри переданного контейнера."""
        return container.select("a.ftop-item")

    @staticmethod
    def parse_ajax_total_pages(html):
        soup = BeautifulSoup(html, "html.parser")
        nav = soup.find("div", class_="ac-navigation")
        if not nav:
            return 1
        pages = [int(a["data-page"]) for a in nav.select("a[data-page]")]
        return pages


    # -- All titles
    @staticmethod
    def parse_total_pages(html):
        soup = BeautifulSoup(html, "html.parser")
        nav = soup.select_one("div.pagination__pages")
        if not nav:
            return 1
        # ссылки выглядят так: <a href=".../page/2/">2</a>
        pages = []
        for a in nav.select("a"):
            try:
                # берём номер из URL, а не из data-page (в этой разметке его нет)
                num = int(a["href"].rstrip("/").split("/")[-1])
                pages.append(num)
            except (KeyError, ValueError):
                continue
        return pages

    async def parse_all_titles_page(self, html: str, max_titles: int) -> List[str]:
        """
        Парсит страницу, полученную из блока <div id="dle-content">.
        Возвращает список строк, где поля разделены символом "·".
        """
        soup = BeautifulSoup(html, "html.parser")
        container = soup.select_one("div#dle-content")
        if not container:
            return []

        items = container.select("div.poster.has-overlay.grid-item")
        titles: List[str] = []
        separator = "\u00B7"

        for item in items[:max_titles]:
            # ---- ссылка и ID ----
            link_tag = item.select_one("a.poster__link")
            link = None
            title_id = None
            if link_tag and link_tag.has_attr("href"):
                link = self.base_url.rstrip("/") + link_tag["href"]
                title_id = str(extract_id_from_url(link))

            # ---- название ----
            title_el = item.select_one("h3.poster__title")
            title = title_el.get_text(strip=True) if title_el else "—"

            # ---- постер ----
            img_el = item.select_one("div.poster__img img")
            poster_url = None
            if img_el and img_el.has_attr("src"):
                poster_url = urljoin(self.base_url, img_el["src"])

            # ---- эпизод/кол-во ----
            ep_el = item.select_one("div.vysser")
            episode = None
            if ep_el:
                # пример: "1 из 1" → берём первое число
                txt = ep_el.get_text(strip=True)
                episode = txt.split()[0] if txt else None

            # ---- рейтинг ----
            rating_el = item.select_one("div.item__rating")
            rating = rating_el.get_text(strip=True) if rating_el else None

            # ---- дата/время обновления ----
            # В примерах дата берётся из соседних элементов, но в текущем HTML её нет.
            # Если понадобится, её можно добавить позже, сейчас оставляем пустой строкой.
            update_time = ""

            parts = [title, rating, update_time, f"{episode} серия" if episode else None,
                     title_id, poster_url, link]
            # Убираем пустые/None
            parts = [p for p in parts if p]
            titles.append(separator.join(parts))

        return titles