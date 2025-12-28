


class APIClientError(Exception):
    """Исключение для ошибок при работе с API."""
    def __init__(self, message):
        super().__init__(message)