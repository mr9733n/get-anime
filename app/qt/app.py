import pathlib
import sys
import json
import logging

from pathlib import Path
from datetime import datetime, timezone
from typing import List, Any, Dict, Union
from PyQt5.QtWidgets import QWidget, QTextBrowser, QApplication
from PyQt5.QtCore import QThreadPool, pyqtSlot, pyqtSignal, QSharedMemory

from app.qt.app_state_manager import AppStateManager
from app.qt.app_handlers import LinkActionHandler
from app.qt.ui_am_generator import UIAMGenerator
from app.qt.ui_manger import UIManager
from app.qt.ui_generator import UIGenerator
from app.qt.ui_s_generator import UISGenerator
from app.qt.app_exceptions import APIClientError
from app.qt.app_state import ViewState, TitleRef
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
        self.thread_pool.setExpiryTimeout(30000)
        self.mpv_window = None
        self.view_state = None
        self._am_total_count = None
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
        self.use_libvlc = self._get_cfg('Settings', 'use_libvlc', "false", lower=True)
        self.log_enabled = self._get_cfg('VlcPlayer', 'log_enabled', "false", lower=True)
        self.verbose = self._get_cfg('VlcPlayer', 'verbose_level', "2")
        # network
        self.proxy_enabled = self._get_cfg('Network', 'proxy_enabled', "false", lower=True)
        self.proxy_url = self._get_cfg('Network', 'proxy_url', None)
        # mpv‑related
        self.use_mpv_player = self._get_cfg('Settings', 'use_mpv_player', "false", lower=True)
        self.mpv_player_executable_name = self._get_cfg('MpvPlayer', 'executable_name', "mpv_player.exe")
        self.mpv_log_enabled = self._get_cfg('MpvPlayer', 'log_enabled', "false", lower=True)
        self.mpv_verbose = self._get_cfg('MpvPlayer', 'verbose_level', "info")

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

        self.state_manager = AppStateManager(self.db_manager)
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

        self.callbacks = self.generate_callbacks(all_layout_metadata)
        days_of_week = ["MO", "TU", "WE", "TH", "FR", "SA", "SU"]
        for i, day in enumerate(days_of_week):
            self.callbacks[f"display_titles_for_day_{i}"] = lambda checked, i=i: self.display_titles_for_day(i + 1)

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
    def _calc_offset(offset: int, total: int, page_size: int, go_forward: bool) -> int:
        if total <= 0:
            return 0
        if go_forward:
            return 0 if offset + page_size >= total else offset + page_size
        return max(0, offset - page_size)

    def on_link_click(self, url):
        link = url.toString()
        self.link_handler.handle(link)

