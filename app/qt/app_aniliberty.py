from app.qt.app_exceptions import APIClientError

PROVIDER_ANILIBERTY = "aniliberty"


def fetch_and_process_schedule(self, day_of_week):
    """
    Получает и обрабатывает расписание с сервера.
    Args:
        day_of_week (int): День недели.
    Returns:
        tuple: (bool, set) Успешность операции и набор title_ids.
    """
    try:
        data = self.get_schedule(day_of_week)
        if data is None:
            self.logger.warning(f"No data available for day {day_of_week}.")
            return False, None

        titles_list = []
        for item in data:
            titles = item.get("list", [])
            titles_list.extend(titles)

        self.logger.debug(f"Total titles (light): {len(titles_list)}")
        ids = [t.get('external_id') for t in titles_list if t.get('external_id') is not None]
        if ids:
            full_list = self.api_adapter.get_releases_full(ids, max_workers=4)
            if full_list:
                self.logger.debug(f"Full bundles fetched: {len(full_list)} (parallel)")
                new_title_ids = self._save_titles_list(full_list)
            else:
                # fallback:
                new_title_ids = self._save_titles_list(titles_list)
        else:
            new_title_ids = self._save_titles_list(titles_list)

        parsed_data = self.parse_schedule_data(data, new_title_ids)
        self.logger.debug(f"Parsed data: {parsed_data}")
        self._save_parsed_data(parsed_data)

        return True, new_title_ids
    except Exception as e:
        self.logger.error(f"Error while fetching and processing schedule: {e}")
        return False, None

def check_and_update_schedule(self, day_of_week, current_titles):
    """
    Проверяет наличие обновлений в расписании и обновляет базу данных.
    Args:
        day_of_week (int): День недели.
        current_titles (set): Текущий набор title_ids.

    Returns:
        tuple: (bool, set) Успешность операции и набор обновленных title_ids.
    """
    try:
        self.ui_manager.show_loader("Updating schedule...")
        self.ui_manager.set_buttons_enabled(False)
        status, new_title_ids = self.fetch_and_process_schedule(day_of_week)
        if not status:
            return False, None

        if current_titles:
            titles_to_remove = current_titles.difference(new_title_ids)
            if titles_to_remove:
                self.logger.debug(f"Titles to remove: {titles_to_remove}")
                self.db_manager.remove_schedule_day(titles_to_remove, day_of_week)
            else:
                self.logger.debug(f"No updates required: {current_titles} == {new_title_ids}")

        return True, new_title_ids
    except Exception as e:
        self.logger.error(f"Error while checking and updating schedule: {e}")
        return False, None
    finally:
        self.ui_manager.hide_loader()
        self.ui_manager.set_buttons_enabled(True)

def get_random_title(self):
    try:
        self.ui_manager.show_loader("Fetching random title...")
        self.ui_manager.set_buttons_enabled(False)

        data = self.api_adapter.get_random_title()

        if not isinstance(data, dict):
            self.logger.error(f"Unexpected response format: {type(data).__name__}")
            self.show_error_notification("API Error", "Unexpected response format.")
            return

        if 'error' in data:
            self.logger.error(data['error'])
            self.show_error_notification("API Error", data['error'])
            return

        self.logger.debug(f"Full response data: {len(data)} keys (type: {type(data).__name__})")

        title_list = data.get('list', [])
        if not title_list:
            self.logger.error("No titles found in the response.")
            self.show_error_notification("Error", "No titles found in the response.")
            return

        internal_ids = self.invoke_database_save(title_list)
        title_id = internal_ids[0] if internal_ids else None
        if title_id is None:
            self.logger.error("Title ID not found in response.")
            self.show_error_notification("Error", "Title ID not found in response.")
            return

        self.display_info(title_id)
        self.current_data = data

    except Exception as e:
        self.logger.error(f"Error while fetching random title: {e}")
        self.show_error_notification("Error", "Unexpected error. Check logs for details.")
        return False, None
    finally:
        self.ui_manager.hide_loader()
        self.ui_manager.set_buttons_enabled(True)

def parse_schedule_data(self, data, title_ids):
    """Парсит расписание и возвращает список {day, title_id}."""
    parsed_data = []
    if not isinstance(data, list):
        self.logger.error(f"Ожидался список, получен: {type(data).__name__}")
        return parsed_data

    for day_info in data:
        if not isinstance(day_info, dict):
            self.logger.error(
                f"Неправильный формат данных: ожидался словарь, получен {type(day_info).__name__}"
            )
            continue

        day = day_info.get("day")
        title_list = day_info.get("list", [])

        if not isinstance(title_list, list):
            self.logger.error(
                f"Неправильный формат 'list': ожидался список, получен {type(title_list).__name__}"
            )
            continue

        for title in title_list:
            if not isinstance(title, dict):
                continue

            external_id = title.get("external_id")
            if not external_id:
                continue
            title_db = self.db_manager.get_title_by_external_id(PROVIDER_ANILIBERTY, external_id)
            internal_title_id = title_db.title_id

            if internal_title_id:
                parsed_data.append({"day": day, "title_id": internal_title_id})
            else:
                self.logger.warning(
                    f"Не найден title_id для external_id={external_id} (day={day})"
                )

    return parsed_data


def get_schedule(self, day):
    """
    Получает расписание с сервера API.
    Args:
        day (int): День недели для запроса.
    Returns:
        list: Данные расписания.
    Raises:
        APIClientError: Если произошла ошибка при запросе или обработке данных.
    """
    try:
        data = self.api_adapter.get_schedule(day)
        if data is None:
            raise APIClientError(f"No data returned for day {day}.")
        if isinstance(data, dict) and 'error' in data:
            raise APIClientError(f"API returned an error: {data['error']}")

        self.logger.debug(f"Data received for day {day}: {len(data)} keys (type: {type(data).__name__})")
        self.current_data = data
        return data
    except APIClientError as api_error:
        self.logger.error(f"API Client Error: {api_error}")
        self.show_error_notification("API Error", str(api_error)) # Показываем ошибку пользователю
        return None
    except Exception as e:
        self.logger.error(f"Unexpected error while fetching schedule: {e}")
        self.show_error_notification("Error", "Unexpected error. Check logs for details.")
        return None