# utils/qt_async_worker.py
import asyncio
from PyQt5.QtCore import QThread, pyqtSignal

class AsyncWorker(QThread):
    """
    Запускает одну корутину в отдельном потоке и возвращает результат
    через сигнал `finished`.
    """
    finished = pyqtSignal(object)          # будет передан объект‑результат
    error   = pyqtSignal(str)              # строка‑сообщение об ошибке

    def __init__(self, coro, *coro_args, **coro_kwargs):
        super().__init__()
        self._coro = coro
        self._args = coro_args
        self._kw   = coro_kwargs

    def run(self):
        try:
            result = asyncio.run(self._coro(*self._args, **self._kw))
            self.finished.emit(result)
        except Exception as exc:            # любые исключения – в UI‑лог
            self.error.emit(str(exc))
