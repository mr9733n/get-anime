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

def extract_file_from_html(html: str, base_url: str) -> Optional[str]:
    """Ищет в HTML строку `file = "..."` и возвращает абсолютный URL."""
    soup = BeautifulSoup(html, "html.parser")
    for script in soup.find_all("script"):
        txt = script.string or script.get_text()
        m = re.search(r'file\s*[:=]\s*["\']([^"\']+)["\']', txt)
        if m:
            return urljoin(base_url, m.group(1))
    return None

def replace_spaces(text: str) -> str:
    """
    Привести строку к безопасному имени файла:
    • пробелы → «_»;
    • дефис «-» → «_»;
    • удалить все точки «.»;
    • убрать любые остальные «опасные» символы;
    • оставить только буквы, цифры и подчёркивание.
    """
    if text is None:
        return None
    text = str(text)
    text = text.replace('"', "").replace("'", "")
    text = text.replace(" ", "_").replace("-", "_")
    text = text.replace(".", "")
    text = re.sub(r"[^A-Za-z0-9_]", "", text)
    return text

def text_or_none(tag) -> Optional[str]:
    return tag.get_text(strip=True) if tag else None