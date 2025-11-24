# safe_qt_worker.py
import sys, asyncio, logging
from PyQt5.QtWidgets import QApplication, QPushButton, QTextEdit, QVBoxLayout, QWidget
from PyQt5.QtCore import QObject, pyqtSignal, QThread
from app.animedia.animedia_adapter import AnimediaAdapter

logging.basicConfig(level=logging.INFO)


class Worker(QObject):
    finished = pyqtSignal(list)
    error   = pyqtSignal(str)

    def __init__(self, base_url, anime_name, max_titles=5):
        super().__init__()
        self.base_url   = base_url
        self.anime_name = anime_name
        self.max_titles = max_titles

    def run(self):
        """Запускается в отдельном QThread → безопасно для asyncio.run."""
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


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Animedia search")
        layout = QVBoxLayout(self)

        self.btn = QPushButton("Поиск")
        self.out = QTextEdit()
        self.out.setReadOnly(True)

        layout.addWidget(self.btn)
        layout.addWidget(self.out)

        self.btn.clicked.connect(self.start_search)

    def start_search(self):
        # ---- создаём поток и воркера ----
        thread = QThread()
        worker = Worker(
            base_url="https://amedia.online/",
            anime_name="sanda",
            max_titles=5,
        )
        worker.moveToThread(thread)

        # сигналы → UI
        worker.finished.connect(lambda links: self.out.append("\n".join(links)))
        worker.error.connect(lambda msg: self.out.append(f"❌ {msg}"))

        # запуск
        thread.started.connect(worker.run)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)

        thread.start()


if __name__ == "__main__":
    # ---- Playwright‑требования ----
    # Убедитесь, что браузеры установлены:
    #   python -m playwright install chromium
    # Если используете Linux, проверьте наличие системных библиотек.
    app = QApplication(sys.argv)
    w = MainWindow()
    w.show()
    sys.exit(app.exec_())
