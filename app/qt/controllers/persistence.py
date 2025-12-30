# app/qt/controllers/persistence.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from app.qt.protocols import IDBManager

if TYPE_CHECKING:
    from logging import Logger


@dataclass
class PersistenceControllerDeps:
    """Явные зависимости PersistenceController"""
    logger: Logger
    db: IDBManager


class PersistenceController:
    """
    Контроллер для сохранения данных в БД.
    Независимый контроллер — не зависит от других контроллеров.
    """

    def __init__(self, deps: PersistenceControllerDeps):
        self._deps = deps

    @property
    def log(self) -> Logger:
        return self._deps.logger

    @property
    def db(self) -> IDBManager:
        return self._deps.db

    # === Public API ===

    def invoke_database_save(self, title_list: list[dict]) -> list[int]:
        """
        Сохраняет тайтлы + эпизоды + торренты.
        Возвращает список ВНУТРЕННИХ title_id из БД.
        """
        self.log.debug(f"Processing title data: {len(title_list)}")
        internal_ids: list[int] = []

        for raw_title_data in title_list:
            title_id = self._process_single_title(raw_title_data)
            if title_id is not None:
                internal_ids.append(title_id)

        return internal_ids

    def save_titles_list(self, titles_list: list[dict]) -> list[int]:
        """Сохраняет список тайтлов."""
        try:
            for title_data in titles_list:
                external_id = title_data.get('external_id')
                self.log.debug(f"Saving external_id from API: {external_id}")

            return self.invoke_database_save(titles_list)

        except Exception as e:
            self.log.error(f"Ошибка при save titles: {e}")
            return []

    def save_parsed_data(self, parsed_data: list[dict]) -> None:
        """Сохраняет распарсенные данные расписания."""
        for i, item in enumerate(parsed_data):
            self.db.save_schedule(
                item["day"],
                item["title_id"],
                last_updated=datetime.now(timezone.utc)
            )
            self.log.debug(
                f"[{i + 1}/{len(parsed_data)}] Saved title_id: {item['title_id']} on day {item['day']}"
            )

    # === Private Methods ===

    def _process_single_title(self, raw_title_data: dict) -> int | None:
        """Обрабатывает один тайтл."""
        title_ok, title_id = self.db.process_titles(raw_title_data)

        if not title_ok or title_id is None:
            self.log.warning(
                f"Failed to process title (external_id={raw_title_data.get('external_id')})"
            )
            return None

        payload = {"title_id": title_id, **raw_title_data}
        self._process_related_data(title_id, payload)

        return title_id

    def _process_related_data(self, title_id: int, payload: dict) -> None:
        """Обрабатывает связанные данные (эпизоды, торренты)."""
        processors = [
            (self.db.process_episodes, "episodes"),
            (self.db.process_torrents, "torrents"),
        ]

        for process_func, name in processors:
            try:
                result = process_func(payload)
                if result:
                    self.log.debug(f"Saved {name} for title_id={title_id}")
                else:
                    self.log.warning(f"Failed to process {name} for title_id={title_id}")
            except Exception as e:
                self.log.error(f"Exception processing {name} for title_id={title_id}: {e}")