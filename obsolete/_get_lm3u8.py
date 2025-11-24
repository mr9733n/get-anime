import re
import json
from bs4 import BeautifulSoup
import requests
from urllib.parse import urljoin

BASE_URL = 'https://amedia.online/2082-ja-byl-predan-tovarischami-v-glubine-podzemelja-no-blagodarja-svoemu-navyku-beskonechnaja-gacha-ja-obrel-sojuznikov-devjat-tysjach-devjatsot.html'


def get_file_from_script(page_url: str) -> str | None:
    """Запрашивает страницу и возвращает значение file из любого <script>."""
    resp = requests.get(page_url, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    print(soup)
    # перебираем все <script>‑теги
    for script in soup.find_all("script"):
        # script.string бывает None, поэтому берём текст через get_text()
        txt = script.string or script.get_text()

        # 1️⃣ Простой регекс: file:"https://…"
        m = re.search(r'file\s*[:=]\s*["\']([^"\']+)["\']', txt)
        if m:
            return urljoin(page_url, m.group(1))

        # 2️⃣ Если в скрипте объявлен объект JavaScript,
        #    пытаемся превратить его в JSON‑строку.
        obj_match = re.search(r'var\s+\w+\s*=\s*({.*?});', txt, re.DOTALL)
        if obj_match:
            raw_obj = obj_match.group(1)

            # Добавляем кавычки к ключам, чтобы получилась валидная JSON‑строка
            json_like = re.sub(r'(?<!")(\b\w+\b)\s*:', r'"\1":', raw_obj)

            try:
                data = json.loads(json_like)
                if "file" in data:
                    return urljoin(page_url, data["file"])
            except json.JSONDecodeError:
                # если не удалось распарсить – просто игнорируем
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

    #print(soup)
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
