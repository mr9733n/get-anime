# app/qt/app_services.py
from __future__ import annotations

import logging
import json
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass(slots=True)
class AppServices:
    # core infra
    logger: Any
    config: Any
    db: Any

    # ui/core controllers
    ui: Any
    playlist: Any

    # providers / api
    api: Any

    # misc/external
    http: Optional[Any] = None

    # state service (создаётся автоматически)
    state_service: Optional[AppStateService] = field(default=None, init=False)

    def __post_init__(self):
        """Инициализирует зависимые сервисы после создания."""
        self.state_service = AppStateService(self.db)

    def load_state(self) -> dict:
        """Делегирует в state_service."""
        return self.state_service.load_state()

    def save_state(self, app_state: dict) -> bool:
        """Делегирует в state_service."""
        return self.state_service.save_state(app_state)


class AppStateService:
    """Сервис для сохранения/загрузки состояния приложения."""

    def __init__(self, db_manager):
        self.logger = logging.getLogger(__name__)
        self.db_manager = db_manager

    def save_state(self, app_state: dict) -> bool:
        """Сохраняет состояние приложения."""
        try:
            if self.db_manager:
                self._save_state_to_db(app_state)
            self.logger.info("Состояние приложения успешно сохранено")
            return True
        except Exception as e:
            self.logger.error(f"Ошибка при сохранении состояния: {e}")
            return False

    def load_state(self) -> dict:
        """Загружает сохраненное состояние приложения."""
        try:
            state = self._load_state_from_db()
            if state:
                self.logger.info("Состояние приложения успешно загружено")
            return state or {}
        except Exception as e:
            self.logger.error(f"Ошибка при загрузке состояния: {e}")
            return {}

    def clear_state_in_db(self) -> bool:
        """Очищает сохраненное состояние в БД."""
        try:
            self.db_manager.state_manager.clear_app_state()
            self.logger.info("Состояние в БД очищено")
            return True
        except Exception as e:
            self.logger.error(f"Ошибка при сбросе состояния: {e}")
            return False

    # Алиас для совместимости
    clear_state = clear_state_in_db

    def _save_state_to_db(self, app_state: dict) -> bool:
        """Сохраняет состояние в базу данных."""
        try:
            state_items = [
                (key, json.dumps(value, ensure_ascii=False) if value is not None else None)
                for key, value in app_state.items()
            ]
            self.db_manager.state_manager.save_app_state(state_items)
            return True
        except Exception as e:
            self.logger.error(f"Ошибка при сохранении состояния в БД: {e}")
            return False

    def _load_state_from_db(self) -> dict:
        """Загружает состояние из базы данных."""
        try:
            state = self.db_manager.state_manager.load_app_state()

            # Конвертируем строки "null" в None
            for key, value in state.items():
                if isinstance(value, str) and value.lower() == "null":
                    state[key] = None

            return state
        except Exception as e:
            self.logger.error(f"Ошибка при загрузке состояния из БД: {e}")
            return {}