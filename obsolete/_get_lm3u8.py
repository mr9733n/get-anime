import re
import json
from bs4 import BeautifulSoup
import requests
from urllib.parse import urljoin

BASE_URL = '


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


try:
    headers = {
        'User-Agent': 'Mozilla/5.0',
        'Accept': 'application/json',
    }

    base_url = BASE_URL

    html = requests.get(base_url, headers=headers)
    soup = BeautifulSoup(html.text, 'html.parser')

    raw_links = soup.find_all('a', attrs={'data-vlnk': True})

    collected_files = []

    for a in raw_links:
        vlnk_url = a['data-vlnk']
        file_url = get_file_from_script(vlnk_url)
        if file_url:
            collected_files.append(file_url)
    print('Найденные ссылки file:')
    for f in collected_files:
        print(f)

except Exception:
    pass
