import re
import json
from typing import Literal

from bs4 import BeautifulSoup
import requests
from urllib.parse import urlparse, urlunparse, urljoin

BASE_URL = 'https://amedia.online/2082-ja-byl-predan-tovarischami-v-glubine-podzemelja-no-blagodarja-svoemu-navyku-beskonechnaja-gacha-ja-obrel-sojuznikov-devjat-tysjach-devjatsot.html'

def get_file_from_script(page_url: str) -> str | None:
    """Запрашивает страницу и возвращает значение file из любого <script>."""
    resp = requests.get(page_url, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    for script in soup.find_all("script"):
        txt = script.string or script.get_text()
        m = re.search(r'file\s*[:=]\s*["\']([^"\']+)["\']', txt)
        if m:
            return urljoin(page_url, m.group(1))

        obj_match = re.search(r'var\s+\w+\s*=\s*({.*?});', txt, re.DOTALL)
        if obj_match:
            raw_obj = obj_match.group(1)
            json_like = re.sub(r'(?<!")(\b\w+\b)\s*:', r'"\1":', raw_obj)

            try:
                data = json.loads(json_like)
                if "file" in data:
                    return urljoin(page_url, data["file"])
            except json.JSONDecodeError:
                pass
    return None

def uniq_files(file_list: list[str]) -> list[str]:
    """Возвращает список без дубликатов, сохраняя порядок появления."""
    seen = set()
    uniq = []
    for url in file_list:
        if url not in seen:
            seen.add(url)
            uniq.append(url)
    return uniq

def add_720_quality(url: str) -> Literal[b""]:
    parsed = urlparse(url)
    parts = parsed.path.split('/')
    try:
        hls_idx = parts.index('hls')
        if hls_idx + 1 < len(parts) and parts[hls_idx + 1] == '720':
            new_path = parsed.path
        else:
            parts.insert(hls_idx + 1, '720')
            new_path = '/'.join(p for p in parts if p)
            new_path = '/' + new_path
    except ValueError:
        if len(parts) > 1:
            parts.insert(-1, '720')
            new_path = '/' + '/'.join(p for p in parts if p)
        else:
            new_path = parsed.path

    return urlunparse(parsed._replace(path=new_path))

def collect_files(start_page: str) -> list[str]:
    """Возвращает список всех найденных file‑URL‑ов."""
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; DuckBot/1.0)",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }

    resp = requests.get(start_page, headers=headers, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    anchors = soup.find_all("a", attrs={"data-vlnk": True})

    try:
        raw_files = []
        for a in anchors:
            vlnk_url = urljoin(start_page, a["data-vlnk"])
            file_url = get_file_from_script(vlnk_url)
            if file_url:
                raw_files.append(file_url)

        unique_files = uniq_files(raw_files)
        final_files = [add_720_quality(u) for u in unique_files]

        return final_files
    except Exception:
        return None

if __name__ == "__main__":

    found = collect_files(BASE_URL)

    print("Найденные ссылки file:")
    for f in found:
        print(f)



