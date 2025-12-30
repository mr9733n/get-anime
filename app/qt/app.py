import os
import pathlib
import sys
import logging
import importlib.resources as ir

from PyQt5.QtWidgets import QWidget, QTextBrowser, QApplication
from PyQt5.QtCore import QThreadPool, pyqtSlot, pyqtSignal, QSharedMemory

from app.qt.app_services import AppServices
from app.qt.orchestrator_proxies import OrchestratorProxies

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
from utils.downloads.poster_manager import PosterManager
from utils.downloads.torrent_manager import TorrentManager
from utils.playlists.playlist_manager import PlaylistManager
from utils.integrations.open_router import OpenRouter
from utils.net.net_client import NetClient
from utils.net.url_resolve_service import UrlResolveService
from utils.net.url_resolver import TTLCache
from utils.net.url_resolver_config import ResolverConfig


class AnimePlayerAppVer3(OrchestratorProxies, QWidget):
    add_title_browser_to_layout = pyqtSignal(QTextBrowser, int, int)
    state_changed = pyqtSignal()

    def __init__(self, config_manager, db_manager, version, template_name, prod_key=None):
        super().__init__()
        self.logger = logging.getLogger(__name__)

        self._init_single_instance(prod_key)
        self._init_threading_and_state()

        self._init_config_and_bootstrap(config_manager, db_manager, version, template_name, prod_key)
        self._init_network()
        self._init_settings()

        self._init_paths_and_cache()
        self._init_providers_and_managers()

        self._init_ui()
        self._init_services_and_controllers()
        self._init_link_handler()

    def _init_single_instance(self, prod_key):
        self.prod_key = prod_key
        if prod_key is not None:
            unique_key = str(prod_key) + '-APA'
            self.shared_memory = QSharedMemory(unique_key)
            if not self.shared_memory.create(1):
                self.logger.error("Main application is already running!")
                sys.exit(1)

    def _init_threading_and_state(self):
        self.thread_pool = QThreadPool()
        self.thread_pool.setMaxThreadCount(4)
        self.thread_pool.setExpiryTimeout(30_000)

        # runtime/ui state defaults
        self.mpv_window = None
        self.view_state = None
        self.am_total_count = None
        self.current_show_mode = None
        self.error_label = None
        self.tray_icon = None
        self.animedia_worker = None
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
        self.callbacks = {}

        self.row_start = 0
        self.col_start = 0
        self.pre = "https://"

    def _init_config_and_bootstrap(self, config_manager, db_manager, version, template_name, prod_key):
        self.current_template = template_name
        self.logger.info(f"Используется шаблон: {self.current_template}")
        self.app_version = version
        self.logger.debug(f"Starting AnimePlayerApp Version {self.app_version}..")

        self.config_manager = config_manager
        self.db_manager = db_manager

        self.bootstrap = BootstrapController(self, None)

    def _init_network(self):
        self.network_config = self.config_manager.network
        self.net_client = NetClient(self.network_config)
        self.logger.info(f"Network client initialized. Proxy enabled: {self.network_config.proxy_enabled}")

        self.url_resolver = UrlResolveService(
            net=self.net_client,
            cache=TTLCache(max_items=2048),
            cfg=ResolverConfig(),
        )

    def _init_settings(self):
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
        self.use_libvlc = self.get_cfg_bool('Settings', 'use_libvlc', False)
        self.log_enabled = self.get_cfg_bool('VlcPlayer', 'log_enabled', False)
        self.verbose = self.get_cfg('VlcPlayer', 'verbose_level', "2")

        # network
        self.proxy_enabled = bool(self.network_config.proxy_enabled)
        self.proxy_url = self.network_config.proxy_url

        # mpv
        self.mpv_player_executable_name = self.get_cfg('MpvPlayer', 'executable_name', "mpv_player.exe")
        self.use_mpv_player = self.get_cfg_bool('Settings', 'use_mpv_player', False)
        self.mpv_log_enabled = self.get_cfg_bool('MpvPlayer', 'log_enabled', False)
        self.mpv_verbose = self.get_cfg('MpvPlayer', 'verbose_level', "info")

    def _init_paths_and_cache(self):
        self.data_dir = self._default_data_dir()
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.torrent_save_path = self.data_dir / "torrents"
        self.torrent_save_path.mkdir(parents=True, exist_ok=True)

        self.temp_dir = self.data_dir / "temp"
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.logger.info(f"[***] {self.temp_dir}, {self.torrent_save_path}")

        self.video_player_path, self.torrent_client_path = self.setup_paths()

        self.animedia_cache_cfg = AniMediaCacheConfig(base_dir=self.temp_dir)
        self.animedia_cache = AniMediaCacheManager(self.animedia_cache_cfg.base_dir)

    def _init_providers_and_managers(self):
        # AniMedia adapter
        self.animedia_adapter = create_adapter(
            base_url=self.base_am_url,
            net_client=self.net_client,
            cache_dir=self.temp_dir,
            logger=self.logger,
        )

        # Torrent manager
        self.torrent_manager = TorrentManager(
            torrent_save_path=self.torrent_save_path,
            torrent_client_path=self.torrent_client_path,
            base_url=self.base_al_url,
            net_client=self.net_client
        )
        self.logger.debug(f"Video Player Path: {self.video_player_path}")
        self.logger.debug(f"Torrent Client Path: {self.torrent_client_path}")

        # AniLiberty API
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
        self.api_adapter = APIAdapter(self.api_client, self.logger)

        # Managers
        self.playlist_manager = PlaylistManager()
        self.poster_manager = PosterManager(
            save_callback=self.db_manager.save_poster,
            net_client=self.net_client
        )

    def _init_ui(self):
        self.ui_generator = UIGenerator(self, self.db_manager, self.current_template)
        self.ui_am_generator = UIAMGenerator(self, self.db_manager, self.current_template)
        self.ui_s_generator = UISGenerator(self, self.db_manager)

        self.add_title_browser_to_layout.connect(self.on_add_title_browser_to_layout)

        try:
            qss_path = ir.files("static").joinpath("styles.qss")
            self.ui_style = qss_path.read_text(encoding="utf-8")
        except Exception as e:
            raise FileNotFoundError("Не удалось загрузить static/styles.qss как ресурс пакета") from e

        self.ui_manager = UIManager(self, self.ui_style)

    def _init_link_handler(self):
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
        self.router = OpenRouter(self)

    def _init_services_and_controllers(self):
        self.svc = AppServices(
            logger=self.logger,
            config=self.config_manager,
            db=self.db_manager,
            ui=self.ui_manager,
            playlist=self.playlist_manager,
            api=self.api_adapter,
            http=getattr(self, "_http", None),
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

        if not hasattr(self, "callbacks"):
            self.callbacks = {}

        self.callbacks.update(self.callback.generate_callbacks())

        app = QApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(self.api_client.close)

        self.init_ui(all_layout_metadata)

    @staticmethod
    def _default_data_dir(app_name: str = "AnimePlayer") -> pathlib.Path:
        if sys.platform.startswith("win"):
            base = pathlib.Path(os.getenv("APPDATA", pathlib.Path.home() / "AppData" / "Roaming"))
        elif sys.platform == "darwin":
            base = pathlib.Path.home() / "Library" / "Application Support"
        else:
            base = pathlib.Path(os.getenv("XDG_DATA_HOME", pathlib.Path.home() / ".local" / "share"))
        return base / app_name

    def get_cfg_bool(self, section, key, default=False) -> bool:
        val = self.get_cfg(section, key, default)
        return str(val).lower() in ("1", "true", "yes", "on")

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


