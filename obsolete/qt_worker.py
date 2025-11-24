# qt_worker.py
import asyncio
from PyQt5.QtCore import QObject, pyqtSignal, QThread
from app.animedia.animedia_adapter import AnimediaAdapter

class Worker(QObject):
    finished = pyqtSignal(list)
    error   = pyqtSignal(str)

    def __init__(self, base_url: str, anime_name: str, max_titles: int = 5):
        super().__init__()
        self.base_url   = base_url
        self.anime_name = anime_name
        self.max_titles = max_titles

    def run(self):
        """Запускается в отдельном QThread."""
        try:
            adapter = AnimediaAdapter(self.base_url)

            async def coro():
                return await adapter.search_anime_and_collect(
                    anime_name=self.anime_name,
                    max_titles=self.max_titles,
                )

            links = asyncio.run(coro())
            self.finished.emit(links)
        except Exception as exc:
            self.error.emit(str(exc))
