# utils.py
import re
from urllib.parse import urljoin, urlparse, urlunparse
from typing import Iterable, Union, Optional, Literal
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


def sort_by_episode(urls: list[str]) -> list[str]:
    """Сортирует ссылки по номеру эпизода, извлечённому из /<num>_/. """
    def _key(u: str) -> int:
        m = re.search(r"/(\d+)_", u)
        return int(m.group(1)) if m else 0
    return sorted(urls, key=_key)


def add_720(url: str) -> Literal[b""]:
    """Вставляет «720» в путь URL после сегмента «hls», если его нет."""
    p = urlparse(url)
    parts = p.path.split("/")
    try:
        idx = parts.index("hls")
        if idx + 1 < len(parts) and parts[idx + 1] != "720":
            parts.insert(idx + 1, "720")
    except ValueError:
        if len(parts) > 1:
            parts.insert(-1, "720")
    new_path = "/" + "/".join(filter(None, parts))
    return urlunparse(p._replace(path=new_path))


def extract_file_from_html(html: str, base_url: str) -> Optional[str]:
    """Ищет в HTML строку `file = "..."` и возвращает абсолютный URL."""
    soup = BeautifulSoup(html, "html.parser")
    for script in soup.find_all("script"):
        txt = script.string or script.get_text()
        m = re.search(r'file\s*[:=]\s*["\']([^"\']+)["\']', txt)
        if m:
            return urljoin(base_url, m.group(1))
    return None
