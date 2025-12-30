# app/qt/controllers/aniliberty.py
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable

from app.qt.app_constants import PROVIDER_ANILIBERTY
from app.qt.app_exceptions import APIClientError
from app.qt.protocols import (
    IDisplayController,
    IPersistenceController,
    IStateController,
    IUIManager,
    IAPIAdapter,
    IDBManager,
)

if TYPE_CHECKING:
    from logging import Logger
    from app.qt.app_context import AppContext


@dataclass
class AniLibertyControllerDeps:
    """Явные зависимости AniLibertyController"""
    logger: Logger
    db: IDBManager
    ui: IUIManager
    api: IAPIAdapter
    context: AppContext
    persistence: IPersistenceController

    # Lazy callbacks
    get_display_controller: Callable[[], IDisplayController] | None = None
    get_state_controller: Callable[[], IStateController] | None = None


class AniLibertyController:
    """
    Контроллер для работы с AniLiberty API.
    Управляет расписанием, случайными тайтлами.
    """

    def __init__(self, deps: AniLibertyControllerDeps):
        self._deps = deps
        self._display: IDisplayController | None = None
        self._state: IStateController | None = None

    # === Lazy Dependencies ===

    @property
    def display(self) -> IDisplayController:
        if self._display is None:
            if self._deps.get_display_controller:
                self._display = self._deps.get_display_controller()
            else:
                raise RuntimeError("DisplayController not configured")
        return self._display

    @property
    def state(self) -> IStateController:
        if self._state is None:
            if self._deps.get_state_controller:
                self._state = self._deps.get_state_controller()
            else:
                raise RuntimeError("StateController not configured")
        return self._state

    # === Simple Properties ===

    @property
    def log(self) -> Logger:
        return self._deps.logger

    @property
    def db(self) -> IDBManager:
        return self._deps.db

    @property
    def ui(self) -> IUIManager:
        return self._deps.ui

    @property
    def api(self) -> IAPIAdapter:
        return self._deps.api

    @property
    def ctx(self) -> AppContext:
        return self._deps.context

    @property
    def persistence(self) -> IPersistenceController:
        return self._deps.persistence

    # === Public API ===

    def fetch_and_process_schedule(self, day_of_week: int) -> tuple[bool, set | None]:
        """Получает и обрабатывает расписание с сервера."""
        try:
            data = self._get_schedule(day_of_week)
            if data is None:
                self.log.warning(f"No data available for day {day_of_week}.")
                return False, None

            titles_list = self._extract_titles_from_schedule(data)
            new_title_ids = self._save_schedule_titles(titles_list)

            parsed_data = self._parse_schedule_data(data)
            self._save_parsed_schedule(parsed_data)

            return True, new_title_ids

        except Exception as e:
            self.log.error(f"Error fetching and processing schedule: {e}")
            return False, None

    def reload_schedule(self) -> None:
        """Обновляет и отображает расписание тайтлов."""
        try:
            day = self.ctx.current_day_of_week or 1

            current_titles = self.ctx.total_titles if self.ctx.total_titles else set()
            status, new_title_ids = self._check_and_update_schedule(day, current_titles)
            self.ctx.current_title_id = None

            if status and new_title_ids:
                self.display.display_titles_for_day(day, force_reload=False)
            else:
                self.display.display_titles_for_day(day, force_reload=True)

        except Exception as e:
            self.log.error(f"Ошибка при обновлении reload_schedule: {e}")

    def get_random_title(self) -> None:
        """Получает случайный тайтл из API."""
        try:
            self.ui.show_loader("Fetching random title...")
            self.ui.set_buttons_enabled(False)

            data = self.api.get_random_title()

            if not self._validate_api_response(data):
                return

            title_list = data.get('list', [])
            if not title_list:
                self.log.error("No titles found in the response.")
                self.display.show_error_notification("Error", "No titles found.")
                return

            internal_ids = self.persistence.invoke_database_save(title_list)
            title_id = internal_ids[0] if internal_ids else None

            if title_id is None:
                self.display.show_error_notification("Error", "Title ID not found.")
                return

            self.display.display_info(title_id)
            self.ctx.current_data = data

        except Exception as e:
            self.log.error(f"Error fetching random title: {e}")
            self.display.show_error_notification("Error", "Unexpected error. Check logs.")
        finally:
            self.ui.hide_loader()
            self.ui.set_buttons_enabled(True)

    # === Private Methods ===

    def _get_schedule(self, day: int) -> list | None:
        """Получает расписание из API."""
        try:
            data = self.api.get_schedule(day)

            if data is None:
                raise APIClientError(f"No data returned for day {day}.")
            if isinstance(data, dict) and 'error' in data:
                raise APIClientError(f"API error: {data['error']}")

            self.log.debug(f"Data received for day {day}: {len(data)} items")
            self.ctx.current_data = data
            return data

        except APIClientError as e:
            self.log.error(f"API Client Error: {e}")
            self.display.show_error_notification("API Error", str(e))
            return None
        except Exception as e:
            self.log.error(f"Unexpected error fetching schedule: {e}")
            self.display.show_error_notification("Error", "Unexpected error. Check logs.")
            return None

    def _extract_titles_from_schedule(self, data: list) -> list[dict]:
        """Извлекает список тайтлов из данных расписания."""
        titles_list = []
        for item in data:
            titles = item.get("list", [])
            titles_list.extend(titles)
        self.log.debug(f"Total titles (light): {len(titles_list)}")
        return titles_list

    def _save_schedule_titles(self, titles_list: list[dict]) -> set[int]:
        """Сохраняет тайтлы расписания в БД."""
        ids = [t.get('external_id') for t in titles_list if t.get('external_id')]

        if ids:
            full_list = self.api.get_releases_full(ids)
            if full_list:
                self.log.debug(f"Full bundles fetched: {len(full_list)}")
                return set(self.persistence.save_titles_list(full_list))

        return set(self.persistence.save_titles_list(titles_list))

    def _parse_schedule_data(self, data: list) -> list[dict]:
        """Парсит расписание в формат {day, title_id}."""
        parsed_data = []

        if not isinstance(data, list):
            self.log.error(f"Expected list, got: {type(data).__name__}")
            return parsed_data

        for day_info in data:
            if not isinstance(day_info, dict):
                continue

            day = day_info.get("day")
            title_list = day_info.get("list", [])

            if not isinstance(title_list, list):
                continue

            for title in title_list:
                if not isinstance(title, dict):
                    continue

                external_id = title.get("external_id")
                if not external_id:
                    continue

                title_db = self.db.get_title_by_external_id(PROVIDER_ANILIBERTY, external_id)
                if title_db and title_db.title_id:
                    parsed_data.append({"day": day, "title_id": title_db.title_id})

        return parsed_data

    def _save_parsed_schedule(self, parsed_data: list[dict]) -> None:
        """Сохраняет распарсенное расписание."""
        from datetime import datetime, timezone

        for item in parsed_data:
            self.db.save_schedule(
                item["day"],
                item["title_id"],
                last_updated=datetime.now(timezone.utc)
            )

    def _check_and_update_schedule(
            self,
            day_of_week: int,
            current_titles: set,
    ) -> tuple[bool, set | None]:
        """Проверяет и обновляет расписание."""
        try:
            self.ui.show_loader("Updating schedule...")
            self.ui.set_buttons_enabled(False)

            status, new_title_ids = self.fetch_and_process_schedule(day_of_week)
            if not status:
                return False, None

            if current_titles and new_title_ids:
                titles_to_remove = current_titles.difference(new_title_ids)
                if titles_to_remove:
                    self.log.debug(f"Titles to remove: {titles_to_remove}")
                    self.db.remove_schedule_day(titles_to_remove, day_of_week)

            return True, new_title_ids

        except Exception as e:
            self.log.error(f"Error checking and updating schedule: {e}")
            return False, None
        finally:
            self.ui.hide_loader()
            self.ui.set_buttons_enabled(True)

    def _validate_api_response(self, data: Any) -> bool:
        """Валидирует ответ API."""
        if not isinstance(data, dict):
            self.log.error(f"Unexpected response format: {type(data).__name__}")
            self.display.show_error_notification("API Error", "Unexpected response format.")
            return False

        if 'error' in data:
            self.log.error(data['error'])
            self.display.show_error_notification("API Error", data['error'])
            return False

        return True