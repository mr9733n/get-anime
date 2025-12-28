# app/qt/app_persistence.py
from __future__ import annotations

from datetime import datetime, timezone

class PersistenceMixin:
    def _save_parsed_data(self, parsed_data):
        for i, item in enumerate(parsed_data):
            self.db_manager.save_schedule(item["day"], item["title_id"], last_updated=datetime.now(timezone.utc))
            # TODO: fix this. need to count as dict
            self.logger.debug(
                f"[{i + 1}/{len(parsed_data)}] Saved title_id from API: {item['title_id']} on day {item['day']}")


    def _save_titles_list(self, titles_list):
        try:
            for title_data in titles_list:
                external_id = title_data.get('external_id', {})
                self.logger.debug(
                    f"[XXX] Saving external_id from API: {external_id}")
            title_ids = self.invoke_database_save(titles_list)
            self.current_data = titles_list
            return title_ids
        except Exception as e:
            self.logger.error(f"Ошибка при save titles расписания: {e}")


    def invoke_database_save(self, title_list: list[dict]) -> list[int]:
        """
        Сохраняет тайтлы + эпизоды + торренты.
        Возвращает список ВНУТРЕННИХ title_id из БД.
        """
        self.logger.debug(f"Processing title data: {len(title_list)}")
        internal_ids: list[int] = []

        processes = {
            self.db_manager.process_episodes: "episodes",
            self.db_manager.process_torrents: "torrents",
        }

        for raw_title_data in title_list:
            title_ok, title_id = self.db_manager.process_titles(raw_title_data)

            if not title_ok or title_id is None:
                self.logger.warning(
                    f"Failed to process title (external_id={raw_title_data.get('external_id')}, "
                    f"provider={raw_title_data.get('provider')})"
                )
                continue

            internal_ids.append(title_id)
            payload = {"title_id": title_id, **raw_title_data}

            for process_func, process_name in processes.items():
                try:
                    result = process_func(payload)
                    if result:
                        self.logger.debug(
                            f"Successfully saved {process_name} table for title_id={title_id}. STATUS: {result}")
                    else:
                        self.logger.warning(f"Failed to process {process_name} for title_id={title_id}")
                except Exception as e:
                    self.logger.error(f"Exception while processing {process_name} for title_id={title_id}: {e}")

        return internal_ids
