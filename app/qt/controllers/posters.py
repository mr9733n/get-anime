# app/qt/controllers/posters.py
from __future__ import annotations

import re

from typing import Any, Union, List, Dict
from datetime import datetime, timezone, timedelta

from app.qt.app_constants import DOWNLOAD_AFTER_AGE, FINAL_AGE


class PosterController:
    """
    Переходный контроллер (stage-2/3):
    - svc: доступ к db/api/ui/logger/config/playlist
    - app: доступ к orchestration-методам (display_titles, show_error_notification, invoke_database_save, ...)
    """

    def __init__(self, app: Any, svc: Any):
        self.app = app
        self.svc = svc

    @property
    def db(self):
        return self.svc.db

    @property
    def ui(self):
        return self.svc.ui

    @property
    def log(self):
        return self.svc.logger

    @property
    def api(self):
        return self.svc.api

    def get_poster_or_placeholder(self, title_id: int, size_key: str = "original", force_download: bool = False,) -> bytes | None:
        """
        Получает постер для тайтла или плейсхолдер, если постер не найден.
        Инициирует скачивание постера только если существующий постер устарел или отсутствует.
        """
        try:
            poster_data, is_placeholder = self.db.get_poster_blob(title_id, size_key=size_key)
            need_download = False

            if force_download:
                need_download = True
                self.log.debug(f"Force download requested for title_id={title_id}, size_key={size_key}")
            else:
                if not poster_data or is_placeholder:
                    need_download = True
                else:
                    poster_date = self.db.get_poster_last_updated(title_id, size_key=size_key)
                    if poster_date:
                        if poster_date.tzinfo is None:
                            poster_date = poster_date.replace(tzinfo=timezone.utc)

                        current_time = datetime.now(timezone.utc)
                        week_age = timedelta(days=DOWNLOAD_AFTER_AGE)
                        final_age = timedelta(days=FINAL_AGE)
                        poster_age = current_time - poster_date

                        if poster_age < week_age:
                            self.log.debug(
                                f"Poster for title_id={title_id} size_key={size_key} is fresh ({poster_date}). Skipping download."
                            )
                        elif poster_age < final_age:
                            need_download = True
                            self.log.debug(
                                f"Poster for title_id={title_id} size_key={size_key} is stale ({poster_date}). Scheduling download."
                            )
                        else:
                            self.log.debug(
                                f"Poster for title_id={title_id} size_key={size_key} is final ({poster_date}). Skipping download considered final (older than 90 days)."
                            )
            if need_download:
                poster_link = self.db.get_poster_link(title_id, size_key)
                if poster_link:
                    processed_link = self.perform_poster_link(poster_link)
                    if processed_link:
                        self.app.poster_manager.write_poster_links([(title_id, processed_link, size_key)])
                        self.log.debug(f"Added poster for title_id {title_id} to download queue.")

            return poster_data

        except Exception as e:
            self.log.error(f"Ошибка get_poster_or_placeholder: {e}")
            return None

    def perform_poster_link(self, poster_link):
        """
        Возвращает «нормализованный» URL постера.
        Если poster_link уже является полным URL, который уже содержит
        base_al_url или base_am_url, он возвращается без добавления префикса.
        """
        try:
            standardized_url = None
            self.log.debug(f"Processing poster link: {poster_link}")
            is_full_url = poster_link.startswith(("http://", "https://"))
            contains_base = any(
                base in poster_link for base in (self.app.base_al_url, self.app.base_am_url)
            )
            if is_full_url and contains_base:
                standardized_url = self.standardize_url(poster_link)
                self.log.debug(
                    f"Poster link already full URL → {standardized_url[-41:]}"
                )
            elif poster_link.startswith("/"):
                poster_url = f"{self.app.pre}{self.app.base_al_url}{poster_link}"
                standardized_url = self.standardize_url(poster_url)
                self.log.debug(f"Constructed poster URL → {standardized_url[-41:]}")

            cached_urls = [url for (_, url, _) in self.app.poster_manager.poster_links]

            if standardized_url in cached_urls:
                self.log.debug(
                    f"Poster URL already cached: {standardized_url}. Skipping fetch."
                )
                return None

            return standardized_url

        except Exception as e:
            self.log.error(f"Error while processing poster link: {e}")
            return None

    @staticmethod
    def sanitize_filename(name):
        """
        Sanitize the filename by removing special characters that are not allowed in filenames.
        """
        return re.sub(r'[<>:"/\\|?*]', '_', name)

    @staticmethod
    def standardize_url(url):
        """
        Standardizes the URL for consistent comparison.
        Strips spaces, removes query parameters if necessary, or any other needed cleaning.
        """
        return url.strip().split('?')[0]

    def clear_previous_posters(self):
        """Удаляет все предыдущие виджеты из сетки постеров."""
        while self.app.posters_layout.count():
            item = self.app.posters_layout.takeAt(0)
            widget_to_remove = item.widget()
            if widget_to_remove is not None:
                widget_to_remove.deleteLater()
            if item.layout() is not None:
                self.app.clear_layout(item.layout())

