# providers/animedia/v0/qt_async_worker.py
import asyncio
import logging
from typing import Callable, Any
from PyQt6.QtCore import QThread, pyqtSignal


class AsyncWorker(QThread):
    """
    Запускает одну корутину в отдельном потоке и возвращает результат
    через сигнал `finished`. Ошибки передаются через сигнал `error`.
    """
    finished = pyqtSignal(object)   # будет передан объект‑результат
    error   = pyqtSignal(str)      # строка‑сообщение об ошибке

    def __init__(
        self,
        coro_func: Callable[..., Any],
        *coro_args,
        **coro_kwargs,
    ):
        """
        :param coro_func:   обычная (не‑awaited) функция, возвращающая корутину.
                            Например, ``adapter.get_by_title``.
        :param coro_args:   позиционные аргументы для ``coro_func``.
        :param coro_kwargs: именованные аргументы для ``coro_func``.
        """
        super().__init__()
        self.logger = logging.getLogger(__name__)
        self._coro_func = coro_func
        self._args = coro_args
        self._kw = coro_kwargs

    # ------------------------------------------------------------------
    # QThread API
    # ------------------------------------------------------------------
    def run(self) -> None:
        """
        Выполняется в отдельном OS‑потоке. Здесь создаём собственный
        asyncio‑loop, запускаем корутину и передаём результат в сигналы.
        """
        loop = None
        try:
            self.logger.info("Animedia async worker started…")
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            coro = self._coro_func(*self._args, **self._kw)
            result = loop.run_until_complete(coro)

            self.logger.info(
                f"Animedia async worker finished – got {len(result) if hasattr(result, '__len__') else 'a'} items"
            )
            self.finished.emit(result)

        except Exception as exc:
            self.logger.error(f"Animedia async worker error: {exc}", exc_info=True)
            self.error.emit(str(exc))

        finally:
            if loop is not None:
                loop.close()