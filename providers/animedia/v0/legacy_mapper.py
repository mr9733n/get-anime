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


def extract_id_from_url(url: str) -> int:
    try:
        last = url.rstrip("/").split("/")[-1]
        num = "".join(ch for ch in last if ch.isdigit())
        return int(num) if num else 0
    except Exception:
        return 0


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


def replace_brackets(text: str) -> str | None:
    txt = str(text).replace("«", "").replace('»', "")
    return txt


