# utils.py
import re
import uuid
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse, urlunparse
from typing import Iterable, Union, Optional, Literal, List, Dict, Any
from bs4 import BeautifulSoup


ID_OFFSET = 30000
ORIGINAL_ID_FIELD = "animedia_id"


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
        if isinstance(u, bytes):
            u = u.decode(errors="ignore")
        u = u.strip()
        if not re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", u):
            u = "http://" + u
        host = urlparse(u).hostname
        if host:
            return host
    return ""


def _strip_host(url: str) -> str:
    """
    Возвращает только путь (и, при необходимости, начальный «/»),
    убирая схему и домен.
    """
    parsed = urlparse(url)
    path = parsed.path
    return path if path.startswith("/") else f"/{path}"


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
    parts = parsed.path.split("/")
    try:
        idx = parts.index("hls")
        if idx + 1 < len(parts) and parts[idx + 1] != quality:
            parts.insert(idx + 1, quality)
    except ValueError:
        if len(parts) > 1:
            parts.insert(-1, quality)
    new_path = "/" + "/".join(filter(None, parts))
    return urlunparse(parsed._replace(path=new_path))


def add_720(url: str) -> Literal[b""]:
    """Insert ``720`` after ``hls`` (or before the last segment)."""
    return _insert_quality(url, "720")


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


def to_timestamp(iso_date: str | None) -> int:
    """Конвертирует ISO‑строку в unix‑timestamp (UTC)."""
    if not iso_date:
        return 0
    try:
        s = iso_date.rstrip('Z')
        if 'T' not in s:
            s += 'T00:00:00'
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return int(dt.timestamp())
    except Exception:
        return 0


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

    date_str = m.group(1)                     # "2 октября 2025"
    # переводим русские названия месяцев в цифры
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
        cur = spanser.select_one("span")
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


def parse_title_page(html: str, base_url: str) -> Dict[str, Optional[str]]:
    """Извлекает все требуемые поля из HTML страницы тайтла."""
    soup = BeautifulSoup(html, "html.parser")

    # ── названия ──
    header = soup.select_one("header.pmovie__header")
    name_ru = _text_or_none(header.select_one("h1"))
    name_en = _text_or_none(header.select_one("div.pmovie__main-info"))
    name_alter = _text_or_none(header.select_one("div.courssp"))

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

    # ── сезон и дата выхода ──
    season_li = soup.select_one("li:has(span:-soup-contains('Сезон года'))")
    season_name, updated_ts = _parse_season_and_updated(season_li)

    # ── типовая информация (эпизоды, длительность) ──
    type_info = _parse_type_info(soup)

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


def _episode_number(url: str) -> str:
    """Номер эпизода берётся из части /<num>_/ в URL."""
    m = re.search(r"/(\d+)_", url)
    return str(int(m.group(1))) if m else "0"


def episodes_dict(sorted_links: list[str]) -> Dict[str, Dict[str, str | None]]:
    """
    Принимает уже отсортированные ссылки (480 p) и возвращает
    структуру, полностью соответствующую требуемому формату.
    """
    hd_links = [add_720(u) for u in sorted_links]   # 720 p
    sd_links = sorted_links                         # 480 p

    episodes: Dict[str, Dict[str, Any]] = {}
    for hd, sd in zip(hd_links, sd_links):
        ep_num = _episode_number(sd)

        episodes[ep_num] = {
            "fhd": "",
            "hd": "",
            "sd": "",
            "hd_animedia": _strip_host(hd),
            "sd_animedia": _strip_host(sd),
            "uuid": str(uuid.uuid4()),
            "created_timestamp": 0,
            "episode": int(ep_num),
            "name": f"Серия {int(ep_num)}",
            "preview": None,
            "skips": {
                "ending": [None, None],
                "opening": [None, None],
            },
        }
    return episodes


