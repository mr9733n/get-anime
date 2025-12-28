# app/qt/app_exceptions.py
from __future__ import annotations


class APIClientError(Exception):
    """Исключение для ошибок при работе с API."""
    def __init__(self, message):
        super().__init__(message)