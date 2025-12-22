# providers/animedia//qt_async_worker.py
import asyncio
import logging
from typing import Callable, Any
from PyQt5.QtCore import QThread, pyqtSignal


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
        try:
            self.logger.info("Animedia async worker started…")
            # каждый поток получает свой цикл
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            # получаем корутину (не вызываем её сразу, иначе будет сразу
            # выполнен sync‑код внутри)
            coro = self._coro_func(*self._args, **self._kw)

            result = loop.run_until_complete(coro)
            self.logger.info(
                f"Animedia async worker finished – got {len(result) if hasattr(result, '__len__') else 'a'} items"
            )
            self.finished.emit(result)

        except Exception as exc:          # любые исключения – в UI‑лог
            self.logger.error(f"Animedia async worker error: {exc}")
            self.error.emit(str(exc))

        finally:
            # важно закрыть цикл, иначе будет утечка ресурсов
            loop.close()