def _extract_id_from_url(url: str) -> int:
    try:
        last = url.rstrip("/").split("/")[-1]
        num = "".join(ch for ch in last if ch.isdigit())
        return int(num) if num else 0
    except Exception:
        return 0


def _make_new_id(original_id: int) -> int:
    return ID_OFFSET + original_id


def map_status(status_str: str | None) -> Dict[str, Any]:
    """
    Приводит строковый статус к старому формату:
        code: 1 = Завершён, 2 = В работе, 3 = Анонс
    """
    if not status_str:
        return {"code": 2, "string": "Завершён"}

    s = status_str.strip().lower()

    if s in {"завершён", "завершенные", "finished", "complete", "completed"}:
        return {"code": 2, "string": "Завершён"}
    if s in {"в работе", "онгоинги", "ongoing", "in_work", "current"}:
        return {"code": 1, "string": "В работе"}
    if s in {"анонс", "announcement", "announced", "planned", "in_production"}:
        return {"code": 3, "string": "Анонс"}

    return {"code": 2, "string": "Завершён"}


def replace_spaces(text: str) -> str:
    """
    Привести строку к безопасному имени файла:
    • пробелы → «-»;
    • удалить все точки «.»;
    • убрать любые «опасные» символы;
    • оставить только буквы, цифры, «-» и «_»;
    • несколько подряд идущих «-» заменить одним «-»;
    • убрать ведущие/концевые «-».
    """
    if text is None:
        return None
    txt = str(text).replace('"', "").replace("'", "")
    txt = txt.replace(" ", "-").replace(".", "")
    txt = re.sub(r"[^A-Za-z0-9_-]", "", txt)
    txt = txt.replace("_", "-")
    txt = re.sub(r"-{2,}", "-", txt)
    txt = txt.strip("-")
    return text


def build_base_dict(
    *,
    url: str,
    stream_video_host: str,
    meta: Dict[str, Any],
    episodes: Dict[str, Dict[str, str | None]],
    status: Dict[str, Any],
    sanitized_code: str,
) -> Dict[str, Any]:
    """Собирает общий словарь‑результат без дублирования кода."""

    original_id = _extract_id_from_url(url)
    new_id = _make_new_id(_extract_id_from_url(url))
    updated_ts = meta.get("updated") or 0
    for ep_data in episodes.values():
        ep_data["created_timestamp"] = updated_ts

    return {
        # "id": new_id,
        ORIGINAL_ID_FIELD: original_id,
        "code": sanitized_code,
        "announce": meta.get("announce", ""),
        "names": {
            "ru": meta.get("name_ru") or "",
            "en": meta.get("name_en") or "",
            "alternative": meta.get("alternative") or ""
        },
        "description": meta.get("description") or "",
        "season": {
            "code": None,
            "string": meta.get("season") or "",
            "year": meta.get("year") or 0,
            "week_day": meta.get("week_day") or None
        },
        "status": status,
        "type": {
            "code": 0,
            "string": meta.get("type") or "",
            "full_string": meta.get("type_full") or "",
            "episodes": meta.get("episodes") or 0,
            "length": meta.get("length") or None
        },
        "studio": meta.get("studio") or "",
        "rating": {
            "name": "AniMedia",
            "score": meta.get("rating") or 0.0
        },
        "genres": meta.get("genres") or [],
        "posters": {
            "small": {"url": meta.get("poster_small") or ""},
            "medium": {"url": meta.get("poster_medium") or ""},
            "original": {"url": meta.get("poster") or ""}
        },
        "updated": updated_ts,
        "last_change": updated_ts,
        "in_favorites": meta.get("in_favorites") or 0,
        "blocked": {
            "copyrights": False,
            "geoip": False,
            "geoip_list": []
        },
        "player": {
            "host": stream_video_host,
            "alternative_player": "",
            "list": episodes
        },
        "team": {"voice": [], "translator": [], "timing": []},
        "franchises": [],
        "torrents": {"list": []},
    }


