import os
import math
import requests
from bs4 import BeautifulSoup
import re
import time
from urllib.parse import urljoin

# Базовые настройки
BASE_URL = "https://anilibria.tv"
CATALOG_URL = f"{BASE_URL}/public/catalog.php"
HEADERS = {
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "Priority": "u=1, i",
    "Sec-CH-UA": '"Chromium";v="132", "DuckDuckGo";v="132", "Not A(Brand";v="8"',
    "Sec-CH-UA-Mobile": "?0",
    "Sec-CH-UA-Platform": '"Windows"',
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
    "Sec-GPC": "1",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": "https://anilibria.tv/pages/catalog.php"
}

SEARCH_PARAM = '{"year":"","genre":"","season":""}'
FILE_PATH = "title_ids.txt"


def get_total_and_pages():
    """
    Отправляет запрос для первой страницы каталога, чтобы получить общее количество релизов (total)
    и вычисляет количество страниц (с учетом, что на странице максимум 12 тайтлов).
    Возвращает кортеж (total, num_pages) или (None, None) в случае ошибки.
    """
    data = {
        "page": "1",
        "xpage": "catalog",
        "sort": "2",
        "finish": "1",
        "search": SEARCH_PARAM
    }
    try:
        response = requests.post(CATALOG_URL, headers=HEADERS, data=data)
        response.encoding = "utf-8"
        json_data = response.json()
        total = json_data.get("total")
        if total is not None:
            total = int(total)
            num_pages = math.ceil(total / 12)
            return total, num_pages
        else:
            print("Не удалось получить total из ответа")
            return None, None
    except Exception as e:
        print("Ошибка получения total:", e)
        return None, None


def is_file_complete(file_path, total):
    """
    Проверяет, существует ли файл и содержит ли он нужное число записей (total).
    """
    if os.path.exists(file_path) and total is not None:
        with open(file_path, "r", encoding="utf-8") as file:
            lines = [line.strip() for line in file if line.strip()]
        return len(lines) == total
    return False


def scrape_title_ids(num_pages, file_path):
    """
    Проходит по страницам каталога, извлекает title_id для каждого релиза и записывает данные в файл.
    """
    with open(file_path, "w", encoding="utf-8") as outfile:
        for page in range(1, num_pages + 1):
            print(f"Обработка страницы {page}...")
            data = {
                "page": str(page),
                "xpage": "catalog",
                "sort": "2",
                "finish": "1",
                "search": SEARCH_PARAM
            }
            try:
                response = requests.post(CATALOG_URL, headers=HEADERS, data=data)
                response.encoding = "utf-8"
                json_data = response.json()
                table_html = json_data.get("table", "")
            except Exception as e:
                print(f"Ошибка при получении страницы {page}: {e}")
                continue

            soup = BeautifulSoup(table_html, "html.parser")
            release_links = soup.find_all("a", href=re.compile(r"^/release/"))
            if not release_links:
                print(f"На странице {page} не найдено ссылок на релизы.")
                continue

            for link in release_links:
                release_href = link.get("href")
                release_url = urljoin(BASE_URL, release_href)

                # Ищем внутри ссылки тег <img> с классом "torrent_pic"
                img_tag = link.find("img", class_="torrent_pic")
                if img_tag:
                    img_src = img_tag.get("src")
                    # Извлекаем title_id – число между /storage/releases/posters/ и следующим слэшем
                    match = re.search(r"/storage/releases/posters/(\d+)/", img_src)
                    if match:
                        title_id = match.group(1)
                        print(f"Релиз: {release_url}, title_id: {title_id}")
                        outfile.write(f"{release_url} -> {title_id}\n")
                    else:
                        print(f"Не удалось извлечь title_id из: {img_src}")
                else:
                    print(f"Изображение не найдено для: {release_url}")
            time.sleep(0.5)


def read_title_ids(file_path):
    """
    Читает файл и возвращает список title_id в виде чисел.
    """
    title_ids = []
    with open(file_path, "r", encoding="utf-8") as file:
        for line in file:
            line = line.strip()
            if not line:
                continue
            if "->" in line:
                parts = line.split("->")
                if len(parts) == 2:
                    tid_str = parts[1].strip()
                    try:
                        title_ids.append(int(tid_str))
                    except ValueError:
                        print(f"Не удалось преобразовать {tid_str} в число")
    return title_ids


def main():
    total, num_pages = get_total_and_pages()
    if total is not None:
        print("Total релизов:", total)
        print("Количество страниц:", num_pages)
    else:
        print("Общее количество релизов неизвестно, продолжаем скрапинг")
        num_pages = 1

    if is_file_complete(FILE_PATH, total):
        print("Файл содержит полное количество записей, скрапинг не требуется")
    else:
        print("Файл не содержит полного количества записей, запускаем скрапинг")
        scrape_title_ids(num_pages, FILE_PATH)

    title_ids = read_title_ids(FILE_PATH)
    print("Title IDs:", title_ids)


if __name__ == "__main__":
    main()
