# example
import pathlib
import sys, logging, asyncio

from PyQt5.QtWidgets import (
    QApplication,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QLineEdit,
    QProgressBar,
)
from qasync import QEventLoop, asyncSlot
from animedia_client import AnimediaClient
from playlist_manager import Playlist
from net_client import NetClient
from config_manager import ConfigManager

logging.basicConfig(level=logging.INFO)

VLC_PATH = r"python mini_browser.py --socks http://192.168.0.100:8866 --file"
BASE_URL = "https://amedia.online"
MAX_TITLES = 5


class Main(QWidget):
    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger(__name__)
        self.setWindowTitle("Animedia Player (demo)")
        layout = QVBoxLayout(self)

        self.config_manager = ConfigManager(pathlib.Path('config/config.ini'))
        """Loads the configuration settings needed by the application."""
        network_config = self.config_manager.network
        self.net_client = NetClient(network_config)
        self.logger.info(f"Network client initialized. Proxy enabled: {network_config.proxy_enabled}")

        self.input = QLineEdit()
        self.input.setPlaceholderText("Введите название аниме")

        self.btn = QPushButton("Play")
        self.out = QTextEdit()
        self.out.setReadOnly(True)

        self.loader_bar = QProgressBar()
        self.loader_bar.setRange(0, 0)
        self.loader_bar.setVisible(False)
        layout.addWidget(self.loader_bar)

        layout.addWidget(self.input)
        layout.addWidget(self.btn)
        layout.addWidget(self.out)

        self.btn.clicked.connect(self.start_search)
        self.playlist_manager = Playlist()


    def _show_loader(self, show: bool):
        self.loader_bar.setVisible(show)


    def save_playlist_wrapper(self, discovered_links, sanitized_title):
        """
        Wrapper function to handle saving the playlists.
        Iterates through all discovered playlists and saves them.
        """
        if discovered_links:
            filename = self.playlist_manager.save_playlist(sanitized_title, discovered_links)
            print(f"Playlist for title {sanitized_title} was sent for saving with filename; {filename}.")
            return filename
        else:
            print(f"No links found for title {sanitized_title}, skipping saving.")
            return None


    @asyncSlot()
    async def start_search(self):
        self.btn.setEnabled(False)
        self._show_loader(True)
        adapter = AnimediaClient(base_url=BASE_URL, net_client=self.net_client)
        try:
            anime_name = self.input.text().strip()
            if not anime_name:
                self.out.append("⚠️ Введите название аниме")
                return
            links, title = await adapter.search_anime_and_collect(anime_name=anime_name, max_titles=MAX_TITLES)
            self.out.append("\n".join(links))
            playlist_filename = self.save_playlist_wrapper(links, title)
            self.playlist_manager.play_playlist(playlist_filename, VLC_PATH)
        except Exception as e:
            self.out.append(f"❌ {e}")
        finally:
            self.btn.setEnabled(True)
            self._show_loader(False)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)
    w = Main()
    w.show()
    with loop:
        loop.run_forever()
