import sys
import os
import argparse
from typing import Iterable, List

# --- Автоопределение: PyQt6 или PyQt5 --- #

QT_VERSION = None  # "PyQt6" или "PyQt5"

try:
    from PyQt6.QtCore import QUrl
    from PyQt6.QtWidgets import QApplication, QMainWindow, QTabWidget
    from PyQt6.QtWebEngineWidgets import QWebEngineView

    QT_VERSION = "PyQt6"
except Exception:
    try:
        from PyQt5.QtCore import QUrl
        from PyQt5.QtWidgets import QApplication, QMainWindow, QTabWidget
        from PyQt5.QtWebEngineWidgets import QWebEngineView
        QT_VERSION = "PyQt5"
    except Exception as e:
        print(
            "[!] Не удалось импортировать ни PyQt6(+WebEngine), ни PyQt5(+WebEngine).\n"
            f"    Ошибка: {e}\n"
            "    Установи один из вариантов (внутри venv):\n"
            "    - python -m pip install PyQt5 PyQtWebEngine\n"
            "      или\n"
            "    - python -m pip install PyQt6 PyQt6-WebEngine"
        )
        sys.exit(1)


class BrowserWindow(QMainWindow):
    def __init__(self, urls: Iterable[str]):
        super().__init__()

        self.setWindowTitle(f"Mini Qt Browser ({QT_VERSION})")
        self.resize(1024, 768)

        self.tabs = QTabWidget(self)
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self.on_tab_close)
        self.setCentralWidget(self.tabs)

        # очередь ссылок; открываем их по одной
        self.url_queue: List[str] = [u for u in urls if u.strip()]

    def start(self):
        """Открыть первую вкладку из очереди."""
        self.open_next_tab()

    def normalize_url(self, url: str) -> str:
        url = url.strip()
        if not url:
            return "https://example.com"

        if not (url.startswith("http://") or url.startswith("https://")):
            url = "https://" + url
        return url

    def add_tab(self, url: str):
        url = self.normalize_url(url)

        view = QWebEngineView(self)
        view.setUrl(QUrl(url))

        idx = self.tabs.addTab(view, url)
        self.tabs.setCurrentIndex(idx)

    def open_next_tab(self):
        """Взять следующую ссылку из очереди и открыть её во вкладке."""
        if not self.url_queue:
            return
        next_url = self.url_queue.pop(0)
        self.add_tab(next_url)

    def on_tab_close(self, index: int):
        widget = self.tabs.widget(index)
        if widget is not None:
            self.tabs.removeTab(index)
            widget.deleteLater()

        # если ещё есть ссылки в очереди – открываем следующую
        if self.url_queue:
            self.open_next_tab()
        else:
            # если вкладок больше нет – закрываем окно
            if self.tabs.count() == 0:
                self.close()


def parse_args():
    parser = argparse.ArgumentParser(
        description="Простой Qt-браузер с прокси и файлом ссылок (по одной вкладке за раз)"
    )

    parser.add_argument(
        "--socks",
        help=(
            "Прокси в формате host:port, socks5://host:port или http://host:port. "
            "Название параметра историческое, можно передавать и http-прокси."
        ),
        default=None,
    )

    parser.add_argument(
        "--file",
        help="Путь к текстовому файлу со списком ссылок (одна ссылка на строку)",
        default=None,
    )

    parser.add_argument(
        "urls",
        nargs="*",
        help="Ссылки (одна или несколько)",
    )
    return parser.parse_args()


def load_urls_from_file(path: str) -> list[str]:
    if not os.path.exists(path):
        print(f"[!] Файл не найден: {path}")
        return []

    urls: list[str] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            s = line.strip()
            if not s:
                continue
            if s.startswith("#"):
                continue
            urls.append(s)

    return urls


def setup_proxy(proxy: str | None):
    if not proxy:
        return

    p = proxy.strip()

    # если схемы нет – считаем, что это socks5
    if "://" not in p:
        p = "socks5://" + p

    # На этом уровне нам всё равно, socks или http – Chromium сам разберётся по схеме.
    proxy_flag = f"--proxy-server={p}"

    existing_flags = os.environ.get("QTWEBENGINE_CHROMIUM_FLAGS", "")
    if existing_flags:
        new_flags = existing_flags + " " + proxy_flag
    else:
        new_flags = proxy_flag

    os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = new_flags
    # Для отладки можно раскомментировать:
    # print("QTWEBENGINE_CHROMIUM_FLAGS =", os.environ["QTWEBENGINE_CHROMIUM_FLAGS"])


def main():
    args = parse_args()

    setup_proxy(args.socks)

    urls = list(args.urls)

    if args.file:
        urls_from_file = load_urls_from_file(args.file)
        urls.extend(urls_from_file)

    if not urls:
        urls = ["https://example.com"]

    app = QApplication(sys.argv)
    window = BrowserWindow(urls)
    window.start()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
