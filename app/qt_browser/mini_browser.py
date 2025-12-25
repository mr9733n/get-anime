import logging
import sys
import os
import argparse
import tempfile
from typing import Iterable, List, Optional

QT_VERSION = None  # "PyQt6" или "PyQt5"

try:
    from PyQt6.QtCore import QUrl
    from PyQt6.QtWidgets import (
        QApplication, QMainWindow, QTabWidget,
        QWidget, QVBoxLayout, QLineEdit, QListWidget, QListWidgetItem,
        QLabel, QPushButton, QHBoxLayout, QFileDialog, QMessageBox
    )
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    QT_VERSION = "PyQt6"
except Exception:
    try:
        from PyQt5.QtCore import QUrl
        from PyQt5.QtWidgets import (
            QApplication, QMainWindow, QTabWidget,
            QWidget, QVBoxLayout, QLineEdit, QListWidget, QListWidgetItem,
            QLabel, QPushButton, QHBoxLayout, QFileDialog, QMessageBox
        )
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

logger = logging.getLogger("mini_browser")
logger.setLevel(logging.INFO)
logger.propagate = False  # важно!

_log_path = os.path.join(tempfile.gettempdir(), "mini_browser.log")

# чистим старые handlers (чтобы не копились при перезапусках)
for h in list(logger.handlers):
    logger.removeHandler(h)

fh = logging.FileHandler(_log_path, encoding="utf-8")
fh.setLevel(logging.INFO)
fh.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
logger.addHandler(fh)

logger.info("mini_browser started; log_file=%s", _log_path)

DEBUG_UI = False

def load_urls_from_file(path: str) -> list[str]:
    if not path:
        return []
    if not os.path.exists(path):
        print(f"[mini_browser] file not found: {path}")
        return []

    urls: list[str] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            urls.append(s)
#    print(f"[mini_browser] file found: {path}")
#    print(f"[mini_browser] urls list found: {urls}")
    return urls


