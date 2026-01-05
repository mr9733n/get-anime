# app/qt/ui_helpers.py
"""
UI хелперы для контроллеров.
Убирают boilerplate код show_loader/hide_loader/set_buttons_enabled.
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING, Generator, Callable, Any
import logging

if TYPE_CHECKING:
    from app.qt.protocols import IUIManager

logger = logging.getLogger(__name__)


@contextmanager
def ui_operation(
        ui: IUIManager,
        message: str = "Loading...",
        *,
        disable_buttons: bool = True,
) -> Generator[None, None, None]:
    """
    Контекстный менеджер для UI операций с loader.

    Автоматически:
    - Показывает loader с сообщением
    - Блокирует кнопки (опционально)
    - Скрывает loader и разблокирует кнопки в finally

    Args:
        ui: UI manager с методами show_loader/hide_loader/set_buttons_enabled
        message: Сообщение для loader
        disable_buttons: Блокировать ли кнопки (default: True)

    Usage:
        with ui_operation(self.ui, "Fetching titles..."):
            data = self.api.get_titles()
            self.display.show(data)

    Example with error handling:
        try:
            with ui_operation(self.ui, "Searching..."):
                results = self.search(query)
        except APIError as e:
            self.display.show_error("Search failed", str(e))
    """
    try:
        ui.show_loader(message)
        if disable_buttons:
            ui.set_buttons_enabled(False)
        yield
    finally:
        ui.hide_loader()
        if disable_buttons:
            ui.set_buttons_enabled(True)


@contextmanager
def ui_operation_async(
        ui: IUIManager,
        message: str = "Loading...",
        *,
        on_complete: Callable[[], None] | None = None,
) -> Generator[None, None, None]:
    """
    Контекстный менеджер для async операций.

    В отличие от ui_operation, НЕ скрывает loader в finally —
    это должен сделать callback асинхронной операции.

    Args:
        ui: UI manager
        message: Сообщение для loader
        on_complete: Callback для вызова при завершении (опционально)

    Usage:
        with ui_operation_async(self.ui, "Loading..."):
            self._start_async_worker(callback=self._on_complete)

        # loader скроется в _on_complete
    """
    try:
        ui.show_loader(message)
        ui.set_buttons_enabled(False)
        yield
    except Exception:
        # При ошибке до запуска async — скрываем loader
        ui.hide_loader()
        ui.set_buttons_enabled(True)
        raise


def cleanup_ui(ui: IUIManager) -> None:
    """
    Утилита для очистки UI состояния.
    Используется в finally блоках async callbacks.
    """
    ui.hide_loader()
    ui.set_buttons_enabled(True)


class UIOperationGuard:
    """
    Класс-guard для более сложных сценариев.

    Позволяет вручную контролировать момент завершения.

    Usage:
        guard = UIOperationGuard(self.ui, "Processing...")
        guard.start()

        try:
            # async operation...
            self._worker.finished.connect(lambda: guard.finish())
        except:
            guard.finish()
            raise
    """

    def __init__(
            self,
            ui: IUIManager,
            message: str = "Loading...",
            *,
            disable_buttons: bool = True,
    ):
        self._ui = ui
        self._message = message
        self._disable_buttons = disable_buttons
        self._started = False

    def start(self) -> None:
        """Начинает операцию — показывает loader."""
        if self._started:
            return
        self._started = True
        self._ui.show_loader(self._message)
        if self._disable_buttons:
            self._ui.set_buttons_enabled(False)

    def finish(self) -> None:
        """Завершает операцию — скрывает loader."""
        if not self._started:
            return
        self._started = False
        self._ui.hide_loader()
        if self._disable_buttons:
            self._ui.set_buttons_enabled(True)

    def __enter__(self) -> UIOperationGuard:
        self.start()
        return self

    def __exit__(self, *args) -> None:
        self.finish()