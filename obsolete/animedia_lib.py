# main_window.py
from PyQt5.QtWidgets import QApplication, QPushButton, QTextEdit, QVBoxLayout, QWidget
from PyQt5.QtCore import QThread
from qt_worker import Worker

app = QApplication([])

win = QWidget()
layout = QVBoxLayout(win)

btn = QPushButton("Поиск")
out = QTextEdit()
out.setReadOnly(True)

layout.addWidget(btn)
layout.addWidget(out)

def start_search():
    # создаём отдельный поток и объект‑работник
    thread = QThread()
    worker = Worker(
        base_url="https://amedia.online/",
        anime_name="sanda",
        max_titles=5,
    )
    worker.moveToThread(thread)

    # соединяем сигналы
    worker.finished.connect(lambda links: out.append("\n".join(links)))
    worker.error.connect(lambda msg: out.append(f"❌ {msg}"))
    thread.started.connect(worker.run)

    # после завершения убираем поток
    worker.finished.connect(thread.quit)
    worker.finished.connect(worker.deleteLater)
    thread.finished.connect(thread.deleteLater)

    thread.start()

btn.clicked.connect(start_search)

win.show()
app.exec_()