class BrowserWindow(QMainWindow):
    def __init__(self, urls: Iterable[str], *, show_list_tab: bool, initial_file: Optional[str] = None):
        super().__init__()
        self.setWindowTitle(f"Mini Qt Browser ({QT_VERSION})")
        self.resize(1100, 800)

        self.tabs = QTabWidget(self)
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self.on_tab_close)
        self.setCentralWidget(self.tabs)

        self.all_urls: List[str] = [u.strip() for u in urls if isinstance(u, str) and u.strip()]
        self.show_list_tab = show_list_tab
        self.initial_file = initial_file

        # Links tab state
        self._list_widget: Optional[QListWidget] = None
        self._search: Optional[QLineEdit] = None
        self._status: Optional[QLabel] = None
        self._list_tab_index: Optional[int] = None

    @staticmethod
    def normalize_url_for_open(url: str) -> str:
        url = (url or "").strip()
        if not url:
            return ""
        if not (url.startswith("http://") or url.startswith("https://")):
            url = "https://" + url
        return url

    def add_tab(self, url: str):
        url = self.normalize_url_for_open(url)
        if not url:
            return

        view = QWebEngineView(self)
        view.setUrl(QUrl(url))

        title = url if len(url) <= 70 else (url[:67] + "...")
        idx = self.tabs.addTab(view, title)
        self.tabs.setTabToolTip(idx, url)
        self.tabs.setCurrentIndex(idx)

    # ---------- Links tab ----------

    def _add_links_tab(self, urls: List[str], file_hint: Optional[str] = None):
        logger.info(f"=== _add_links_tab called: len(urls)={len(urls)}, file_hint={file_hint}")

        w = QWidget(self)
        layout = QVBoxLayout(w)

        header_row = QHBoxLayout()
        header = QLabel("Links", w)
        header_row.addWidget(header)
        header_row.addStretch(1)

        btn_load = QPushButton("Load file…", w)
        btn_load.clicked.connect(self._on_load_file_clicked)
        header_row.addWidget(btn_load)
        layout.addLayout(header_row)

        self._status = QLabel("", w)
        self._status.setMinimumHeight(22)
        self._status.setStyleSheet("color: #333; font-weight: bold;")
        layout.addWidget(self._status)

        self._search = QLineEdit(w)
        self._search.setPlaceholderText("Search…")
        self._search.textChanged.connect(self._apply_filter)
        layout.addWidget(self._search)

        self._list_widget = QListWidget(w)
        logger.info(f"=== list_widget created: {self._list_widget is not None}")

        self._status.setStyleSheet("color: #444;")
        self._list_widget.setStyleSheet("""
        QListWidget { background: white; color: black; font-size: 11pt; }
        QListWidget::item { padding: 1px 2px; }
        QListWidget::item:selected { background: #cce8ff; color: black; }
        """)

        self._list_widget.setAlternatingRowColors(True)
        self._list_widget.itemDoubleClicked.connect(self._open_selected_item)
        self._list_widget.setUniformItemSizes(True)
        self._list_widget.setSpacing(2)
        self._list_widget.setWordWrap(True)
        f = self._list_widget.font()
        f.setPointSize(11)
        self._list_widget.setFont(f)

        # Добавляем в layout ПЕРЕД repaint
        layout.addWidget(self._list_widget)

        btn_row = QHBoxLayout()
        btn_open = QPushButton("Open", w)
        btn_open.clicked.connect(self._open_selected_item)
        btn_row.addWidget(btn_open)

        btn_remove = QPushButton("Remove", w)
        btn_remove.clicked.connect(self._remove_selected_item)
        btn_row.addWidget(btn_remove)
        layout.addLayout(btn_row)

        # Обновляем UI уже после добавления в layout
        self._status.repaint()
        self._list_widget.repaint()

        logger.info(f"=== Before _rebuild_list: widget={self._list_widget is not None}")
        self._rebuild_list(urls, file_hint=file_hint)
        logger.info(f"=== After _rebuild_list")

        self._list_tab_index = self.tabs.addTab(w, "Links")
        self.tabs.setCurrentIndex(self._list_tab_index)

    def _rebuild_list(self, urls: List[str], file_hint: Optional[str] = None):
        logger.info(f"=== _rebuild_list ENTRY: widget={self._list_widget is not None}, len(urls)={len(urls)}")

        # ВАЖНО: в PyQt используем "is None", а не "if not widget"!
        if self._list_widget is None:
            logger.error("=== _rebuild_list EXIT: widget is None!")
            return

        logger.info(f"=== _rebuild_list: widget exists, clearing")
        self._list_widget.clear()

        added = 0
        for u in urls:
            s = (u or "").strip()
            if not s:
                continue
            logger.info(f"=== Adding item: {s[:50]}...")
            item = QListWidgetItem(s)
            item.setToolTip(s)
            self._list_widget.addItem(item)
            added += 1

        count_now = self._list_widget.count()
        logger.info(f"=== _rebuild_list: added={added}, count_now={count_now}")

        src = f" • {os.path.basename(file_hint)}" if file_hint else ""
        self._status.setText(f"{added} links{src}")

        if self._status is not None:
            self._status.setText(f"Loaded: {added} | Widget count: {count_now}{src}")

        if DEBUG_UI:
            QMessageBox.information(
                self,
                "DEBUG _rebuild_list",
                f"added={added}\ncount_now={count_now}\nfile_hint={file_hint}\nfirst={urls[0] if urls else None}"
            )

        logger.info("rebuild_list: added=%s count=%s file=%s first=%s",
                    added, count_now, file_hint, (urls[0] if urls else None))
        logger.info(f"[mini_browser] widget count now: {self._list_widget.count()}")

    def start(self):
        logger.info(f"=== start() called: initial_file={self.initial_file}")

        if self.initial_file:
            try:
                if os.path.exists(self.initial_file):
                    logger.info(f"=== Loading file: {self.initial_file}")
                    self.all_urls = load_urls_from_file(self.initial_file)
                    logger.info(f"=== Loaded {len(self.all_urls)} URLs from file")
                else:
                    logger.warning(f"=== File does not exist: {self.initial_file}")
                self.show_list_tab = True
            except Exception as e:
                logger.error(f"=== Exception loading file: {e}", exc_info=True)
                self.show_list_tab = True

        logger.info(f"=== show_list_tab={self.show_list_tab}, len(all_urls)={len(self.all_urls)}")

        if self.show_list_tab:
            self._add_links_tab(self.all_urls, file_hint=self.initial_file)
        else:
            if self.all_urls:
                self.add_tab(self.all_urls[0])
            else:
                self._add_links_tab([], file_hint=self.initial_file)

    def _apply_filter(self, text: str):
        if self._list_widget is None:
            return
        q = (text or "").strip().lower()
        for i in range(self._list_widget.count()):
            it = self._list_widget.item(i)
            it.setHidden(bool(q) and q not in it.text().lower())

    def _get_selected_url(self) -> Optional[str]:
        if self._list_widget is None:
            return None
        it = self._list_widget.currentItem()
        return it.text() if it else None

    def _open_selected_item(self, *_):
        url = self._get_selected_url()
        if url:
            self.add_tab(url)

    def _remove_selected_item(self):
        if self._list_widget is None:
            return
        row = self._list_widget.currentRow()
        if row >= 0:
            self._list_widget.takeItem(row)
            if self._status is not None:
                self._status.setText(f"Links: {self._list_widget.count()}")

    def _on_load_file_clicked(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open links file",
            "playlists/",
            "Links (*.urls *.txt);;All files (*)",
        )
        if not path:
            return

        urls = load_urls_from_file(path)
        logger.info(f"[mini_browser] loaded file: {path} | lines={len(urls)}")

        if not urls:
            QMessageBox.information(self, "Links", "No links found in the selected file.")
        self.all_urls = urls
        self._rebuild_list(urls, file_hint=path)

    # ---------- Tabs close ----------

    def on_tab_close(self, index: int):
        # Не закрываем таб списка
        if self._list_tab_index is not None and index == self._list_tab_index:
            return

        widget = self.tabs.widget(index)
        if widget is not None:
            self.tabs.removeTab(index)
            widget.deleteLater()

        if self.tabs.count() == 0:
            self.close()