# --- Display ---
from app.qt.app_display import (
    init_ui,
    show_error_notification,
    refresh_display,
    update_title_links,
    navigate_pagination,
    display_titles,
    _update_pagination_offset,
    _setup_pagination_ui,
    display_titles_in_ui,
    display_info,
    display_titles_for_day,
    clear_layout,
    create_system_browser,
    create_animedia_schedule_browser,
    create_animedia_titles_browser,
    create_title_browser,
    reset_offset,
)
# --- Bootstrap ---
from app.qt.app_bootstrap import _get_cfg, setup_paths
# --- State runtime ---
from app.qt.app_state_runtime import (
    get_current_state,
    set_view_state,
    restore_state,
    _restore_day,
    _restore_title,
    _restore_titles,
    _navigate_animedia_mode,
    _animedia_display_for_mode,
)
# --- Callbacks ---
from app.qt.app_callbacks import generate_callbacks, generate_simple_callback
# --- Actions ---
from app.qt.app_actions import (
    get_search_by_title,
    get_search_by_title_aniliberty,
    get_search_by_title_animedia,
    get_update_title,
    get_update_title_aniliberty,
    get_update_title_animedia,
    _resolve_titles_for_query,
    _update_titles,
    _search_by_title,
    _handle_found_titles,
    _handle_get_titles_from_api,
)
# --- Persistence ---
from app.qt.app_persistence import (
    invoke_database_save,
    _save_titles_list,
    _save_parsed_data,
)
# --- Torrents ---
from app.qt.app_torrents import save_torrent_wrapper
# --- Players ---
from app.qt.app_players import (
    open_mpv_player,
    open_standalone_mpv_player,
    open_vlc_player,
    open_standalone_vlc_player,
    open_web_link,
    play_link,
    play_playlist_wrapper,
    get_mini_browser_command,
    ensure_playlist_bundle,
    save_playlist_wrapper,
    save_combined_playlist_wrapper,
)
# --- Posters ---
from app.qt.app_posters import (
    get_poster_or_placeholder,
    perform_poster_link,
    sanitize_filename,
    standardize_url,
    clear_previous_posters,
)
# --- AniMedia ---
from app.qt.app_animedia import (
    display_animedia_titles_screen,
    display_animedia_schedule_screen,
    _warmup_animedia_titles_and_posters,
    _count_animedia_items,
    _slice_animedia_titles,
    get_animedia_all_titles,
    get_animedia_new_titles,
    _on_animedia_all_titles,
    _on_animedia_new_titles,
    _on_animedia_error,
    _on_animedia_result,
)
# --- AniLiberty ---
from app.qt.app_aniliberty import (
    fetch_and_process_schedule,
    check_and_update_schedule,
    get_random_title,
    parse_schedule_data,
    get_schedule,
    reload_schedule,
)
# --- Display ---
AnimePlayerAppVer3.init_ui = init_ui
AnimePlayerAppVer3.show_error_notification = show_error_notification
AnimePlayerAppVer3.refresh_display = refresh_display
AnimePlayerAppVer3.update_title_links =  update_title_links
AnimePlayerAppVer3.navigate_pagination = navigate_pagination
AnimePlayerAppVer3.display_titles = display_titles
AnimePlayerAppVer3._update_pagination_offset = _update_pagination_offset
AnimePlayerAppVer3._setup_pagination_ui = _setup_pagination_ui
AnimePlayerAppVer3.display_titles_in_ui = display_titles_in_ui
AnimePlayerAppVer3.display_info = display_info
AnimePlayerAppVer3.display_titles_for_day = display_titles_for_day
AnimePlayerAppVer3.clear_layout = clear_layout
AnimePlayerAppVer3.create_system_browser = create_system_browser
AnimePlayerAppVer3.create_animedia_schedule_browser = create_animedia_schedule_browser
AnimePlayerAppVer3.create_animedia_titles_browser = create_animedia_titles_browser
AnimePlayerAppVer3.create_title_browser = create_title_browser
AnimePlayerAppVer3.reset_offset = reset_offset
# --- Bootstrap ---
AnimePlayerAppVer3._get_cfg = _get_cfg
AnimePlayerAppVer3.setup_paths = setup_paths
# --- State runtime ---
AnimePlayerAppVer3.get_current_state = get_current_state
AnimePlayerAppVer3.set_view_state = set_view_state
AnimePlayerAppVer3.restore_state = restore_state
AnimePlayerAppVer3._restore_day = _restore_day
AnimePlayerAppVer3._restore_title = _restore_title
AnimePlayerAppVer3._restore_titles = _restore_titles
AnimePlayerAppVer3._navigate_animedia_mode = _navigate_animedia_mode
AnimePlayerAppVer3._animedia_display_for_mode = _animedia_display_for_mode
# --- Callbacks ---
AnimePlayerAppVer3.generate_callbacks = generate_callbacks
AnimePlayerAppVer3.generate_simple_callback = generate_simple_callback
# --- Actions ---
AnimePlayerAppVer3.get_search_by_title = get_search_by_title
AnimePlayerAppVer3.get_search_by_title_aniliberty = get_search_by_title_aniliberty
AnimePlayerAppVer3.get_search_by_title_animedia = get_search_by_title_animedia
AnimePlayerAppVer3.get_update_title = get_update_title
AnimePlayerAppVer3.get_update_title_aniliberty = get_update_title_aniliberty
AnimePlayerAppVer3.get_update_title_animedia = get_update_title_animedia
AnimePlayerAppVer3._resolve_titles_for_query = _resolve_titles_for_query
AnimePlayerAppVer3._update_titles = _update_titles
AnimePlayerAppVer3._search_by_title = _search_by_title
AnimePlayerAppVer3._handle_found_titles = _handle_found_titles
AnimePlayerAppVer3._handle_get_titles_from_api = _handle_get_titles_from_api
# --- Persistence ---
AnimePlayerAppVer3.invoke_database_save = invoke_database_save
AnimePlayerAppVer3._save_titles_list = _save_titles_list
AnimePlayerAppVer3._save_parsed_data = _save_parsed_data
# --- Torrents ---
AnimePlayerAppVer3.save_torrent_wrapper = save_torrent_wrapper
# --- Players ---
AnimePlayerAppVer3.open_mpv_player = open_mpv_player
AnimePlayerAppVer3.open_standalone_mpv_player = open_standalone_mpv_player
AnimePlayerAppVer3.open_vlc_player = open_vlc_player
AnimePlayerAppVer3.open_standalone_vlc_player = open_standalone_vlc_player
AnimePlayerAppVer3.open_web_link = open_web_link
AnimePlayerAppVer3.play_link = play_link
AnimePlayerAppVer3.play_playlist_wrapper = play_playlist_wrapper
AnimePlayerAppVer3.get_mini_browser_command = get_mini_browser_command
AnimePlayerAppVer3.ensure_playlist_bundle = ensure_playlist_bundle
AnimePlayerAppVer3.save_playlist_wrapper = save_playlist_wrapper
AnimePlayerAppVer3.save_combined_playlist_wrapper = save_combined_playlist_wrapper
# --- Posters ---
AnimePlayerAppVer3.get_poster_or_placeholder = get_poster_or_placeholder
AnimePlayerAppVer3.perform_poster_link = perform_poster_link
AnimePlayerAppVer3.clear_previous_posters = clear_previous_posters
AnimePlayerAppVer3.sanitize_filename = staticmethod(sanitize_filename)
AnimePlayerAppVer3.standardize_url = staticmethod(standardize_url)
# --- AniMedia ---
AnimePlayerAppVer3.display_animedia_titles_screen = display_animedia_titles_screen
AnimePlayerAppVer3.display_animedia_schedule_screen = display_animedia_schedule_screen
AnimePlayerAppVer3._warmup_animedia_titles_and_posters = _warmup_animedia_titles_and_posters
AnimePlayerAppVer3._count_animedia_items = staticmethod(_count_animedia_items)
AnimePlayerAppVer3._slice_animedia_titles = staticmethod(_slice_animedia_titles)
AnimePlayerAppVer3.get_animedia_all_titles = get_animedia_all_titles
AnimePlayerAppVer3.get_animedia_new_titles = get_animedia_new_titles
AnimePlayerAppVer3._on_animedia_all_titles = _on_animedia_all_titles
AnimePlayerAppVer3._on_animedia_new_titles = _on_animedia_new_titles
AnimePlayerAppVer3._on_animedia_error = _on_animedia_error
AnimePlayerAppVer3._on_animedia_result = _on_animedia_result
# --- AniLiberty ---
AnimePlayerAppVer3.fetch_and_process_schedule = fetch_and_process_schedule
AnimePlayerAppVer3.check_and_update_schedule = check_and_update_schedule
AnimePlayerAppVer3.get_random_title = get_random_title
AnimePlayerAppVer3.parse_schedule_data = parse_schedule_data
AnimePlayerAppVer3.get_schedule = get_schedule
AnimePlayerAppVer3.reload_schedule = reload_schedule
