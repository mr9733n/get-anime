# utils.py
import re
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse, urlunparse
from typing import Iterable, Union, Optional, Literal, List, Dict
from bs4 import BeautifulSoup


def safe_str(value: bytes | str) -> str:
    """Преобразует bytes в str, оставляя строки без изменений."""
    return value.decode("utf-8") if isinstance(value, (bytes, bytearray)) else value


def uniq(seq: Iterable[Union[str, bytes]]) -> list[str]:
    """Убирает дубликаты, сохраняя порядок."""
    seen: set[str] = set()
    out: list[str] = []
    for x in seq:
        s = safe_str(x)
        if s not in seen:
            seen.add(s)
            out.append(s)
    return out


def extract_video_host(urls: Iterable[Union[str, bytes]]) -> str:
    """
    Return the hostname that appears in the given URLs.
    If all URLs share the same host, that host is returned.
    If different hosts are found, the first one encountered is returned.
    """
    for u in urls:
        # Convert bytes → str
        if isinstance(u, bytes):
            u = u.decode(errors="ignore")
        u = u.strip()

        # Ensure a scheme so urlparse can extract the netloc
        if not re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", u):
            u = "http://" + u

        host = urlparse(u).hostname
        if host:
            return host

    # No valid host found
    return ""


def sort_by_episode(urls: list[str]) -> list[str]:
    """Сортирует ссылки по номеру эпизода, извлечённому из /<num>_/. """
    def _key(u: str) -> int:
        m = re.search(r"/(\d+)_", u)
        return int(m.group(1)) if m else 0
    return sorted(urls, key=_key)


def _insert_quality(url: str, quality: str) -> str:
    """
    Insert *quality* into the URL path after the ``hls`` segment.
    If ``hls`` is not present, insert it before the final segment.
    """
    parsed = urlparse(url)
    parts = parsed.path.split("/")          # ['', 'segment1', 'segment2', ...]
    try:
        idx = parts.index("hls")
        # If the next part already equals the desired quality – do nothing
        if idx + 1 < len(parts) and parts[idx + 1] != quality:
            parts.insert(idx + 1, quality)
    except ValueError:
        # No ``hls`` – insert before the last non‑empty segment (if any)
        if len(parts) > 1:
            parts.insert(-1, quality)

    # Re‑assemble the path, discarding empty fragments that may appear
    new_path = "/" + "/".join(filter(None, parts))
    return urlunparse(parsed._replace(path=new_path))


def add_1080(url: str) -> Literal[b""]:
    """Insert ``1080`` after ``hls`` (or before the last segment)."""
    return _insert_quality(url, "1080")  # type: ignore[return-value]


def add_720(url: str) -> Literal[b""]:
    """Insert ``720`` after ``hls`` (or before the last segment)."""
    return _insert_quality(url, "720")   # type: ignore[return-value]


def extract_file_from_html(html: str, base_url: str) -> Optional[str]:
    """Ищет в HTML строку `file = "..."` и возвращает абсолютный URL."""
    soup = BeautifulSoup(html, "html.parser")
    for script in soup.find_all("script"):
        txt = script.string or script.get_text()
        m = re.search(r'file\s*[:=]\s*["\']([^"\']+)["\']', txt)
        if m:
            return urljoin(base_url, m.group(1))
    return None

def _text_or_none(tag) -> Optional[str]:
    return tag.get_text(strip=True) if tag else None


def parse_title_page(html: str, base_url: str) -> Dict[str, Optional[str]]:
    """Извлекает все требуемые поля из HTML страницы тайтла."""
    soup = BeautifulSoup(html, "html.parser")

    # ── названия ──
    header = soup.select_one("header.pmovie__header")
    name_ru = _text_or_none(header.select_one("h1"))
    name_en = _text_or_none(header.select_one("div.pmovie__main-info"))

    # ── жанры ──
    genres = [
        a.get_text(strip=True)
        for a in soup.select("div.animli a")
    ]

    # ── список <ul> с метаданными ──
    meta = {  # ключ → CSS‑селектор внутри <li>
        "season": "li:has(span:-soup-contains('Сезон года')) a",
        "year": "li:has(span:-soup-contains('Год')) a",
        "status": "li:has(span:-soup-contains('Статус')) a",
        "type": "li:has(span:-soup-contains('Тип')) a",
        "studio": "li:has(span:-soup-contains('Студия')) a",
    }
    extracted = {}
    for field, selector in meta.items():
        extracted[field] = _text_or_none(soup.select_one(selector))

    # ── рейтинг ──
    rating = _text_or_none(soup.select_one(
        "div.item-slide__ext-rating.item-slide__ext-rating--imdb"
    ))

    # ── описание ──
    description = _text_or_none(soup.select_one(
        "div.pmovie__text.full-text.clearfix p"
    ))

    # ── постер ──
    poster_tag = soup.select_one("div.pmovie__img img")
    poster = urljoin(base_url, poster_tag["src"]) if poster_tag else None

    return {
        "name_ru": name_ru,
        "name_en": name_en,
        "genres": genres,
        "season": extracted["season"],
        "year": extracted["year"],
        "status": extracted["status"],
        "type": extracted["type"],
        "studio": extracted["studio"],
        "rating": rating,
        "description": description,
        "poster": poster,
    }


def to_timestamp(iso_date: str | None) -> int:
    """Универсальная конверсия ISO‑строки → unix‑timestamp."""
    if not iso_date:
        return 0
    try:
        # поддерживаем как «2025-10-20T21:36:25Z», так и без Z
        s = iso_date.rstrip('Z')
        if 'T' not in s:
            # если пришёл только день, добавляем «T00:00:00»
            s += 'T00:00:00'
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return int(dt.timestamp())
    except Exception:
        return 0
