# providers/animedia/v0/legacy_mapper.py
import re
import uuid
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse, urlunparse, parse_qs, parse_qsl, urlencode
from typing import Iterable, Union, Optional, Literal, List, Dict, Any


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
            u = "https://" + u
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


def _canon_query(query: str) -> str:
    q = parse_qsl(query, keep_blank_values=True)
    q.sort()
    return urlencode(q, doseq=True)


def dedup_key(u: str) -> str:
    p = urlparse(u)
    host = (p.netloc or "").lower()
    path = p.path or ""

    if host.endswith(("vkvideo.ru", "vk.com")) and path.endswith("/video_ext.php"):
        qs = parse_qs(p.query)
        oid = (qs.get("oid", [""])[0])
        vid = (qs.get("id", [""])[0])
        h = (qs.get("hash", [""])[0])
        if oid and vid and h:
            return f"{p.scheme}://{host}{path}?oid={oid}&id={vid}&hash={h}"

    return urlunparse((p.scheme, host, path, p.params, _canon_query(p.query), ""))


def dedup_urls(urls: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for u in urls:
        key = dedup_key(u)
        if key not in seen:
            seen.add(key)
            out.append(u)
    return out


def dedup_and_sort(urls: List[str]) -> List[str]:
    """
    Убирает дубликаты и сортирует ссылки по номеру эпизода.
    """
    unique_urls = uniq(urls)
    return sort_by_episode(unique_urls)


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


def episodes_dict(sorted_links: List[str]) -> Dict[str, Dict[str, Any]]:
    """
    Присваивает каждой ссылке порядковый номер (1‑based) и
    формирует структуру с полями sd/hd/fhd.
    """
    episodes: Dict[str, Dict[str, Any]] = {}

    for idx, link in enumerate(sorted_links, start=1):   # <-- порядковый номер
        # создаём запись один раз
        episodes[str(idx)] = {
            "hls": {"fhd": "", "hd": "", "sd": ""},
            "uuid": str(uuid.uuid4()),
            "created_timestamp": 0,
            "episode": idx,
            "name": f"Серия {idx}",
            "preview": None,
            "skips": {"ending": [None, None], "opening": [None, None]},
        }

        # определяем качество ссылки
        if link.endswith(".m3u8"):
            episodes[str(idx)]["hls"]["sd"] = _strip_host(link)
            episodes[str(idx)]["hls"]["hd"] = _strip_host(add_720(link))
        else:
            episodes[str(idx)]["hls"]["fhd"] = link

    return episodes


def extract_id_from_url(url: str) -> int:
    try:
        last = url.rstrip("/").split("/")[-1]
        num = "".join(ch for ch in last if ch.isdigit())
        return int(num) if num else 0
    except Exception:
        return 0


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


def _slugify(text: Optional[str], sep: str) -> Optional[str]:
    """
    Привести строку к безопасному имени файла.
    * `sep` - символ‑разделитель: «-» или «_».
    """
    if text is None:
        return None
    txt = str(text).replace('"', "").replace("'", "")
    txt = txt.replace(" ", sep).replace(".", "")
    txt = re.sub(r"[^A-Za-z0-9_-]", "", txt)
    opposite = "_" if sep == "-" else "-"
    txt = txt.replace(opposite, sep)
    txt = re.sub(rf"{re.escape(sep)}{{2,}}", sep, txt)
    txt = txt.strip(sep)

    return txt.lower()


def replace_spaces_to_hyphen(text: Optional[str]) -> Optional[str]:
    """Slug с дефисами – используется для `code`."""
    return _slugify(text, "-")


def replace_spaces_to_underline(text: Optional[str]) -> Optional[str]:
    """Slug с подчёркиваниями – используется в URL‑частях."""
    return _slugify(text, "_")


def replace_brackets(text: str) -> str | None:
    txt = str(text).replace("«", "").replace('»', "")
    return txt


def build_base_dict(
    *,
    url: str,
    stream_video_host: str,
    meta: Dict[str, Any],
    episodes: Dict[str, Dict[str, str | None]],
    status: Dict[str, Any],
    sanitized_code: str,
    sanitized_name_ru: str,
) -> Dict[str, Any]:
    """Собирает общий словарь‑результат без дублирования кода."""

    original_id = extract_id_from_url(url)
    updated_ts = meta.get("updated") or 0
    for ep_data in episodes.values():
        ep_data["created_timestamp"] = updated_ts

    return {
        "external_id": original_id,
        "provider": "AniMedia",
        "code": sanitized_code,
        "announce": meta.get("announce", ""),
        "names": {
            "ru": sanitized_name_ru,
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
            "small": {},
            "medium": {},
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


