# providers/animedia/v0/parser.py
import re
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Callable, Awaitable, TypeVar
from urllib.parse import urljoin
from bs4 import BeautifulSoup

from providers.animedia.v0.legacy_mapper import extract_id_from_url

class AniMediaParser:
    TITLE_LAYOUTS = {
        "old": {
            "simple_fields": {
                "name_ru": "header.pmovie__header h1",
                "name_en": "header.pmovie__header div.pmovie__main-info",
                "alternative": "header.pmovie__header div.courssp",
                "description": "div.pmovie__text.full-text.clearfix p",
                "rating": "div.item-slide__ext-rating.item-slide__ext-rating--imdb",
            },
            "poster": "div.pmovie__img img",
            "genres": "div.animli a",
        },
        "new": {
            "simple_fields": {
                "name_ru": ".amd-title h1",
                "name_en": ".amd-sub",
                "alternative": ".amd-alt-names div",
                "description": ".amd-description",
                "rating": ".amd-score div",
            },
            "poster": ".amd-poster > img",
            "genres": ".amd-tags a",
        },
    }

    def __init__(self, base_url: str, logger: logging.Logger | None = None,):
        self.logger = logger or logging.getLogger(__name__)
        self.base_url = base_url
        if not self.base_url.startswith(("http://", "https://")):
            self.base_url = "https://" + self.base_url.rstrip("/")

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

    def _build_new_titles(self, items: List[BeautifulSoup], max_titles: int) -> List[str]:
        results: List[str] = []
        separator = "\u00B7"

        for a in items[:max_titles]:
            link_tag = None
            if a.has_attr("href"):
                link_tag = urljoin(self.base_url, a["href"])

            extracted_id = extract_id_from_url(link_tag)
            title_id = str(extracted_id) if extracted_id is not None else ""

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
    def _text_or_none(tag) -> Optional[str]:
        return tag.get_text(strip=True) if tag else None

    def detect_title_layout(self, soup: BeautifulSoup) -> str:
        if soup.select_one(".amd-title"):
            return "new"
        if soup.select_one("header.pmovie__header"):
            return "old"
        return "unknown"

    @staticmethod
    def _safe_int(value: Optional[str]) -> Optional[int]:
        if value is None:
            return None
        value = value.strip()
        if not value:
            return None
        m = re.search(r"\d+", value)
        return int(m.group()) if m else None

    @staticmethod
    def _safe_float(value: Optional[str]) -> Optional[float]:
        if value is None:
            return None
        value = value.strip().replace(",", ".")
        if not value:
            return None
        m = re.search(r"\d+(?:\.\d+)?", value)
        return float(m.group()) if m else None

    def _parse_simple_title_fields(
        self,
        soup: BeautifulSoup,
        layout: str,
    ) -> Dict[str, Optional[str]]:
        config = self.TITLE_LAYOUTS[layout]["simple_fields"]
        result: Dict[str, Optional[str]] = {}

        for field, selector in config.items():
            result[field] = self._text_or_none(soup.select_one(selector))

        return result

    def _parse_title_poster(
        self,
        soup: BeautifulSoup,
        layout: str,
        base_url: str,
    ) -> Optional[str]:
        selector = self.TITLE_LAYOUTS[layout]["poster"]
        poster_tag = soup.select_one(selector)
        if not poster_tag:
            # fallback если верстка снова изменится
            imgs = soup.select(".amd-poster img")
            for img in imgs:
                src = img.get("src", "")
                if "/posts/" in src:
                    poster_tag = img
                    break

        src = poster_tag.get("src")
        if not src:
            return None

        return urljoin(base_url, src)

    def _parse_title_genres(
        self,
        soup: BeautifulSoup,
        layout: str,
    ) -> List[str]:
        selector = self.TITLE_LAYOUTS[layout]["genres"]
        return [a.get_text(strip=True) for a in soup.select(selector)]

    def _parse_old_title_meta(self, soup: BeautifulSoup) -> Dict[str, Optional[str]]:
        meta = {
            "year": "li:has(span:-soup-contains('Год')) a",
            "status": "li:has(span:-soup-contains('Статус')) a",
            "type": "li:has(span:-soup-contains('Тип')) a",
            "studio": "li:has(span:-soup-contains('Студия')) a",
        }

        extracted = {}
        for field, selector in meta.items():
            extracted[field] = self._text_or_none(soup.select_one(selector))

        season_li = soup.select_one("li:has(span:-soup-contains('Сезон года'))")
        season_name, updated_ts = self._parse_season_and_updated_old(season_li)

        return {
            "year": self._safe_int(extracted["year"]),
            "status": extracted["status"],
            "type": extracted["type"],
            "studio": extracted["studio"],
            "season": season_name,
            "updated": updated_ts,
        }

    def _parse_new_title_meta(self, soup: BeautifulSoup) -> Dict[str, Optional[str]]:
        result = {
            "year": None,
            "status": None,
            "type": None,
            "studio": None,
            "season": None,
            "updated": 0,
        }

        for a in soup.select(".amd-meta a"):
            href = a.get("href", "")
            text = a.get_text(strip=True)

            if "/god/" in href:
                result["year"] = self._safe_int(text)
            elif "/ongoingi/" in href:
                result["status"] = text
            elif "/sezon_goda/" in href:
                result["season"] = text.split()[0].lower() if text else None
            elif "/tip/" in href:
                result["type"] = text
            elif "/stydiya/" in href:
                result["studio"] = text

        result["updated"] = self._parse_updated_from_new_layout(soup)
        return result

    def _parse_title_meta(
        self,
        soup: BeautifulSoup,
        layout: str,
    ) -> Dict[str, Optional[str]]:
        if layout == "old":
            return self._parse_old_title_meta(soup)
        if layout == "new":
            return self._parse_new_title_meta(soup)

        return {
            "year": None,
            "status": None,
            "type": None,
            "studio": None,
            "season": None,
            "updated": 0,
        }

    @staticmethod
    def _parse_season_and_updated_old(li_tag) -> tuple[Optional[str], int]:
        if not li_tag:
            return None, 0

        season_a = li_tag.select_one("a")
        season_full = season_a.get_text(strip=True) if season_a else ""
        season_name = season_full.split()[0].lower() if season_full else None

        raw = li_tag.get_text(separator=" ", strip=True)
        m = re.search(r"выходит с\s+(\d{1,2}\s+\w+\s+\d{4})", raw, re.IGNORECASE)
        if not m:
            return season_name, 0

        date_str = m.group(1)
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

    @staticmethod
    def _parse_russian_partial_date_to_ts(raw: str) -> int:
        raw = raw.strip().lower()
        months = {
            "января": 1, "февраля": 2, "марта": 3,
            "апреля": 4, "мая": 5, "июня": 6,
            "июля": 7, "августа": 8, "сентября": 9,
            "октября": 10, "ноября": 11, "декабря": 12,
        }

        m = re.search(r"(\d{1,2})\s+([а-яё]+)(?:\s+(\d{4}))?(?:\s+(\d{1,2}):(\d{2}))?", raw, re.IGNORECASE)
        if not m:
            return 0

        day = int(m.group(1))
        month_name = m.group(2)
        year = int(m.group(3)) if m.group(3) else datetime.now(timezone.utc).year
        hour = int(m.group(4)) if m.group(4) else 0
        minute = int(m.group(5)) if m.group(5) else 0

        month = months.get(month_name)
        if not month:
            return 0

        try:
            dt = datetime(year, month, day, hour, minute, tzinfo=timezone.utc)
            return int(dt.timestamp())
        except Exception:
            return 0

    def _parse_updated_from_new_layout(self, soup: BeautifulSoup) -> int:
        timer = soup.select_one(".amd-timer")
        if timer:
            timer_value = timer.get("data-timer")
            if timer_value:
                return self._parse_russian_partial_date_to_ts(timer_value)

        next_block = soup.select_one(".amd-next")
        if next_block:
            raw = next_block.get_text(" ", strip=True)
            m = re.search(r"(\d{1,2}\s+[а-яё]+(?:\s+\d{4})?)", raw, re.IGNORECASE)
            if m:
                return self._parse_russian_partial_date_to_ts(m.group(1))

        return 0


    def _parse_old_title_type_info(self, soup: BeautifulSoup) -> Dict[str, Optional[int]]:
        result = {
            "type_full": None,
            "episodes": 0,
            "length": None,
        }

        spanser = soup.select_one("div.spanser")
        if spanser:
            txt = spanser.get_text(separator=" ", strip=True)
            m = re.search(r"из\s+(\d+)\+?", txt)
            total = int(m.group(1)) if m else 0
            result["episodes"] = total
            result["type_full"] = f"ТВ ({total} эп.)" if total else None

        return result


    def _parse_new_title_type_info(self, soup: BeautifulSoup, meta_type: Optional[str]) -> Dict[str, Optional[int]]:
        result = {
            "type_full": None,
            "episodes": 0,
            "length": None,
        }

        vser = soup.select_one(".amd-vser")
        if not vser:
            return result

        txt = vser.get_text(" ", strip=True)
        m = re.search(r"из\s+(\d+)\+?", txt)
        total = int(m.group(1)) if m else 0

        result["episodes"] = total
        if meta_type and total:
            result["type_full"] = f"{meta_type} ({total} эп.)"
        elif total:
            result["type_full"] = f"ТВ ({total} эп.)"

        return result

    def _parse_title_type_info(
        self,
        soup: BeautifulSoup,
        layout: str,
        meta_type: Optional[str],
    ) -> Dict[str, Optional[int]]:
        if layout == "old":
            return self._parse_old_title_type_info(soup)
        if layout == "new":
            return self._parse_new_title_type_info(soup, meta_type)

        return {
            "type_full": None,
            "episodes": 0,
            "length": None,
        }

    def parse_title_page(self, html: str, base_url: str) -> Dict[str, Optional[str]]:
        soup = BeautifulSoup(html, "html.parser")
        layout = self.detect_title_layout(soup)

        if layout == "unknown":
            self.logger.warning("Unknown title page layout")
            return {
                "name_ru": None,
                "name_en": None,
                "alternative": None,
                "genres": [],
                "season": None,
                "updated": 0,
                "year": None,
                "status": None,
                "type": None,
                "studio": None,
                "rating": None,
                "description": None,
                "poster": None,
                "type_full": None,
                "episodes": 0,
                "length": None,
            }

        simple = self._parse_simple_title_fields(soup, layout)
        meta = self._parse_title_meta(soup, layout)
        type_info = self._parse_title_type_info(soup, layout, meta["type"])

        return {
            "name_ru": simple["name_ru"],
            "name_en": simple["name_en"],
            "alternative": simple["alternative"],
            "genres": self._parse_title_genres(soup, layout),
            "season": meta["season"],
            "updated": meta["updated"],
            "year": meta["year"],
            "status": meta["status"],
            "type": meta["type"],
            "studio": meta["studio"],
            "rating": self._safe_float(simple["rating"]),
            "description": simple["description"],
            "poster": self._parse_title_poster(soup, layout, base_url),
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
                link = link_tag["href"]
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
