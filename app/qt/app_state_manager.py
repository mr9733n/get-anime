# app_state_manager.py
import logging
import json


class AppStateManager:
    def __init__(self, db_manager):
        self.logger = logging.getLogger(__name__)
        self.db_manager = db_manager

    def save_state(self, app_state):
        """Сохраняет состояние приложения"""
        try:
            if self.db_manager:
                self.save_state_to_db(app_state)

            self.logger.info("Состояние приложения успешно сохранено")
            return True
        except Exception as e:
            self.logger.error(f"Ошибка при сохранении состояния: {e}")
            return False

    def load_state(self):
        """Загружает сохраненное состояние приложения"""
        try:
            state = self.load_state_from_db()

            self.logger.info("Состояние приложения успешно загружено")
            return state or {}
        except Exception as e:
            self.logger.error(f"Ошибка при загрузке состояния: {e}")
            return {}

    def save_state_to_db(self, app_state):
        """Сохраняет состояние в базу данных"""
        try:
            state_items = [(key, json.dumps(value, ensure_ascii=False)) for key, value in app_state.items()]
            self.db_manager.state_manager.save_app_state(state_items)
            return True
        except Exception as e:
            self.logger.error(f"Ошибка при сохранении состояния в БД: {e}")
            return False

    def load_state_from_db(self):
        """Загружает состояние из базы данных"""
        try:
            return self.db_manager.state_manager.load_app_state()
        except Exception as e:
            self.logger.error(f"Ошибка при загрузке состояния из БД: {e}")
            return {}

    def clear_state_in_db(self):
        """Очищает сохраненное состояние в БД"""
        try:
            return self.db_manager.state_manager.clear_app_state()

        except Exception as e:
            self.logger.error(f"Ошибка при сбросе состояния: {e}")
            return {}