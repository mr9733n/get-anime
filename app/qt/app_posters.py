"""Poster related methods extracted from app.py.

Attach to AnimePlayerAppVer3 similarly to keep call sites intact.
"""

import re
from datetime import datetime, timezone, timedelta
from pathlib import Path
from app.qt.app_constants import DOWNLOAD_AFTER_AGE, FINAL_AGE



def get_poster_or_placeholder(self, title_id: int, size_key: str = "original", force_download: bool = False,) -> bytes | None:
    """
    Получает постер для тайтла или плейсхолдер, если постер не найден.
    Инициирует скачивание постера только если существующий постер устарел или отсутствует.
    """
    try:
        poster_data, is_placeholder = self.db_manager.get_poster_blob(title_id, size_key=size_key)
        need_download = False

        if force_download:
            need_download = True
            self.logger.debug(f"Force download requested for title_id={title_id}, size_key={size_key}")
        else:
            if not poster_data or is_placeholder:
                need_download = True
            else:
                poster_date = self.db_manager.get_poster_last_updated(title_id, size_key=size_key)
                if poster_date:
                    if poster_date.tzinfo is None:
                        poster_date = poster_date.replace(tzinfo=timezone.utc)

                    current_time = datetime.now(timezone.utc)
                    week_age = timedelta(days=DOWNLOAD_AFTER_AGE)
                    final_age = timedelta(days=FINAL_AGE)
                    poster_age = current_time - poster_date

                    if poster_age < week_age:
                        self.logger.debug(
                            f"Poster for title_id={title_id} size_key={size_key} is fresh ({poster_date}). Skipping download."
                        )
                    elif poster_age < final_age:
                        need_download = True
                        self.logger.debug(
                            f"Poster for title_id={title_id} size_key={size_key} is stale ({poster_date}). Scheduling download."
                        )
                    else:
                        self.logger.debug(
                            f"Poster for title_id={title_id} size_key={size_key} is final ({poster_date}). Skipping download considered final (older than 90 days)."
                        )
        if need_download:
            poster_link = self.db_manager.get_poster_link(title_id, size_key)
            if poster_link:
                processed_link = self.perform_poster_link(poster_link)
                if processed_link:
                    self.poster_manager.write_poster_links([(title_id, processed_link, size_key)])
                    self.logger.debug(f"Added poster for title_id {title_id} to download queue.")

        return poster_data

    except Exception as e:
        self.logger.error(f"Ошибка get_poster_or_placeholder: {e}")
        return None

def perform_poster_link(self, poster_link):
    """
    Возвращает «нормализованный» URL постера.
    Если poster_link уже является полным URL, который уже содержит
    base_al_url или base_am_url, он возвращается без добавления префикса.
    """
    try:
        standardized_url = None
        self.logger.debug(f"Processing poster link: {poster_link}")
        is_full_url = poster_link.startswith(("http://", "https://"))
        contains_base = any(
            base in poster_link for base in (self.base_al_url, self.base_am_url)
        )
        if is_full_url and contains_base:
            standardized_url = self.standardize_url(poster_link)
            self.logger.debug(
                f"Poster link already full URL → {standardized_url[-41:]}"
            )
        elif poster_link.startswith("/"):
            poster_url = f"{self.pre}{self.base_al_url}{poster_link}"
            standardized_url = self.standardize_url(poster_url)
            self.logger.debug(f"Constructed poster URL → {standardized_url[-41:]}")

        cached_urls = [url for (_, url, _) in self.poster_manager.poster_links]

        if standardized_url in cached_urls:
            self.logger.debug(
                f"Poster URL already cached: {standardized_url}. Skipping fetch."
            )
            return None

        return standardized_url

    except Exception as e:
        self.logger.error(f"Error while processing poster link: {e}")
        return None

def sanitize_filename(name):
    """
    Sanitize the filename by removing special characters that are not allowed in filenames.
    """
    return re.sub(r'[<>:"/\\|?*]', '_', name)

def standardize_url(url):
    """
    Standardizes the URL for consistent comparison.
    Strips spaces, removes query parameters if necessary, or any other needed cleaning.
    """
    return url.strip().split('?')[0]

def clear_previous_posters(self):
    """Удаляет все предыдущие виджеты из сетки постеров."""
    while self.posters_layout.count():
        item = self.posters_layout.takeAt(0)
        widget_to_remove = item.widget()
        if widget_to_remove is not None:
            widget_to_remove.deleteLater()
        if item.layout() is not None:
            self.clear_layout(item.layout())