def parse_args():
    parser = argparse.ArgumentParser(
        description="Mini Qt browser: open URLs and/or show a links list tab"
    )
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    parser.add_argument("--socks", default=None)
    parser.add_argument("--file", default=None)
    parser.add_argument("urls", nargs="*")
    return parser.parse_args()


def setup_proxy(proxy: Optional[str]):
    if not proxy:
        return

    p = proxy.strip()
    if "://" not in p:
        p = "socks5://" + p

    proxy_flag = f"--proxy-server={p}"
    existing_flags = os.environ.get("QTWEBENGINE_CHROMIUM_FLAGS", "")
    os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = (existing_flags + " " + proxy_flag).strip()


def main():
    args = parse_args()
    setup_proxy(args.socks)

    if args.debug:
        logger.setLevel(logging.DEBUG)
        fh.setLevel(logging.DEBUG)
        DEBUG_UI = True

    urls: list[str] = []
    from_file = False

    if args.file:
        from_file = True
        urls_from_file = load_urls_from_file(args.file)
        logger.info(f"[mini_browser] args.file={args.file} | lines={len(urls_from_file)}")
        urls.extend(urls_from_file)

    urls.extend(list(args.urls))
    urls = [u for u in urls if isinstance(u, str) and u.strip()]

    # show Links если был файл или ссылок != 1
    show_list_tab = from_file or (len(urls) != 1)

    app = QApplication(sys.argv)
    window = BrowserWindow(urls, show_list_tab=show_list_tab, initial_file=args.file)
    window.start()
    window.show()

    # PyQt6: exec(), PyQt5: exec_()
    if QT_VERSION == "PyQt6":
        sys.exit(app.exec())
    else:
        sys.exit(app.exec_())


if __name__ == "__main__":
    main()
