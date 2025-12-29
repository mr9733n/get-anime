import pathlib
import sys
import logging

from pathlib import Path
from PyQt5.QtWidgets import QWidget, QTextBrowser, QApplication
from PyQt5.QtCore import QThreadPool, pyqtSlot, pyqtSignal, QSharedMemory

from app.qt.app_services import AppServices

from app.qt.controllers.actions import ActionsController
from app.qt.controllers.animedia import AniMediaController
from app.qt.controllers.aniliberty import AniLibertyController
from app.qt.controllers.persistence import PersistenceController
from app.qt.controllers.callback import CallbackController
from app.qt.controllers.display import DisplayController
from app.qt.controllers.torrents import TorrentController
from app.qt.controllers.bootstrap import BootstrapController
from app.qt.controllers.state_runtime import StateRuntimeController
from app.qt.controllers.posters import PosterController
from app.qt.controllers.players import PlayerController

from app.qt.app_handlers import LinkActionHandler
from app.qt.ui_am_generator import UIAMGenerator
from app.qt.ui_manger import UIManager
from app.qt.ui_generator import UIGenerator
from app.qt.ui_s_generator import UISGenerator
from static.layout_metadata import all_layout_metadata

from providers.aniliberty.v1.api import APIClient
from providers.aniliberty.v1.adapter import APIAdapter
from providers.animedia.v0.cache_manager import AniMediaCacheManager, AniMediaCacheConfig
from providers.animedia.v0 import create_adapter
from utils.config.config_manager import ConfigManager
from utils.downloads.poster_manager import PosterManager
from utils.downloads.torrent_manager import TorrentManager
from utils.playlists.playlist_manager import PlaylistManager
from utils.integrations.open_router import OpenRouter
from utils.net.net_client import NetClient
from utils.net.url_resolve_service import UrlResolveService
from utils.net.url_resolver import TTLCache
from utils.net.url_resolver_config import ResolverConfig


