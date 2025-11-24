# example
import sys, logging, asyncio

from PyQt5.QtWidgets import (
    QApplication,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QLineEdit,
)
from qasync import QEventLoop, asyncSlot
from app.animedia.animedia_adapter import AnimediaAdapter

logging.basicConfig(level=logging.INFO)


class Main(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Animedia (qasync)")
        layout = QVBoxLayout(self)

        self.input = QLineEdit()
        self.input.setPlaceholderText("Введите название аниме")

        self.btn = QPushButton("Поиск")
        self.out = QTextEdit()
        self.out.setReadOnly(True)

        layout.addWidget(self.input)
        layout.addWidget(self.btn)
        layout.addWidget(self.out)

        self.btn.clicked.connect(self.start_search)

    @asyncSlot()
    async def start_search(self):
        adapter = AnimediaAdapter(
            base_url="https://amedia.online/",
        )
        try:
            anime_name = self.input.text().strip()
            if not anime_name:
                self.out.append("⚠️ Введите название аниме")
                return
            links = await adapter.search_anime_and_collect(
                anime_name=anime_name,
                max_titles=5,
            )
            self.out.append("\n".join(links))
        except Exception as e:
            self.out.append(f"❌ {e}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)
    w = Main()
    w.show()
    with loop:
        loop.run_forever()
