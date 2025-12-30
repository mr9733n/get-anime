# app/qt/controllers/posters.py
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import TYPE_CHECKING

from app.qt.app_constants import DOWNLOAD_AFTER_AGE, FINAL_AGE
from app.qt.protocols import IDBManager

if TYPE_CHECKING:
    from logging import Logger
    from app.qt.app_context import AppContext
    from utils.downloads.poster_manager import PosterManager


@dataclass
class PosterControllerDeps:
    """Явные зависимости PosterController"""
    logger: Logger
    db: IDBManager
    context: AppContext
    poster_manager: PosterManager

    # Config
    base_al_url: str = ""
    base_am_url: str = ""
    url_prefix: str = "https://"


class PosterController:
    """
    Контроллер для работы с постерами.
    Независимый контроллер — не зависит от других контроллеров.
    """

    def __init__(self, deps: PosterControllerDeps):
        self._deps = deps

    # === Properties ===

    @property
    def log(self) -> Logger:
        return self._deps.logger

    @property
    def db(self) -> IDBManager:
        return self._deps.db

    @property
    def ctx(self) -> AppContext:
        return self._deps.context

    @property
    def poster_manager(self) -> PosterManager:
        return self._deps.poster_manager

    # === Public API ===

    def get_poster_or_placeholder(
            self,
            title_id: int,
            size_key: str = "original",
            force_download: bool = False,
    ) -> bytes | None:
        """
        Получает постер для тайтла или плейсхолдер.
        Инициирует скачивание только если постер устарел или отсутствует.
        """
        try:
            poster_data, is_placeholder = self.db.get_poster_blob(title_id, size_key=size_key)
            need_download = self._should_download_poster(
                title_id, size_key, poster_data, is_placeholder, force_download
            )

            if need_download:
                self._queue_poster_download(title_id, size_key)

            return poster_data

        except Exception as e:
            self.log.error(f"Ошибка get_poster_or_placeholder: {e}")
            return None

    def clear_previous_posters(self) -> None:
        """Удаляет все предыдущие виджеты из сетки постеров."""
        layout = self.ctx.posters_layout
        if layout is None:
            return

        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
            elif item.layout() is not None:
                self._clear_layout_recursive(item.layout())

    @staticmethod
    def sanitize_filename(name: str) -> str:
        """Очищает имя файла от недопустимых символов."""
        return re.sub(r'[<>:"/\\|?*]', '_', name)

    # === Private Methods ===

    def _should_download_poster(
            self,
            title_id: int,
            size_key: str,
            poster_data: bytes | None,
            is_placeholder: bool,
            force_download: bool,
    ) -> bool:
        """Определяет, нужно ли скачивать постер."""
        if force_download:
            self.log.debug(f"Force download for title_id={title_id}, size_key={size_key}")
            return True

        if not poster_data or is_placeholder:
            return True

        poster_date = self.db.get_poster_last_updated(title_id, size_key=size_key)
        if not poster_date:
            return True

        return self._is_poster_stale(poster_date, title_id, size_key)

    def _is_poster_stale(self, poster_date: datetime, title_id: int, size_key: str) -> bool:
        """Проверяет, устарел ли постер."""
        if poster_date.tzinfo is None:
            poster_date = poster_date.replace(tzinfo=timezone.utc)

        current_time = datetime.now(timezone.utc)
        poster_age = current_time - poster_date

        week_age = timedelta(days=DOWNLOAD_AFTER_AGE)
        final_age = timedelta(days=FINAL_AGE)

        if poster_age < week_age:
            self.log.debug(f"Poster for title_id={title_id} is fresh. Skipping.")
            return False
        elif poster_age < final_age:
            self.log.debug(f"Poster for title_id={title_id} is stale. Scheduling download.")
            return True
        else:
            self.log.debug(f"Poster for title_id={title_id} is final (>90 days). Skipping.")
            return False

    def _queue_poster_download(self, title_id: int, size_key: str) -> None:
        """Добавляет постер в очередь на скачивание."""
        poster_link = self.db.get_poster_link(title_id, size_key)
        if not poster_link:
            return

        processed_link = self._process_poster_link(poster_link)
        if processed_link:
            self.poster_manager.write_poster_links([(title_id, processed_link, size_key)])
            self.log.debug(f"Added poster for title_id={title_id} to download queue.")

    def _process_poster_link(self, poster_link: str) -> str | None:
        """Нормализует URL постера."""
        try:
            standardized_url = None
            is_full_url = poster_link.startswith(("http://", "https://"))
            contains_base = any(
                base in poster_link
                for base in (self._deps.base_al_url, self._deps.base_am_url)
            )

            if is_full_url and contains_base:
                standardized_url = self._standardize_url(poster_link)
            elif poster_link.startswith("/"):
                full_url = f"{self._deps.url_prefix}{self._deps.base_al_url}{poster_link}"
                standardized_url = self._standardize_url(full_url)

            if not standardized_url:
                return None

            # Проверяем кэш
            cached_urls = [url for (_, url, _) in self.poster_manager.poster_links]
            if standardized_url in cached_urls:
                self.log.debug(f"Poster URL already cached: {standardized_url[-40:]}")
                return None

            return standardized_url

        except Exception as e:
            self.log.error(f"Error processing poster link: {e}")
            return None

    @staticmethod
    def _standardize_url(url: str) -> str:
        """Стандартизирует URL для сравнения."""
        return url.strip().split('?')[0]

    def _clear_layout_recursive(self, layout) -> None:
        """Рекурсивно очищает layout."""
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
            elif item.layout() is not None:
                self._clear_layout_recursive(item.layout())