class AnimePlayerAppVer3(QWidget):
    add_title_browser_to_layout = pyqtSignal(QTextBrowser, int, int)
    state_changed = pyqtSignal()

    def __init__(self, db_manager, version, template_name, prod_key=None):
        super().__init__()
        self.logger = logging.getLogger(__name__)
        self.prod_key = prod_key
        if prod_key is not None:
            unique_key = str(prod_key) + '-APA'
            self.shared_memory = QSharedMemory(unique_key)
            if not self.shared_memory.create(1):
                self.logger.error("Main application is already running!")
                sys.exit(1)

        self.thread_pool = QThreadPool()  # Пул потоков для управления задачами
        self.thread_pool.setMaxThreadCount(4)
        self.thread_pool.setExpiryTimeout(30_000)
        self.mpv_window = None
        self.view_state = None
        self.am_total_count = None
        self.current_show_mode = None
        self.error_label = None
        self.tray_icon = None
        self._animedia_worker = None
        self.current_title_ids = None
        self.current_day_of_week = None
        self.current_title_id = None
        self.vlc_window = None
        self.quality_dropdown = None
        self.playlist_filename = None
        self.current_data = None
        self.current_link = None
        self.poster_container = None
        self.scroll_area = None
        self.posters_layout = None
        self.title_search_entry = None
        self.current_titles = None
        self.selected_quality = None
        self._last_search_text = None
        self.stream_video_url = None
        self.discovered_links = []
        self.sanitized_titles = []
        self.title_names = []
        self.total_titles = []
        self.playlists = {}

        self.current_template = template_name
        self.logger.info(f"Используется шаблон: {self.current_template}")
        self.app_version = version
        self.logger.debug(f"Starting AnimePlayerApp Version {self.app_version}..")
        self.row_start = 0
        self.col_start = 0
        self.pre = "https://"
        self.config_manager = ConfigManager(pathlib.Path('config/config.ini'))
        self.bootstrap = BootstrapController(self, None)

        """Loads the configuration settings needed by the application."""
        network_config = self.config_manager.network
        self.net_client = NetClient(network_config)
        self.logger.info(f"Network client initialized. Proxy enabled: {network_config.proxy_enabled}")
        self.url_resolver = UrlResolveService(
            net=self.net_client,
            cache=TTLCache(max_items=2048),
            cfg=ResolverConfig(),
        )

        self.base_al_url = self.config_manager.get_setting('Settings', 'base_al_url')
        self.base_am_url = self.config_manager.get_setting('Settings', 'base_am_url')
        self.al_api_version = self.config_manager.get_setting('Settings', 'al_api_version')

        self.titles_batch_size = int(self.config_manager.get_setting('Settings', 'titles_batch_size'))
        self.titles_list_batch_size = int(self.config_manager.get_setting('Settings', 'titles_list_batch_size'))
        self.current_offset = int(self.config_manager.get_setting('Settings', 'current_offset'))
        self.num_columns = int(self.config_manager.get_setting('Settings', 'num_columns'))
        self.user_id = int(self.config_manager.get_setting('Settings', 'user_id'))
        self.default_rating_name = self.config_manager.get_setting('Settings', 'default_rating_name')

        # vlc_player
        self.use_libvlc = self.get_cfg('Settings', 'use_libvlc', "false", lower=True)
        self.log_enabled = self.get_cfg('VlcPlayer', 'log_enabled', "false", lower=True)
        self.verbose = self.get_cfg('VlcPlayer', 'verbose_level', "2")
        # network
        self.proxy_enabled = self.get_cfg('Network', 'proxy_enabled', "false", lower=True)
        self.proxy_url = self.get_cfg('Network', 'proxy_url', None)
        # mpv‑related
        self.use_mpv_player = self.get_cfg('Settings', 'use_mpv_player', "false", lower=True)
        self.mpv_player_executable_name = self.get_cfg('MpvPlayer', 'executable_name', "mpv_player.exe")
        self.mpv_log_enabled = self.get_cfg('MpvPlayer', 'log_enabled', "false", lower=True)
        self.mpv_verbose = self.get_cfg('MpvPlayer', 'verbose_level', "info")

        self.torrent_save_path = pathlib.Path("torrents/")  # Ensure this is set correctly
        self.video_player_path, self.torrent_client_path = self.setup_paths()

        self.temp_dir = "temp"

        self.animedia_cache_cfg = AniMediaCacheConfig(base_dir=Path(self.temp_dir))
        self.animedia_cache = AniMediaCacheManager(self.animedia_cache_cfg.base_dir)
        self.animedia_adapter = create_adapter(
            base_url=self.base_am_url,
            net_client=self.net_client,
            cache_dir=Path(self.temp_dir),
            logger=self.logger,
        )

        # Initialize TorrentManager with the correct paths
        self.torrent_manager = TorrentManager(
            torrent_save_path=self.torrent_save_path,
            torrent_client_path=self.torrent_client_path,
            base_url=self.base_al_url,  # Передаём base_al_url из конфига
            net_client=self.net_client
        )
        # Corrected debug logging of paths using setup values
        self.logger.debug(f"Video Player Path: {self.video_player_path}")
        self.logger.debug(f"Torrent Client Path: {self.torrent_client_path}")

        self.api_client = APIClient(
            base_url=self.base_al_url,
            api_version=self.al_api_version,
            net_client=self.net_client,
            logger=self.logger,
            utils_folder=self.temp_dir,
            sleep_fn=None,
            max_cache_items=256,
            enable_dumps=False
        )
        self.api_adapter = APIAdapter(
            self.api_client,
            self.logger,
        )

        self.playlist_manager = PlaylistManager()
        self.db_manager = db_manager
        self.poster_manager = PosterManager(
            save_callback=self.db_manager.save_poster,
            net_client=self.net_client
        )

        self.ui_generator = UIGenerator(self, self.db_manager, self.current_template)
        self.ui_am_generator = UIAMGenerator(self, self.db_manager, self.current_template)
        self.ui_s_generator = UISGenerator(self, self.db_manager)
        self.add_title_browser_to_layout.connect(self.on_add_title_browser_to_layout)

        qss_path = pathlib.Path('static/styles.qss')
        if not qss_path.is_file():
            raise FileNotFoundError(f"Не найден файл стилей: {qss_path}")
        self.ui_style = qss_path.read_text(encoding='utf-8')
        self.ui_manager = UIManager(self, self.ui_style)

        self.link_handler = LinkActionHandler(
            logger=self.logger,
            db_manager=self.db_manager,
            animedia_cache=self.animedia_cache,
            titles_list_batch_size=self.titles_list_batch_size,
            display_info=self.display_info,
            display_titles=self.display_titles,
            play_link=self.play_link,
            play_playlist_wrapper=self.play_playlist_wrapper,
            save_torrent_wrapper=self.save_torrent_wrapper,
            reset_offset=self.reset_offset,
            get_search_by_title_animedia=self.get_search_by_title_animedia,
            open_web=self.open_web_link,
            refresh_display=self.refresh_display,
            reload_poster=self.get_poster_or_placeholder
        )

        # init open router
        self.router = OpenRouter(self)

        self.callbacks = {}
        days_of_week = ["MO", "TU", "WE", "TH", "FR", "SA", "SU"]
        for i, day in enumerate(days_of_week):
            self.callbacks[f"display_titles_for_day_{i}"] = lambda checked, i=i: self.display_titles_for_day(i + 1)

        self.svc = AppServices(
            logger=self.logger,
            config=self.config_manager,
            db=self.db_manager,
            ui=self.ui_manager,
            playlist=self.playlist_manager,
            api=self.api_adapter,
            http=getattr(self, "_http", None),  # если есть общий клиент
        )

        self.state_runtime = StateRuntimeController(self, self.svc)
        self.actions = ActionsController(self, self.svc)
        self.animedia = AniMediaController(self, self.svc)
        self.aniliberty = AniLibertyController(self, self.svc)
        self.persistence = PersistenceController(self, self.svc)
        self.callback = CallbackController(self, self.svc, all_layout_metadata)
        self.display = DisplayController(self, self.svc)
        self.torrent = TorrentController(self, self.svc)
        self.poster = PosterController(self, self.svc)
        self.player = PlayerController(self, self.svc)

        self.callbacks.update(self.callback.generate_callbacks())

        app = QApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(self.api_client.close)

        self.init_ui(all_layout_metadata)

    def closeEvent(self, event):
        QApplication.instance().quit()  # Завершает все окна приложения

    @pyqtSlot(QTextBrowser, int, int)
    def on_add_title_browser_to_layout(self, title_browser, row, column):
        self.posters_layout.addWidget(title_browser, row, column)

    @staticmethod
    def calc_offset(offset: int, total: int, page_size: int, go_forward: bool) -> int:
        if total <= 0:
            return 0
        if go_forward:
            return 0 if offset + page_size >= total else offset + page_size
        return max(0, offset - page_size)

    def on_link_click(self, url):
        link = url.toString()
        self.link_handler.handle(link)

    # Bootstrap
    def get_cfg(self, *a, **kw):
        return self.bootstrap.get_cfg(*a, **kw)

    def setup_paths(self):
        return self.bootstrap.setup_paths()

    # State runtime
    def restore_state(self, *a, **kw):
        return self.state_runtime.restore_state(*a, **kw)

    def set_view_state(self, *a, **kw):
        return self.state_runtime.set_view_state(*a, **kw)

    def get_current_state(self):
        return self.state_runtime.get_current_state()

    def navigate_animedia_mode(self, *a, **kw):
        return self.state_runtime.navigate_animedia_mode(*a, **kw)

    # Actions
    def get_update_title(self):
        return self.actions.get_update_title()

    def get_update_title_aniliberty(self):
        return self.actions.get_update_title_aniliberty()

    def get_search_by_title(self):
        return self.actions.get_search_by_title()

    def get_update_title_animedia(self):
        return self.actions.get_update_title_animedia()

    def get_search_by_title_aniliberty(self):
        return self.actions.get_search_by_title_aniliberty()

    def get_search_by_title_animedia(self, *a, **kw):
        return self.actions.get_search_by_title_animedia(*a, **kw)

    # AniMedia
    def get_animedia_new_titles(self):
        return self.animedia.get_animedia_new_titles()

    def get_animedia_all_titles(self):
        return self.animedia.get_animedia_all_titles()

    def display_animedia_schedule_screen(self, *a, **kw):
        return self.animedia.display_animedia_schedule_screen(*a, **kw)

    def display_animedia_titles_screen(self, *a, **kw):
        return self.animedia.display_animedia_titles_screen(*a, **kw)

    # AniLiberty
    def get_random_title(self):
        return self.aniliberty.get_random_title()

    def reload_schedule(self):
        return self.aniliberty.reload_schedule()

    def fetch_and_process_schedule(self, *a, **kw):
        return self.aniliberty.fetch_and_process_schedule(*a, **kw)

    # Persistence
    def save_titles_list(self, *a, **kw):
        return self.persistence.save_titles_list(*a, **kw)

    def save_parsed_data(self, *a, **kw):
        return self.persistence.save_parsed_data(*a, **kw)

    def invoke_database_save(self, *a, **kw):
        return self.persistence.invoke_database_save(*a, **kw)

    # Callbacks
    def generate_callbacks(self):
        return self.callback.generate_callbacks()

    # Display
    def show_error_notification(self, *a, **kw):
        return self.display.show_error_notification(*a, **kw)

    def create_animedia_schedule_browser(self, *a, **kw):
        return self.display.create_animedia_schedule_browser(*a, **kw)

    def create_animedia_titles_browser(self, *a, **kw):
        return self.display.create_animedia_titles_browser(*a, **kw)

    def create_title_browser(self, *a, **kw):
        return self.display.create_title_browser(*a, **kw)

    def create_system_browser(self, *a, **kw):
        return self.display.create_system_browser(*a, **kw)

    def navigate_pagination(self, *a, **kw):
        return self.display.navigate_pagination(*a, **kw)

    def setup_pagination_ui(self, *a, **kw):
        return self.display.setup_pagination_ui(*a, **kw)

    def display_info(self, *a, **kw):
        return self.display.display_info(*a, **kw)

    def display_titles(self, *a, **kw):
        return self.display.display_titles(*a, **kw)

    def display_titles_in_ui(self, *a, **kw):
        return self.display.display_titles_in_ui(*a, **kw)

    def init_ui(self, *a, **kw):
        return self.display.init_ui(*a, **kw)

    def refresh_display(self):
        return self.display.refresh_display()

    def reset_offset(self):
        return self.display.reset_offset()

    # Torrent
    def save_torrent_wrapper(self, *a, **kw):
        return self.torrent.save_torrent_wrapper(*a, **kw)

    # Poster
    def get_poster_or_placeholder(self, *a, **kw):
        return self.poster.get_poster_or_placeholder(*a, **kw)

    def clear_previous_posters(self):
        return self.poster.clear_previous_posters()

    def sanitize_filename(self, *a, **kw):
        return self.poster.sanitize_filename(*a, **kw)

    # Player
    def play_link(self, *a, **kw):
        return self.player.play_link(*a, **kw)

    def play_playlist_wrapper(self,*a, **kw):
        return self.player.play_playlist_wrapper(*a, **kw)

    def open_web_link(self, *a, **kw):
        return self.player.open_web_link(*a, **kw)

    def save_playlist_wrapper(self):
        return self.player.save_playlist_wrapper()

    def ensure_playlist_bundle(self, *a, **kw):
        return self.player.ensure_playlist_bundle(*a, **kw)

    def get_mini_browser_command(self):
        return self.player.get_mini_browser_command()

