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
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
base_dir = os.path.join(ROOT_DIR, "midnight")
log_path = os.path.join(ROOT_DIR, "logs")
FILE_PATH = os.path.join(log_path, "title_ids.txt")


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


def read_title_ids(file_path):
    """
    Читает файл и возвращает список title_id в виде чисел.
    Ожидается, что каждая строка имеет формат: "URL -> title_id"
    """
    title_ids = []
    if not os.path.exists(file_path):
        return title_ids
    with open(file_path, "r", encoding="utf-8") as file:
        for line in file:
            line = line.strip()
            if not line:
                continue
            if "->" in line:
                parts = line.split("->")
                if len(parts) == 3:
                    tid_str = parts[1].strip()
                    poster_path = parts[2].strip()
                    # Находим числовой ID
                    match = re.search(r'\d+', tid_str)
                    if match:
                        tid_str = match.group(0)
                        try:
                            title_ids.append(int(tid_str))
                        except ValueError:
                            print(f"Не удалось преобразовать {tid_str} в число")
                    else:
                        print(f"Не удалось найти числовой ID в строке: {line}")
    return title_ids


def scrape_title_ids(existing_ids, num_pages, file_path):
    """
    Проходит по страницам каталога, извлекает title_id и путь постера для каждого релиза
    и записывает в файл только те записи, которых нет в existing_ids.
    """
    new_title_ids = []
    with open(file_path, "a", encoding="utf-8") as outfile:
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
                img_tag = link.find("img", class_="torrent_pic")
                if img_tag:
                    img_src = img_tag.get("src")
                    match = re.search(r"/storage/releases/posters/(\d+)/(.+)$", img_src)
                    if match:
                        title_id = match.group(1)
                        poster_path = match.group(2)
                        title_id_int = int(title_id)

                        if title_id_int not in existing_ids:
                            print(f"Новый релиз: {release_url}, title_id: {title_id}, poster: {poster_path}")
                            outfile.write(f"{release_url} -> {title_id} -> {poster_path}\n")
                            new_title_ids.append(title_id_int)
                            existing_ids.add(title_id_int)
                    else:
                        print(f"Не удалось извлечь title_id из: {img_src}")
                else:
                    print(f"Изображение не найдено для: {release_url}")
            time.sleep(0.5)
    return new_title_ids


def main():
    total, num_pages = get_total_and_pages()
    if total is not None:
        print("Total релизов:", total)
        print("Количество страниц:", num_pages)
    else:
        print("Общее количество релизов неизвестно, продолжаем...")
        num_pages = 1

    existing_ids = set(read_title_ids(FILE_PATH))
    print("Найдено записей в файле:", len(existing_ids))

    if total is not None and len(existing_ids) == total:
        print("Файл содержит полное количество записей, обновление не требуется")
        new_title_ids = []
    else:
        print("Запускаем получение новых данных...")
        new_title_ids = scrape_title_ids(existing_ids, num_pages, FILE_PATH)

    print("Новые Title IDs:", new_title_ids)
    all_title_ids = read_title_ids(FILE_PATH)
    print("Все Title IDs:", all_title_ids)


if __name__ == "__main__":
    main()
