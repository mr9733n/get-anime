# app/qt/app.py
from __future__ import annotations

import os
import sys
import logging
import pathlib
import importlib.resources as ir

from PyQt5.QtWidgets import QWidget, QTextBrowser, QApplication
from PyQt5.QtCore import QThreadPool, pyqtSlot, pyqtSignal, QSharedMemory

from app.qt.app_context import AppContext
from app.qt.app_services import AppServices
from app.qt.controller_factory import ControllerFactory, ControllerFactoryConfig
from app.qt.app_handlers import LinkActionHandler
from app.qt.ui_manager import UIManager
from app.qt.ui_generator import UIGenerator
from app.qt.ui_am_generator import UIAMGenerator
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


class AnimePlayerAppVer3(QWidget):
    """
    Главное окно приложения.

    После рефакторинга:
    - Использует AppContext для общего состояния
    - Контроллеры создаются через ControllerFactory
    - Нет OrchestratorProxies — зависимости явные
    - Тонкие обёртки для публичного API
    """

    # Signals
    add_title_browser_to_layout = pyqtSignal(QTextBrowser, int, int)
    state_changed = pyqtSignal()

    def __init__(
            self,
            config_manager,
            db_manager,
            version: str,
            template_name: str,
            prod_key: str | None = None,
    ):
        super().__init__()
        self.logger = logging.getLogger(__name__)

        # === Core Context ===
        self.ctx = AppContext()
        self.ctx.app_version = version
        self.ctx.current_template = template_name

        # === Initialization Sequence ===
        self._init_single_instance(prod_key)
        self._init_threading()
        self._init_config(config_manager, db_manager, prod_key)
        self._init_styles()
        self._init_network()
        self._init_settings()
        self._init_paths_and_cache()
        self._init_providers_and_managers()
        self._init_ui_generators()
        self._init_services()
        self._init_controllers()
        self._init_link_handler()
        self._finalize_ui()
        self._restore_saved_state()

        # =========================================================================
    # INITIALIZATION METHODS
    # =========================================================================
    def _init_styles(self) -> None:
        """Загружает стили (вызывается раньше всех UI методов)."""
        try:
            qss_path = ir.files("static").joinpath("styles.qss")
            self.ui_style = qss_path.read_text(encoding="utf-8")
        except Exception as e:
            self.ui_style = ""  # fallback
            self.logger.warning(f"Failed to load styles.qss: {e}")

    def _init_single_instance(self, prod_key: str | None) -> None:
        """Гарантирует единственный экземпляр приложения."""
        self.prod_key = prod_key
        self.shared_memory = None

        if prod_key is not None:
            unique_key = f"{prod_key}-APA"
            self.shared_memory = QSharedMemory(unique_key)
            if not self.shared_memory.create(1):
                self.logger.error("Main application is already running!")
                sys.exit(1)

    def _init_threading(self) -> None:
        """Настраивает thread pool."""
        self.thread_pool = QThreadPool()
        self.thread_pool.setMaxThreadCount(4)
        self.thread_pool.setExpiryTimeout(30_000)

    def _init_config(
            self,
            config_manager,
            db_manager,
            prod_key: str | None,
    ) -> None:
        """Инициализирует конфигурацию."""
        self.config_manager = config_manager
        self.db_manager = db_manager

        self.logger.info(f"Using template: {self.ctx.current_template}")
        self.logger.debug(f"Starting AnimePlayerApp Version {self.ctx.app_version}")

    def _init_network(self) -> None:
        """Инициализирует сетевые компоненты."""
        self.network_config = self.config_manager.network
        self.net_client = NetClient(self.network_config)
        self.logger.info(f"Network client initialized. Proxy: {self.network_config.proxy_enabled}")

        self.url_resolver = UrlResolveService(
            net=self.net_client,
            cache=TTLCache(max_items=2048),
            cfg=ResolverConfig(),
        )

    def _init_settings(self) -> None:
        """Загружает настройки в контекст."""
        cfg = self.config_manager

        # URLs
        self.base_al_url = cfg.get_setting('Settings', 'base_al_url')
        self.base_am_url = cfg.get_setting('Settings', 'base_am_url')
        self.al_api_version = cfg.get_setting('Settings', 'al_api_version')

        # Batch sizes -> context
        self.ctx.titles_batch_size = int(cfg.get_setting('Settings', 'titles_batch_size'))
        self.ctx.titles_list_batch_size = int(cfg.get_setting('Settings', 'titles_list_batch_size'))
        self.ctx.current_offset = int(cfg.get_setting('Settings', 'current_offset'))
        self.ctx.user_id = int(cfg.get_setting('Settings', 'user_id'))

        # Other settings
        self.num_columns = int(cfg.get_setting('Settings', 'num_columns'))
        self.default_rating_name = cfg.get_setting('Settings', 'default_rating_name')

        # VLC Player
        self.use_libvlc = self._get_cfg_bool('Settings', 'use_libvlc', False)
        self.log_enabled = self._get_cfg_bool('VlcPlayer', 'log_enabled', False)
        self.verbose = self._get_cfg('VlcPlayer', 'verbose_level', "2")

        # Proxy
        self.proxy_enabled = bool(self.network_config.proxy_enabled)
        self.proxy_url = self.network_config.proxy_url

        # MPV Player
        self.mpv_player_executable_name = self._get_cfg('MpvPlayer', 'executable_name', "mpv_player.exe")
        self.use_mpv_player = self._get_cfg_bool('Settings', 'use_mpv_player', False)
        self.mpv_log_enabled = self._get_cfg_bool('MpvPlayer', 'log_enabled', False)
        self.mpv_verbose = self._get_cfg('MpvPlayer', 'verbose_level', "info")

    def _init_paths_and_cache(self) -> None:
        """Настраивает пути и кэш."""
        self.data_dir = self._default_data_dir()
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.torrent_save_path = self.data_dir / "torrents"
        self.torrent_save_path.mkdir(parents=True, exist_ok=True)

        self.temp_dir = self.data_dir / "temp"
        self.temp_dir.mkdir(parents=True, exist_ok=True)

        self.logger.info(f"Data dirs: temp={self.temp_dir}, torrents={self.torrent_save_path}")

        self.video_player_path, self.torrent_client_path = self._setup_paths()

        self.animedia_cache_cfg = AniMediaCacheConfig(base_dir=self.temp_dir)
        self.animedia_cache = AniMediaCacheManager(self.animedia_cache_cfg.base_dir)

    def _init_providers_and_managers(self) -> None:
        """Инициализирует провайдеры и менеджеры."""
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
            net_client=self.net_client,
        )

        # AniLiberty API
        self.api_client = APIClient(
            base_url=self.base_al_url,
            api_version=self.al_api_version,
            net_client=self.net_client,
            logger=self.logger,
            utils_folder=self.temp_dir,
            sleep_fn=None,
            max_cache_items=256,
            enable_dumps=False,
        )
        self.api_adapter = APIAdapter(self.api_client, self.logger)

        # Managers
        self.playlist_manager = PlaylistManager()
        self.poster_manager = PosterManager(
            save_callback=self.db_manager.save_poster,
            net_client=self.net_client,
        )

        self.logger.debug(f"Video Player Path: {self.video_player_path}")
        self.logger.debug(f"Torrent Client Path: {self.torrent_client_path}")

    def _init_ui_generators(self) -> None:
        """Инициализирует UI генераторы."""
        self.ui_manager = UIManager(self, self.ui_style)

        self.ui_generator = UIGenerator(self, self.db_manager, self.ctx.current_template)
        self.ui_am_generator = UIAMGenerator(self, self.db_manager, self.ctx.current_template)
        self.ui_s_generator = UISGenerator(self, self.db_manager)

    def _init_services(self) -> None:
        """Инициализирует сервисный слой."""
        self.svc = AppServices(
            logger=self.logger,
            config=self.config_manager,
            db=self.db_manager,
            ui=self.ui_manager,
            playlist=self.playlist_manager,
            api=self.api_adapter,
            http=None,
        )
        self._saved_state = self.svc.load_state()

    def _restore_saved_state(self) -> None:
        """Восстанавливает сохранённое состояние ПОСЛЕ init UI."""
        if not self._saved_state:
            # Нет сохранённого состояния — показываем стартовый экран
            self.display.display_titles(start=True)
            return

        try:
            self.state.restore_state(self._saved_state)
        except Exception as e:
            self.logger.error(f"Failed to restore state: {e}")
            self.display.display_titles(start=True)

    def _init_controllers(self) -> None:
        """Создаёт все контроллеры через фабрику."""
        config = ControllerFactoryConfig(
            base_al_url=self.base_al_url,
            base_am_url=self.base_am_url,
            use_libvlc=self.use_libvlc,
            use_mpv_player=self.use_mpv_player,
            proxy_enabled=self.proxy_enabled,
            proxy_url=self.proxy_url,
            log_enabled=self.log_enabled,
            verbose=self.verbose,
            mpv_log_enabled=self.mpv_log_enabled,
            mpv_verbose=self.mpv_verbose,
            mpv_player_executable_name=self.mpv_player_executable_name,
            video_player_path=self.video_player_path,
            prod_key=self.prod_key,
        )

        self._factory = ControllerFactory(
            logger=self.logger,
            context=self.ctx,
            svc=self.svc,
            parent_widget=self,
            config=config,
            layout_metadata=all_layout_metadata,
            config_manager=self.config_manager,
            animedia_adapter=self.animedia_adapter,
            animedia_cache=self.animedia_cache,
            ui_generator=self.ui_generator,
            ui_am_generator=self.ui_am_generator,
            ui_s_generator=self.ui_s_generator,
            poster_manager=self.poster_manager,
            torrent_manager=self.torrent_manager,
            playlist_manager=self.playlist_manager,
            api_adapter=self.api_adapter,
            url_resolver=self.url_resolver,
            router_getter=lambda: self.router,
        ).build()

        # Shortcut references
        self.bootstrap = self._factory.bootstrap
        self.persistence = self._factory.persistence
        self.poster = self._factory.poster
        self.torrent = self._factory.torrent
        self.state = self._factory.state
        self.display = self._factory.display
        self.actions = self._factory.actions
        self.aniliberty = self._factory.aniliberty
        self.animedia = self._factory.animedia
        self.player = self._factory.player
        self.callback = self._factory.callback

    def _init_link_handler(self) -> None:
        """Инициализирует обработчик ссылок."""
        self.link_handler = LinkActionHandler(
            logger=self.logger,
            db_manager=self.db_manager,
            animedia_cache=self.animedia_cache,
            titles_list_batch_size=self.ctx.titles_list_batch_size,
            display_info=self.display_info,
            display_titles=self.display_titles,
            play_link=self.play_link,
            play_playlist_wrapper=self.play_playlist_wrapper,
            save_torrent_wrapper=self.save_torrent_wrapper,
            reset_offset=self.reset_offset,
            get_search_by_title_animedia=self.get_search_by_title_animedia,
            load_more_animedia_titles=self.load_more_animedia_titles,
            open_web=self.open_web_link,
            refresh_display=self.refresh_display,
            reload_poster=self.get_poster_or_placeholder,
        )
        self.router = OpenRouter(self)

    def _finalize_ui(self) -> None:
        """Финализирует инициализацию UI."""
        # Connect signals
        self.add_title_browser_to_layout.connect(self._on_add_title_browser_to_layout)

        # Get callbacks from factory
        callbacks = self._factory.get_callbacks()

        # Initialize display UI
        self.display.init_ui(all_layout_metadata, callbacks)

        # Store layout references in context
        self.ctx.posters_layout = self.posters_layout
        self.ctx.scroll_area = self.scroll_area
        self.ctx.poster_container = self.poster_container
        self.ctx.title_search_entry = self.ui_manager.parent_widgets.get("title_input")
        self.ctx.quality_dropdown = self.ui_manager.parent_widgets.get("quality_dropdown")

        # === ДОБАВИТЬ: ссылка на parent для callbacks в контроллерах ===
        self.ctx._parent = self

        # Connect app quit
        app = QApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(self.api_client.close)

    # =========================================================================
    # PUBLIC API (thin wrappers for backwards compatibility)
    # =========================================================================

    # --- Display ---

    def display_info(self, title_id: int) -> None:
        """Отображает информацию о тайтле."""
        self.display.display_info(title_id)

    def display_titles(self, **kwargs) -> None:
        """Отображает список тайтлов."""
        self.display.display_titles(**kwargs)

    def display_titles_for_day(self, day_of_week: int, force_reload: bool = False) -> None:
        """Отображает тайтлы для дня недели."""
        self.display.display_titles_for_day(day_of_week, force_reload)

    def display_titles_in_ui(self, titles: list, show_mode: str = "default") -> None:
        """Отображает тайтлы в UI."""
        self.display.display_titles_in_ui(titles, show_mode)

    def refresh_display(self) -> None:
        """Обновляет текущее отображение."""
        self.display.refresh_display()

    def show_error_notification(self, title: str, message: str) -> None:
        """Показывает уведомление об ошибке."""
        self.display.show_error_notification(title, message)

    def clear_layout(self, layout) -> None:
        """Очищает layout."""
        self.display.clear_layout(layout)

    def reset_offset(self) -> None:
        """Сбрасывает offset пагинации."""
        self.display.reset_offset()

    def setup_pagination_ui(self, count: int, batch_size: int, description: str = None) -> None:
        """Настраивает пагинацию."""
        self.display.setup_pagination_ui(count, batch_size, description)

    def navigate_pagination(self, go_forward: bool = True) -> None:
        """Навигация по страницам."""
        self.display.navigate_pagination(go_forward)

    # --- Actions ---

    def get_search_by_title(self) -> bool:
        """Поиск тайтла."""
        return self.actions.get_search_by_title()

    def get_search_by_title_aniliberty(self) -> bool:
        """Поиск через AniLiberty."""
        return self.actions.get_search_by_title_aniliberty()

    def get_search_by_title_animedia(self, search_text: str = None) -> bool:
        """Поиск через AniMedia."""
        return self.actions.get_search_by_title_animedia(search_text)

    def get_update_title(self) -> bool:
        """Обновление тайтла."""
        return self.actions.get_update_title()

    def get_update_title_aniliberty(self) -> bool:
        """Обновление через AniLiberty."""
        return self.actions.get_update_title_aniliberty()

    def get_update_title_animedia(self) -> bool:
        """Обновление через AniMedia."""
        return self.actions.get_update_title_animedia()

    # --- AniLiberty ---

    def get_random_title(self) -> None:
        """Получает случайный тайтл."""
        self.aniliberty.get_random_title()

    def reload_schedule(self) -> None:
        """Перезагружает расписание."""
        self.aniliberty.reload_schedule()

    def fetch_and_process_schedule(self, day_of_week: int) -> tuple[bool, set | None]:
        """Загружает и обрабатывает расписание."""
        return self.aniliberty.fetch_and_process_schedule(day_of_week)

    # --- AniMedia ---

    def display_animedia_schedule_screen(self, schedule_json: list = None) -> None:
        """Отображает экран расписания AniMedia."""
        self.animedia.display_animedia_schedule_screen(schedule_json)

    def display_animedia_titles_screen(self, titles_json: list = None) -> None:
        """Отображает экран тайтлов AniMedia."""
        self.animedia.display_animedia_titles_screen(titles_json)

    def get_animedia_new_titles(self) -> None:
        """Загружает новые тайтлы AniMedia."""
        self.animedia.get_animedia_new_titles()

    def get_animedia_all_titles(self) -> None:
        """Загружает все тайтлы AniMedia."""
        self.animedia.get_animedia_all_titles()

    def load_more_animedia_titles(self) -> None:
        """Загрузить следующую порцию тайтлов AniMedia."""
        self.animedia.load_more_titles()

    # --- Persistence ---

    def invoke_database_save(self, title_list: list[dict]) -> list[int]:
        """Сохраняет тайтлы в БД."""
        return self.persistence.invoke_database_save(title_list)

    def save_titles_list(self, titles_list: list[dict]) -> list[int]:
        """Сохраняет список тайтлов."""
        return self.persistence.save_titles_list(titles_list)

    def save_parsed_data(self, parsed_data: list[dict]) -> None:
        """Сохраняет распарсенные данные."""
        self.persistence.save_parsed_data(parsed_data)

    # --- Poster ---

    def get_poster_or_placeholder(
            self,
            title_id: int,
            size_key: str = "original",
            force_download: bool = False,
    ) -> bytes | None:
        """Получает постер или placeholder."""
        return self.poster.get_poster_or_placeholder(title_id, size_key, force_download)

    def clear_previous_posters(self) -> None:
        """Очищает предыдущие постеры."""
        self.poster.clear_previous_posters()

    def sanitize_filename(self, name: str) -> str:
        """Очищает имя файла."""
        return self.poster.sanitize_filename(name)

    # --- Player ---

    def play_link(self, link: str, title_id: int = None, skip_data: str = None) -> None:
        """Воспроизводит ссылку."""
        self.player.play_link(link, title_id, skip_data)

    def play_playlist_wrapper(
            self,
            file_name: str = None,
            title_id: int = None,
            skip_data: str = None,
    ) -> None:
        """Воспроизводит плейлист."""
        self.player.play_playlist_wrapper(file_name, title_id, skip_data)

    def save_playlist_wrapper(self) -> None:
        """Сохраняет плейлист."""
        self.player.save_playlist_wrapper()

    def ensure_playlist_bundle(self, title_id: int) -> dict | None:
        """Обеспечивает создание bundle плейлиста."""
        return self.player.ensure_playlist_bundle(title_id)

    def open_web_link(self, link: str, title_id: int = None, skip_data: str = None) -> None:
        """Открывает ссылку в браузере."""
        self.player.open_web_link(link, title_id, skip_data)

    def get_mini_browser_command(self) -> list[str]:
        """Возвращает команду для мини-браузера."""
        return self.player.get_mini_browser_command()

    # --- Torrent ---

    def save_torrent_wrapper(self, link: str, title_name: str, torrent_id: int) -> None:
        """Сохраняет торрент."""
        self.torrent.save_torrent_wrapper(link, title_name, torrent_id)

    # --- State ---

    def set_view_state(self, state) -> None:
        """Устанавливает ViewState."""
        self.state.set_view_state(state)

    def get_current_state(self) -> dict:
        """Возвращает текущее состояние."""
        return self.state.get_current_state()

    def restore_state(self, state: dict) -> None:
        """Восстанавливает состояние."""
        self.state.restore_state(state)

    def navigate_animedia_mode(self, show_mode: str, go_forward: bool) -> bool:
        """Навигация в AniMedia режиме."""
        return self.state.navigate_animedia_mode(show_mode, go_forward)

    # --- Bootstrap ---

    def get_cfg(self, section: str, option: str, default) -> any:
        """Получает значение конфигурации."""
        return self.bootstrap.get_cfg(section, option, default)

    def setup_paths(self) -> tuple[str, str]:
        """Настраивает пути."""
        return self.bootstrap.setup_paths()

    # --- UI Generators (delegation) ---

    def create_title_browser(self, title, show_mode: str = "default"):
        """Создаёт title browser."""
        return self.display.create_title_browser(title, show_mode)

    def create_system_browser(self, statistics: dict):
        """Создаёт system browser."""
        return self.display.create_system_browser(statistics)

    def create_animedia_schedule_browser(self, schedule: list):
        """Создаёт AniMedia schedule browser."""
        return self.display.create_animedia_schedule_browser(schedule)

    def create_animedia_titles_browser(self, titles: list):
        """Создаёт AniMedia titles browser."""
        return self.display.create_animedia_titles_browser(titles)

    # =========================================================================
    # PROPERTIES (для обратной совместимости)
    # =========================================================================

    @property
    def view_state(self):
        return self.ctx.view_state

    @view_state.setter
    def view_state(self, value):
        self.ctx.view_state = value

    @property
    def current_title_id(self):
        return self.ctx.current_title_id

    @current_title_id.setter
    def current_title_id(self, value):
        self.ctx.current_title_id = value

    @property
    def current_title_ids(self):
        return self.ctx.current_title_ids

    @current_title_ids.setter
    def current_title_ids(self, value):
        self.ctx.current_title_ids = value

    @property
    def current_day_of_week(self):
        return self.ctx.current_day_of_week

    @current_day_of_week.setter
    def current_day_of_week(self, value):
        self.ctx.current_day_of_week = value

    @property
    def current_show_mode(self):
        return self.ctx.current_show_mode

    @current_show_mode.setter
    def current_show_mode(self, value):
        self.ctx.current_show_mode = value

    @property
    def current_offset(self):
        return self.ctx.current_offset

    @current_offset.setter
    def current_offset(self, value):
        self.ctx.current_offset = value

    @property
    def current_data(self):
        return self.ctx.current_data

    @current_data.setter
    def current_data(self, value):
        self.ctx.current_data = value

    @property
    def total_titles(self):
        return self.ctx.total_titles

    @total_titles.setter
    def total_titles(self, value):
        self.ctx.total_titles = value

    @property
    def current_titles(self):
        return self.ctx.current_titles

    @current_titles.setter
    def current_titles(self, value):
        self.ctx.current_titles = value

    @property
    def am_total_count(self):
        return self.ctx.am_total_count

    @am_total_count.setter
    def am_total_count(self, value):
        self.ctx.am_total_count = value

    @property
    def playlists(self):
        return self.ctx.playlists

    @playlists.setter
    def playlists(self, value):
        self.ctx.playlists = value

    @property
    def discovered_links(self):
        return self.ctx.discovered_links

    @discovered_links.setter
    def discovered_links(self, value):
        self.ctx.discovered_links = value

    @property
    def sanitized_titles(self):
        return self.ctx.sanitized_titles

    @sanitized_titles.setter
    def sanitized_titles(self, value):
        self.ctx.sanitized_titles = value

    @property
    def title_search_entry(self):
        return self.ctx.title_search_entry

    @title_search_entry.setter
    def title_search_entry(self, value):
        self.ctx.title_search_entry = value

    @property
    def quality_dropdown(self):
        return self.ctx.quality_dropdown

    @quality_dropdown.setter
    def quality_dropdown(self, value):
        self.ctx.quality_dropdown = value

    @property
    def posters_layout(self):
        return self.ctx.posters_layout

    @posters_layout.setter
    def posters_layout(self, value):
        self.ctx.posters_layout = value

    @property
    def scroll_area(self):
        return self.ctx.scroll_area

    @scroll_area.setter
    def scroll_area(self, value):
        self.ctx.scroll_area = value

    @property
    def poster_container(self):
        return self.ctx.poster_container

    @poster_container.setter
    def poster_container(self, value):
        self.ctx.poster_container = value

    @property
    def playlist_filename(self):
        return self.ctx.playlist_filename

    @playlist_filename.setter
    def playlist_filename(self, value):
        self.ctx.playlist_filename = value

    @property
    def stream_video_url(self):
        return self.ctx.stream_video_url

    @stream_video_url.setter
    def stream_video_url(self, value):
        self.ctx.stream_video_url = value

    @property
    def app_version(self):
        return self.ctx.app_version

    @property
    def current_template(self):
        return self.ctx.current_template

    @property
    def user_id(self):
        return self.ctx.user_id

    @property
    def titles_batch_size(self):
        return self.ctx.titles_batch_size

    @property
    def titles_list_batch_size(self):
        return self.ctx.titles_list_batch_size

    # =========================================================================
    # PRIVATE HELPERS
    # =========================================================================

    def _get_cfg(self, section: str, option: str, default) -> any:
        """Получает значение из конфигурации."""
        try:
            return self.config_manager.get_setting(section, option)
        except Exception:
            return default

    def _get_cfg_bool(self, section: str, key: str, default: bool = False) -> bool:
        """Получает булево значение из конфигурации."""
        val = self._get_cfg(section, key, default)
        return str(val).lower() in ("1", "true", "yes", "on")

    def _setup_paths(self) -> tuple[str, str]:
        """Настраивает пути к приложениям."""
        video_player_path = self.config_manager.get_video_player_path()
        torrent_client_path = self.config_manager.get_torrent_client_path()
        return video_player_path, torrent_client_path

    @staticmethod
    def _default_data_dir(app_name: str = "AnimePlayer") -> pathlib.Path:
        """Возвращает директорию данных по умолчанию."""
        if sys.platform.startswith("win"):
            base = pathlib.Path(os.getenv("APPDATA", pathlib.Path.home() / "AppData" / "Roaming"))
        elif sys.platform == "darwin":
            base = pathlib.Path.home() / "Library" / "Application Support"
        else:
            base = pathlib.Path(os.getenv("XDG_DATA_HOME", pathlib.Path.home() / ".local" / "share"))
        return base / app_name

    @staticmethod
    def calc_offset(offset: int, total: int, page_size: int, go_forward: bool) -> int:
        """Вычисляет новый offset для пагинации."""
        if total <= 0:
            return 0
        if go_forward:
            return 0 if offset + page_size >= total else offset + page_size
        return max(0, offset - page_size)

    # =========================================================================
    # EVENT HANDLERS
    # =========================================================================

    def on_link_click(self, url) -> None:
        """Обрабатывает клик по ссылке."""
        link = url.toString()
        self.link_handler.handle(link)

    @pyqtSlot(QTextBrowser, int, int)
    def _on_add_title_browser_to_layout(self, title_browser, row, column) -> None:
        """Добавляет title browser в layout."""
        if self.ctx.posters_layout:
            self.ctx.posters_layout.addWidget(title_browser, row, column)

    def closeEvent(self, event) -> None:
        """Обрабатывает закрытие окна."""
        QApplication.instance().quit()