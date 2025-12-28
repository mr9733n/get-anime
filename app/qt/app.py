import os
import pathlib
import re
import sys
import json
import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import List, Any, Dict, Union, Optional
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QTextBrowser, QApplication, QLabel, QSystemTrayIcon, QStyle, QDialog
from PyQt5.QtCore import QTimer, QThreadPool, pyqtSlot, pyqtSignal, Qt, QSharedMemory
from app.qt.app_state_manager import AppStateManager
from app.qt.app_handlers import LinkActionHandler
from app.qt.ui_am_generator import UIAMGenerator
from app.qt.app_helpers import TitleDisplayFactory, TitleDataFactory
from app.qt.ui_manger import UIManager
from app.qt.ui_generator import UIGenerator
from app.qt.ui_s_generator import UISGenerator

from app.qt.app_exceptions import APIClientError
from app.qt.app_state import ViewState, TitleRef

from static.layout_metadata import all_layout_metadata
from providers.aniliberty.v1.api import APIClient
from providers.aniliberty.v1.adapter import APIAdapter
from providers.animedia.v0.cache_manager import AniMediaCacheManager, AniMediaCacheStatus, AniMediaCacheConfig
from providers.animedia.v0.qt_async_worker import AsyncWorker
from providers.animedia.v0 import create_adapter
from utils.config.config_manager import ConfigManager
from utils.downloads.poster_manager import PosterManager
from utils.downloads.torrent_manager import TorrentManager
from utils.playlists.playlist_manager import PlaylistManager
from utils.playlists.playlist_key import calc_bundle_key
from utils.integrations.open_router import OpenRouter, PlaylistTargets
from utils.net.net_client import NetClient
from utils.net.url_resolve_service import UrlResolveService
from utils.net.url_resolver import TTLCache
from utils.net.url_resolver_config import ResolverConfig

from app.qt.app_constants import (
    PROVIDER_ANILIBERTY,
    PROVIDER_ANIMEDIA,
    SHOW_DEFAULT,
    SHOW_SYSTEM,
    SHOW_ONE_TITLE,
    SHOW_AM_SCHEDULE,
    SHOW_AM_TITLES,
    DEFAULT_TEMPLATE,
    APP_WIDTH,
    APP_HEIGHT,
    APP_X_POS,
    APP_Y_POS,
)


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

        self.callbacks = self.generate_callbacks()
        days_of_week = ["MO", "TU", "WE", "TH", "FR", "SA", "SU"]
        for i, day in enumerate(days_of_week):
            self.callbacks[f"display_titles_for_day_{i}"] = lambda checked, i=i: self.display_titles_for_day(i + 1)

        app = QApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(self.api_client.close)

        self.init_ui()

    def _get_cfg(self, section: str, option: str, default: Any, *, lower: bool = False) -> Any:
        """
        Возвращает значение из конфигурации.
        Если чтение падает – возвращает `default`.
        Параметр `lower` приводит строку к нижнему регистру (удобно для булевых флагов).
        """
        try:
            value = self.config_manager.get_setting(section, option)
            return value.lower() if lower and isinstance(value, str) else value
        except Exception:
            return default

    def closeEvent(self, event):
        QApplication.instance().quit()  # Завершает все окна приложения

    @pyqtSlot(QTextBrowser, int, int)
    def on_add_title_browser_to_layout(self, title_browser, row, column):
        self.posters_layout.addWidget(title_browser, row, column)

    def setup_paths(self):
        """Sets up paths based on the current platform and returns them for use."""
        video_player_path = self.config_manager.get_video_player_path()
        torrent_client_path = self.config_manager.get_torrent_client_path()
        # Return paths to be used in the class
        return video_player_path, torrent_client_path

    def init_ui(self):
        self.setWindowTitle(f'Anime Player App {self.app_version}')
        self.setGeometry(APP_X_POS, APP_Y_POS, APP_WIDTH, APP_HEIGHT)
        self.setMinimumSize(APP_WIDTH, APP_HEIGHT)

        if self.current_template == DEFAULT_TEMPLATE:
            self.setStyleSheet("""
                QWidget {
                    background-color: rgba(240, 240, 240, 1.0);
                }
            """)
        elif self.current_template == "no_background_night":
            self.setStyleSheet("""
                QWidget {
                    background-color: rgba(140, 140, 140, 1.0);
                }
            """)
        elif self.current_template == "no_background":
            self.setStyleSheet("""
                QWidget {
                    background-color: rgba(220, 220, 220, 1.0);
                }
            """)
        main_layout = QVBoxLayout()

        self.ui_manager.setup_main_layout(main_layout, all_layout_metadata, self.callbacks)
        self.setLayout(main_layout)

        self.title_search_entry = self.ui_manager.parent_widgets.get("title_input")
        self.quality_dropdown = self.ui_manager.parent_widgets.get("quality_dropdown")

    def show_error_notification(self, title, message):
        """Показывает всплывающее уведомление об ошибке."""
        self.error_label = QLabel(message, self)
        self.error_label.setWordWrap(True)
        self.error_label.setStyleSheet("""
            QLabel {
                background-color: rgba(255, 0, 0, 0.9);
                color: white;
                font-size: 14px;
                padding: 6px;
                border-radius: 4px;
            }
        """)
        self.error_label.setAlignment(Qt.AlignJustify)
        self.error_label.setGeometry(50, 50, 500, 50)

        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(self.style().standardIcon(QStyle.SP_MessageBoxWarning))

        self.error_label.show()
        self.tray_icon.show()

        QTimer.singleShot(5000, self.error_label.hide)
        QTimer.singleShot(5000, self.tray_icon.hide)
        self.tray_icon.showMessage(title, message, QSystemTrayIcon.Warning, 5000)

    def set_view_state(self, state: ViewState) -> None:
        self.view_state = state
        self.current_show_mode = state.show_mode
        self.current_title_id = state.title_id
        self.current_title_ids = state.title_ids
        self.current_day_of_week = state.day_of_week

    def refresh_display(self):
        try:
            q = self.quality_dropdown.currentText()
            self.clear_previous_posters()

            state = self.view_state
            if state.show_mode == SHOW_AM_SCHEDULE:
                self.display_animedia_schedule_screen()
                return
            elif state.show_mode == SHOW_AM_TITLES:
                self.display_animedia_titles_screen()
                return
            elif state.show_mode == SHOW_SYSTEM:
                self.display_titles(show_mode=SHOW_SYSTEM)
                return

            if state.title_id is not None:
                titles = self.db_manager.get_titles_from_db(title_id=state.title_id)
            elif state.title_ids:
                titles = self.db_manager.get_titles_from_db(title_ids=state.title_ids)
            elif state.day_of_week is not None:
                titles = self.db_manager.get_titles_from_db(day_of_week=state.day_of_week)
            else:
                titles = self.current_titles or []

            updated = [self.update_title_links(t, q) for t in titles]
            self.display_titles_in_ui(updated)

        except Exception as e:
            self.logger.error(f"Ошибка REFRESH: {e}")

    def update_title_links(self, title, selected_quality):
        """Обновляет ссылки на эпизоды для заданного качества."""
        if selected_quality == 'fhd':
            title.current_links = [ep.hls_fhd for ep in title.episodes if ep.hls_fhd]
        elif selected_quality == 'hd':
            title.current_links = [ep.hls_hd for ep in title.episodes if ep.hls_hd]
        elif selected_quality == 'sd':
            title.current_links = [ep.hls_sd for ep in title.episodes if ep.hls_sd]
        else:
            self.logger.warning(f"Неизвестное качество: {selected_quality}, используем ссылки по умолчанию.")

        # Логирование обновленных ссылок
        self.logger.debug(f"Обновлены ссылки для тайтла {title.title_id}: {title.current_links}")
        return title

    def reload_schedule(self):
        """Обновляет и отображает расписание тайтлов."""
        try:
            day = self.current_day_of_week
            if not day:
                day = 1  # Monday (1–7)

            current_titles = self.total_titles if self.total_titles else set()
            status, new_title_ids = self.check_and_update_schedule(day, current_titles)
            self.current_title_id = None

            if status and new_title_ids:
                self.display_titles_for_day(day, force_reload=False)
            else:
                self.display_titles_for_day(day, force_reload=True)
        except Exception as e:
            self.logger.error(f"Ошибка при обновлении reload_schedule: {e}")

    def generate_callbacks(self):
        callbacks = {
            "get_search_by_title": self.get_search_by_title,
            "get_search_by_title_all": self.get_search_by_title_aniliberty,
            "get_search_by_title_am": self.get_search_by_title_animedia,
            "get_update_title": self.get_update_title,
            "get_update_title_all": self.get_update_title_aniliberty,
            "get_update_title_am": self.get_update_title_animedia,
            "get_random_title": self.get_random_title,
            "get_animedia_new_titles": self.get_animedia_new_titles,
            "get_animedia_all_titles": self.get_animedia_all_titles,
            "refresh_display": self.refresh_display,
            "save_playlist_wrapper": self.save_playlist_wrapper,
            "play_playlist_wrapper": self.play_playlist_wrapper,
            "reload_schedule": self.reload_schedule,
        }

        for metadata in all_layout_metadata:
            callback_key = metadata.get("callback_key")
            callback_type = metadata.get("callback_type", "complex")

            if callback_key and callback_type == "simple" and callback_key not in callbacks:
                callbacks[callback_key] = self.generate_simple_callback(callback_key)

        return callbacks

    def generate_simple_callback(self, callback_name):
        """Создает простой колбек, который вызывает display_titles с соответствующими параметрами."""

        def simple_callback(*args, **kwargs):
            self.logger.info(f"Вызван простой колбек: {callback_name}")
            if callback_name == "load_previous_titles":
                self.display_titles(show_previous=True)
            elif callback_name == "load_more_titles":
                self.display_titles(show_next=True)
            elif callback_name == "display_titles_text_list":
                self.display_titles(show_mode='titles_list', batch_size=self.titles_list_batch_size)
            elif callback_name == "display_ongoing_list":
                self.display_titles(show_mode='ongoing_list', batch_size=self.titles_list_batch_size)
            elif callback_name == "display_franchises":
                self.display_titles(show_mode='franchise_list', batch_size=self.titles_list_batch_size)
            elif callback_name == "toggle_need_to_see":
                self.display_titles(show_mode='need_to_see_list', batch_size=self.titles_list_batch_size)
            elif callback_name == "display_system":
                self.display_titles(show_mode='system')
            else:
                self.logger.warning(f"Неизвестный колбек: {callback_name}")

        return simple_callback

    def get_current_state(self) -> Dict[str, Any]:
        """Return a serialisable snapshot of the current UI state."""
        return {
            "current_title_id": self.current_title_id,
            "current_title_ids": self.current_title_ids,
            "current_day": self.current_day_of_week,
            "player_offset": self.current_offset,
            "template_name": self.current_template,
            "show_mode": self.current_show_mode,
        }

    def _restore_day(self, day: int) -> None:
        self.logger.info("Restoring schedule for %s", day)
        self.current_day_of_week = day
        self.display_titles_for_day(day)

    def _restore_title(self, title_id: int) -> None:
        self.logger.info("Restoring title %s", title_id)
        self.display_info(title_id)

    def _restore_titles(
        self,
        title_ids: Union[str, List[int]],
        show_mode: str,
    ) -> None:
        """Restore a list of titles, accepting JSON‑encoded strings."""
        if isinstance(title_ids, str):
            try:
                self.logger.info("Restoring titles from JSON")
                title_ids = json.loads(title_ids)
            except json.JSONDecodeError:
                self.logger.error("Failed to decode title IDs JSON")
                title_ids = []

        count = len(title_ids)
        if count >= 12:
            self.logger.info(
                "Using titles_list mode for %d titles (show_mode=%s)",
                count,
                show_mode,
            )
            self.display_titles(
                show_mode=show_mode,
                batch_size=self.titles_list_batch_size,
                title_ids=title_ids,
            )
        else:
            self.logger.info("Using default mode for %d titles", count)
            self.display_titles(title_ids=title_ids)

    def restore_state(self, state: Dict[str, Any]) -> None:
        """Re-create the UI from a previously saved snapshot."""
        try:
            self.current_template = state.get("template_name", DEFAULT_TEMPLATE)
            self.logger.info("Restored template: %s", self.current_template)

            if "player_offset" in state:
                try:
                    self.current_offset = int(state["player_offset"])
                except (TypeError, ValueError):
                    self.current_offset = 0
                self.logger.info("Offset restored: %d", self.current_offset)

            day = state.get("current_day")
            title_id = state.get("current_title_id")
            title_ids = state.get("current_title_ids")
            show_mode = state.get("show_mode", SHOW_DEFAULT)

            has_day = day is not None
            has_title_id = title_id is not None
            has_title_ids = bool(title_ids)

            if has_day and not has_title_id and not has_title_ids:
                self._restore_day(day)
            elif has_day and has_title_id and not has_title_ids:
                self._restore_title(title_id)
            elif not has_day and has_title_id:
                self._restore_title(title_id)
            elif has_title_ids:
                self._restore_titles(title_ids, show_mode)
            elif show_mode == SHOW_AM_SCHEDULE:
                self.display_animedia_schedule_screen()
            elif show_mode == SHOW_AM_TITLES:
                self.display_animedia_titles_screen()
            elif show_mode == SHOW_SYSTEM:
                self.display_titles(show_mode=SHOW_SYSTEM)
            else:
                self.logger.info("Falling back to offset-based restore")
                self.display_titles(start=True)

        except Exception as exc:
            self.logger.exception("Error restoring app state: %s", exc)

    def _navigate_animedia_mode(self, show_mode: str, go_forward: bool) -> bool:
        st = self.view_state or ViewState(show_mode=show_mode)

        # total_count уже посчитан при display_* и лежит в self._am_total_count
        total_count = int(self._am_total_count or 0)

        new_offset = self._calc_offset(st.am_offset, total_count, st.am_page_size, go_forward)

        self.set_view_state(ViewState(
            show_mode=show_mode,
            am_offset=new_offset,
            am_page_size=st.am_page_size,
        ))

        display_fn = self._animedia_display_for_mode(show_mode)
        if not display_fn:
            return False
        display_fn()
        return True

    def _animedia_display_for_mode(self, mode: str):
        return {
            SHOW_AM_SCHEDULE: self.display_animedia_schedule_screen,
            SHOW_AM_TITLES: self.display_animedia_titles_screen,
        }.get(mode)

    def navigate_pagination(self, go_forward=True):
        """
        Навигация по страницам текущих результатов (любых списков тайтлов)
        """
        try:
            show_mode = getattr(self, 'current_show_mode', 'default')
            batch_size = 12  # TODO: default size = 12

            if show_mode in (SHOW_AM_SCHEDULE, SHOW_AM_TITLES):
                if self._navigate_animedia_mode(show_mode, go_forward):
                    return

            if self.current_title_ids:
                total_count = len(self.current_title_ids)
                self.current_offset = self._update_pagination_offset(total_count, batch_size, go_forward)
                self.logger.debug(
                    f"Navigation: offset={self.current_offset}, batch_size={batch_size}, total={total_count}")
                self.display_titles(title_ids=self.current_title_ids, batch_size=batch_size, show_mode=show_mode)
            else:
                total_count = self.db_manager.get_total_titles_count(show_mode=show_mode)
                self.current_offset = self._update_pagination_offset(total_count, batch_size, go_forward)
                self.logger.debug(
                    f"Navigation: offset={self.current_offset}, batch_size={batch_size}, total={total_count}")
                self.display_titles(batch_size=batch_size, show_mode=show_mode)

        except Exception as e:
            self.logger.error(f"Ошибка при навигации по результатам: {e}")

    def display_titles(self, title_ids=None, batch_size=None, show_mode='default', show_previous=False, show_next=False,
                       start=False):
        try:
            self.ui_manager.show_loader("Loading titles...")
            self.ui_manager.set_buttons_enabled(False)

            if not isinstance(title_ids, list):
                try:
                    title_ids = list(title_ids) if title_ids is not None else None
                except TypeError:
                    title_ids = title_ids

            if start:
                self.logger.debug(
                    f"START: current_offset: {self.current_offset} - titles_batch_size: {self.titles_batch_size}")

            if show_next or show_previous:
                statistics = self.db_manager.get_statistics_from_db() if show_next else None
                total_available_titles = statistics.get('titles_count', 0) if show_next else 0

                if show_next:
                    self.current_offset = self._update_pagination_offset(
                        total_available_titles,
                        self.titles_batch_size,
                        go_forward=True
                    )
                    self.logger.debug(
                        f"NEXT: current_offset: {self.current_offset} - titles_batch_size: {self.titles_batch_size}")
                elif show_previous:
                    self.current_offset = max(0, self.current_offset - self.titles_batch_size)
                    self.logger.debug(
                        f"PREV: current_offset: {self.current_offset} - titles_batch_size: {self.titles_batch_size}")

            data_factory = TitleDataFactory(self.db_manager, self.user_id)
            titles = data_factory.get_titles(
                show_mode=show_mode,
                title_ids=title_ids,
                current_offset=self.current_offset,
                batch_size=batch_size
            )

            self.current_title_ids = [t.title_id for t in titles if getattr(t, "title_id", None) is not None]
            self.set_view_state(ViewState(show_mode=show_mode, title_ids=self.current_title_ids))
            description = data_factory.get_metadata_description(show_mode=show_mode)
            show_modes = ['titles_list', 'franchise_list', 'need_to_see_list', 'ongoing_list']

            if not titles and description:
                self.logger.info("Нет доступных данных для отображения, сбрасываем оффсет.")
                self.current_offset = 0
                self.total_titles = 0
                return

            if title_ids and len(title_ids) > 0:
                if self.current_offset >= len(title_ids):
                    self.logger.warning(
                        f"Offset {self.current_offset} превышает количество доступных title_ids {len(title_ids)}. Сбрасываем offset.")
                    self.current_offset = 0

                if batch_size:
                    self._setup_pagination_ui(len(title_ids), batch_size, description)
                else:
                    pagination_widget = self.ui_manager.parent_widgets.get("pagination_widget")
                    if pagination_widget:
                        pagination_widget.setVisible(False)
            elif show_mode in show_modes:
                self.logger.info(f"Was sent to display {show_mode} ")
                count_titles = self.db_manager.get_total_titles_count(show_mode=show_mode)
                self._setup_pagination_ui(count_titles, batch_size, description)
            else:
                pagination_widget = self.ui_manager.parent_widgets.get("pagination_widget")
                if pagination_widget:
                    pagination_widget.setVisible(False)

            self.display_titles_in_ui(titles, show_mode)
            self.logger.debug(f"Was sent to display {show_mode} {len(titles)} titles.")
            if isinstance(self.total_titles, list):
                self.logger.debug(f"self.total_titles: {len(self.total_titles)}")
            else:
                self.logger.debug(
                    f"self.total_titles is not a list, but {type(self.total_titles).__name__}: {self.total_titles}")

        except Exception as e:
            self.logger.error(f"Ошибка display_titles: {e}")
        finally:
            self.ui_manager.hide_loader()
            self.ui_manager.set_buttons_enabled(True)

    @staticmethod
    def _calc_offset(offset: int, total: int, page_size: int, go_forward: bool) -> int:
        if total <= 0:
            return 0
        if go_forward:
            return 0 if offset + page_size >= total else offset + page_size
        return max(0, offset - page_size)

    def _update_pagination_offset(self, total_count, batch_size, go_forward=True):
        """
        Обновляет текущий offset для пагинации на основе направления навигации.

        Args:
            total_count: общее количество элементов
            batch_size: размер страницы
            go_forward: направление навигации (True - вперед, False - назад)

        Returns:
            Новое значение offset
        """
        if go_forward:
            if self.current_offset + batch_size >= total_count:
                self.logger.info("End of the list, return to beginning")
                return 0
            else:
                return self.current_offset + batch_size
        else:
            return max(0, self.current_offset - batch_size)

    def _setup_pagination_ui(self, count_titles, batch_size, description=None):
        """
        Настраивает отображение пагинации в UI.

        Args:
            count_titles: общее количество элементов
            batch_size: размер страницы
            description: описание текущего режима отображения
        """
        total_pages = (count_titles + batch_size - 1) // batch_size  # Округление вверх
        current_page = (self.current_offset // batch_size) + 1

        # Обновляем информацию о пагинации в UI
        self.ui_manager.update_pagination_info(current_page, total_pages, count_titles, description)

        # Показываем виджет пагинации только если страниц больше одной
        pagination_widget = self.ui_manager.parent_widgets.get("pagination_widget")
        if pagination_widget:
            pagination_widget.setVisible(total_pages > 1)


    def display_titles_in_ui(self, titles, show_mode='default', row_start=0, col_start=0):
        try:
            special_modes = {SHOW_SYSTEM, SHOW_AM_SCHEDULE, SHOW_AM_TITLES}
            self.clear_previous_posters()

            factory = TitleDisplayFactory(self)

            if show_mode in special_modes:
                widget, _ = factory.create(show_mode, titles)  # titles тут целиком список блоков/данных
                self.posters_layout.addWidget(widget, 0, 0, 1, 2)
            elif len(titles) == 1:
                widget, _ = factory.create(SHOW_ONE_TITLE, titles[0])
                self.posters_layout.addWidget(widget, 0, 0, 1, 2)
            else:
                for index, title in enumerate(titles):
                    title_widget, num_columns = factory.create(show_mode, title)
                    row = (index + row_start) // num_columns
                    column = (index + col_start) % num_columns
                    self.posters_layout.addWidget(title_widget, row, column)

            self.logger.debug(f"Displayed {show_mode} with {len(titles)} titles.")
            app_state = self.get_current_state()
            QTimer.singleShot(100, lambda: self.state_manager.save_state(app_state))
        except Exception as e:
            self.logger.error(f"Ошибка display_titles_in_ui: {e}")

    def display_info(self, title_id):
        """Отображает информацию о конкретном тайтле."""
        try:
            self.ui_manager.show_loader("Loading title...")
            self.ui_manager.set_buttons_enabled(False)

            self.clear_previous_posters()
            titles = self.db_manager.get_titles_from_db(title_id=title_id)

            if not titles or titles[0] is None:
                self.logger.error(f"Title with title_id {title_id} not found in the database.")
                return

            self.total_titles = titles
            self.set_view_state(ViewState(show_mode=SHOW_DEFAULT, title_id=title_id))

            pagination_widget = self.ui_manager.parent_widgets.get("pagination_widget")
            if pagination_widget:
                pagination_widget.setVisible(False)

            self.display_titles_in_ui(titles)
        except Exception as e:
            self.logger.error(f"Error display_info: {e}")

        finally:
            self.ui_manager.hide_loader()
            self.ui_manager.set_buttons_enabled(True)

    def display_titles_for_day(self, day_of_week, force_reload=False):
        """
        Отображает тайтлы для указанного дня недели.

        Args:
            day_of_week (int): День недели.
            force_reload (bool): Принудительно загрузить данные с сервера.
        """
        try:
            self.ui_manager.show_loader("Loading schedule...")
            self.ui_manager.set_buttons_enabled(False)

            self.clear_previous_posters()
            self.set_view_state(ViewState(show_mode=SHOW_DEFAULT, day_of_week=day_of_week))

            pagination_widget = self.ui_manager.parent_widgets.get("pagination_widget")
            if pagination_widget:
                pagination_widget.setVisible(False)

            titles = None
            if not force_reload:
                titles = self.db_manager.get_titles_from_db(show_all=False, day_of_week=day_of_week)
                self.logger.debug(f"day_of_week: {day_of_week}, titles from DB: {len(titles)}")
            if titles:
                self.total_titles = {title.title_id for title in titles}
                self.display_titles_in_ui(titles)
            else:
                status, new_title_ids = self.fetch_and_process_schedule(day_of_week)
                if status and new_title_ids:
                    titles = self.db_manager.get_titles_from_db(day_of_week=day_of_week)
                    self.total_titles = {title.title_id for title in titles}
                    self.display_titles_in_ui(titles)
                else:
                    self.display_titles(start=True)

        except Exception as e:
            self.logger.error(f"Error displaying titles for day: {e}")
        finally:
            self.ui_manager.hide_loader()
            self.ui_manager.set_buttons_enabled(True)

    def _save_parsed_data(self, parsed_data):
        for i, item in enumerate(parsed_data):
            self.db_manager.save_schedule(item["day"], item["title_id"], last_updated=datetime.now(timezone.utc))
            # TODO: fix this. need to count as dict
            self.logger.debug(
                f"[{i + 1}/{len(parsed_data)}] Saved title_id from API: {item['title_id']} on day {item['day']}")

    def _save_titles_list(self, titles_list):
        try:
            for title_data in titles_list:
                external_id = title_data.get('external_id', {})
                self.logger.debug(
                f"[XXX] Saving external_id from API: {external_id}")
            title_ids = self.invoke_database_save(titles_list)
            self.current_data = titles_list
            return title_ids
        except Exception as e:
            self.logger.error(f"Ошибка при save titles расписания: {e}")

    def clear_layout(self, layout):
        """Рекурсивно очищает все элементы из переданного layout."""
        if layout is not None:
            while layout.count():
                item = layout.takeAt(0)
                widget_to_remove = item.widget()
                if widget_to_remove is not None:
                    widget_to_remove.deleteLater()
                elif item.layout() is not None:
                    self.clear_layout(item.layout())

    def create_system_browser(self, statistics):
        """
        Прокси-метод, который делегирует создание system_browser в UISGenerator.
        """
        template = self.current_template
        self.logger.debug(f"Пытаемся создать system_browser с параметрами: {len(statistics)}")
        return self.ui_s_generator.create_system_browser(statistics, template)

    def create_animedia_schedule_browser(self, schedule):
        """
        Прокси-метод, который делегирует создание animedia_schedule_browser в UIAMGenerator.
        """
        self.logger.debug(f"Пытаемся создать animedia_schedule_browser с параметрами: {len(schedule)}")
        return self.ui_am_generator.create_animedia_schedule_browser(schedule)

    def create_animedia_titles_browser(self, titles):
        """
        Прокси-метод, который делегирует создание animedia_titles_browser в UIAMGenerator.
        """
        self.logger.debug(f"Пытаемся создать animedia_titles_browser с параметрами: {len(titles)}")
        return self.ui_am_generator.create_animedia_titles_browser(titles)

    def create_title_browser(self, title, show_mode=SHOW_DEFAULT):
        """
        Прокси-метод, который делегирует создание title_browser в UIGenerator.
        """
        return self.ui_generator.create_title_browser(title, show_mode=show_mode)

    def invoke_database_save(self, title_list: list[dict]) -> list[int]:
        """
        Сохраняет тайтлы + эпизоды + торренты.
        Возвращает список ВНУТРЕННИХ title_id из БД.
        """
        self.logger.debug(f"Processing title data: {len(title_list)}")
        internal_ids: list[int] = []

        processes = {
            self.db_manager.process_episodes: "episodes",
            self.db_manager.process_torrents: "torrents",
        }

        for raw_title_data in title_list:
            title_ok, title_id = self.db_manager.process_titles(raw_title_data)

            if not title_ok or title_id is None:
                self.logger.warning(
                    f"Failed to process title (external_id={raw_title_data.get('external_id')}, "
                    f"provider={raw_title_data.get('provider')})"
                )
                continue

            internal_ids.append(title_id)
            payload = {"title_id": title_id, **raw_title_data}

            for process_func, process_name in processes.items():
                try:
                    result = process_func(payload)
                    if result:
                        self.logger.debug(
                            f"Successfully saved {process_name} table for title_id={title_id}. STATUS: {result}")
                    else:
                        self.logger.warning(f"Failed to process {process_name} for title_id={title_id}")
                except Exception as e:
                    self.logger.error(f"Exception while processing {process_name} for title_id={title_id}: {e}")

        return internal_ids

    def _resolve_titles_for_query(self, search_text: str) -> list[TitleRef]:
        """Ищет тайтлы в БД и приводит результат к единому виду."""
        titles_list = self.db_manager.get_titles_search_query(search_text)
        results: list[TitleRef] = []

        for t in titles_list:
            title_id = t.get("title_id")
            name_ru = t.get("name_ru")
            name_en = t.get("name_en")
            providers = t.get("providers", []) or []

            if providers:
                primary = providers[0]
                provider = primary.get("provider")
                provider_name = primary.get("name")
                external_id = primary.get("external_id")
            else:
                provider = None
                external_id = None

            self.logger.info(
                f"Found title: {title_id}, {name_ru}, {name_en}, {provider}, {provider_name}, {external_id}"
            )

            if title_id is None:
                continue

            results.append(
                TitleRef(
                    title_id=title_id,
                    name_ru=name_ru,
                    name_en=name_en,
                    provider=provider,
                    provider_name=provider_name,
                    external_id=external_id,
                )
            )

        return results

    def _update_titles(self, provider_filter: str | None) -> bool:
        """
        Общая логика обновления тайтлов.
        :param provider_filter:
            None               → авто (по полю provider у тайтла)
            PROVIDER_ANILIBERTY → только AniLiberty
            PROVIDER_ANIMEDIA   → только AniMedia
        """
        try:
            self.ui_manager.show_loader("Updating title info...")
            self.ui_manager.set_buttons_enabled(False)

            search_text = self.title_search_entry.text().strip()
            if not search_text:
                if self.current_title_ids:
                    search_text = ",".join(str(tid) for tid in self.current_title_ids)
                elif self.current_title_id is not None:
                    search_text = str(self.current_title_id)
                else:
                    self.logger.warning("Unable to update title(s): missing title ID(s)")
                    self.show_error_notification("Error", "Unable to update title(s): missing title ID(s)")
                    return False
                self.logger.debug(f"Used current title_id(s): {search_text} for update")
            else:
                self.title_search_entry.clear()

            self.logger.info(f"Updating title(s). Keywords: {search_text}")
            titles = self._resolve_titles_for_query(search_text)
            if not titles:
                self.logger.warning(f"No titles found in DB for update by query: {search_text}")
                self.show_error_notification("Update", "No titles found for update.")
                return False

            for tref in titles:
                self.logger.info(
                    f"Updating title: {tref.title_id}, {tref.name_ru}, {tref.name_en}, "
                    f"{tref.provider}, {tref.external_id}"
                )
                if provider_filter is not None and tref.provider != provider_filter:
                    self.logger.info(
                        f"Skip title_id={tref.title_id}: provider={tref.provider}, filter={provider_filter}"
                    )
                    continue
                if tref.provider == PROVIDER_ANILIBERTY or provider_filter == PROVIDER_ANILIBERTY:
                    query_name = str(tref.external_id or tref.title_id) or tref.name_en or tref.name_ru
                    self.logger.info(f"Updating via AniLiberty API: query={query_name}")
                    title_ids = self._handle_get_titles_from_api(query_name)
                    if title_ids:
                        self._handle_found_titles(title_ids, query_name)
                    continue
                if tref.provider == PROVIDER_ANIMEDIA or provider_filter == PROVIDER_ANIMEDIA:
                    query_name = tref.name_en or tref.name_ru or str(tref.external_id or tref.title_id)

                    self.logger.info(f"Updating via AniMedia: query={query_name}")
                    self._last_search_text = query_name
                    self._animedia_worker = AsyncWorker(
                        self.animedia_adapter.get_by_title,
                        query_name,
                        max_titles=5,
                    )
                    self._animedia_worker.finished.connect(self._on_animedia_result)
                    self._animedia_worker.error.connect(self._on_animedia_error)
                    self._animedia_worker.start()
                    continue

                self.logger.warning(
                    f"Unknown or missing provider for title_id={tref.title_id}: {tref.provider} "
                    f"(filter={provider_filter})"
                )

            return True

        except Exception as e:
            self.logger.error(f"Error on update title(s): {e}")
            return False
        finally:
            # TODO: для асинхронного пути Animedia надо делать внутри рутин
            self.ui_manager.hide_loader()
            self.ui_manager.set_buttons_enabled(True)

    def get_update_title(self):
        """Обновление с авто-определением провайдера."""
        return self._update_titles(provider_filter=None)

    def get_update_title_aniliberty(self):
        """Обновление только через AniLiberty."""
        return self._update_titles(provider_filter=PROVIDER_ANILIBERTY)

    def get_update_title_animedia(self):
        """Обновление только через AniMedia."""
        return self._update_titles(provider_filter=PROVIDER_ANIMEDIA)

    def _search_by_title(self, provider_filter: str | None, search_text: str | None) -> bool:
        """
        Общая логика поиска тайтлов по названию.
        :param provider_filter:
            None                → авто: ищем в БД у всех, fallback AniLiberty + Animedia
            PROVIDER_ANILIBERTY → фокус на AniLiberty (БД + AniLiberty)
            PROVIDER_ANIMEDIA   → фокус на Animedia (БД + Animedia)
        """
        try:
            self.ui_manager.show_loader("Fetching by title...")
            self.ui_manager.set_buttons_enabled(False)

            if not search_text:
                search_text = self.title_search_entry.text().strip()
            self.title_search_entry.clear()
            if not search_text:
                return False

            self.logger.debug(f"keywords: {search_text}")
            title_ids, providers = self.db_manager.get_titles_by_keywords(search_text)

            def providers_match_filter() -> bool:
                if provider_filter is None:
                    return True
                non_empty = [p for p in providers if p]
                if not non_empty:
                    return False
                return all(p == provider_filter for p in non_empty)

            if title_ids and providers_match_filter():
                self.logger.info(
                    f"Found {len(title_ids)} titles in local DB for '{search_text}' "
                    f"(filter={provider_filter})"
                )
                self._handle_found_titles(title_ids, search_text)
                return True

            self.logger.info(
                f"No suitable titles in local DB for '{search_text}' (filter={provider_filter})."
            )

            if provider_filter in (None, PROVIDER_ANILIBERTY):
                try:
                    self.logger.info("...Try to load from AniLiberty provider")
                    title_ids = self._handle_get_titles_from_api(search_text)
                    if title_ids:
                        self.logger.info(
                            f"AniLiberty returned {len(title_ids)} titles for '{search_text}'"
                        )
                        self._handle_found_titles(title_ids, search_text)
                        return True
                except Exception as e:
                    self.logger.warning(f"AniLiberty provider error: {e}")

            if provider_filter in (None, PROVIDER_ANIMEDIA):
                try:
                    self.logger.info("...Try to load from Animedia (async)")
                    self._last_search_text = search_text
                    self._animedia_worker = AsyncWorker(
                        self.animedia_adapter.get_by_title,
                        search_text,
                        max_titles=5,
                    )
                    self._animedia_worker.finished.connect(self._on_animedia_result)
                    self._animedia_worker.error.connect(self._on_animedia_error)
                    self._animedia_worker.start()
                    return True
                except Exception as e:
                    self.logger.error(f"Error starting Animedia worker: {e}")
                    return False

            self.logger.warning(f"No titles found anywhere for '{search_text}'")
            self.show_error_notification("Search", "No titles found.")
            return False

        except Exception as e:
            self.logger.error(f"Error while fetching get_search_by_title: {e}")
            return False
        finally:
            # TODO: для асинхронного пути Animedia надо делать внутри рутин
            self.ui_manager.hide_loader()
            self.ui_manager.set_buttons_enabled(True)

    def get_search_by_title(self):
        """Поиск тайтла: локальная БД → AniLiberty → Animedia."""
        return self._search_by_title(provider_filter=None, search_text=None)

    def get_search_by_title_aniliberty(self):
        """Поиск тайтла: локальная БД → AniLiberty."""
        return self._search_by_title(provider_filter=PROVIDER_ANILIBERTY, search_text=None)

    def get_search_by_title_animedia(self, search_text=None):
        """Поиск тайтла: локальная БД (где провайдер = Animedia) → Animedia (async)."""
        if search_text:
            return self._search_by_title(provider_filter=PROVIDER_ANIMEDIA, search_text=search_text)
        return self._search_by_title(provider_filter=PROVIDER_ANIMEDIA, search_text=None)

    def _handle_found_titles(self, title_ids, search_text):
        if len(title_ids) == 1:
            self.display_info(title_ids[0])
        else:
            self.logger.debug(f"Get titles from DB with title_ids: {title_ids} by keyword {search_text}")
            self.display_titles(title_ids)


    def _handle_get_titles_from_api(self, search_text) -> list[int] | None:
        try:
            keywords = search_text.split(',')
            keywords = [kw.strip() for kw in keywords]
            if len(keywords) == 1 and keywords[0].isdigit():
                title_id = int(keywords[0])
                data = self.api_adapter.get_release_full(title_id)
            elif all(kw.isdigit() for kw in keywords):
                title_ids = [int(kw) for kw in keywords]
                data = self.api_adapter.get_releases_full(title_ids)
            else:
                data = self.api_adapter.get_search_by_title(search_text)

            if isinstance(data, dict) and 'error' in data:
                self.logger.error(data['error'])
                self.show_error_notification("API Error", data['error'])
                return

            if isinstance(data, dict) and 'list' in data:
                title_list = data['list']
            elif isinstance(data, dict) and 'external_id' in data:
                title_list = [data]
            elif isinstance(data, list):
                title_list = data
            else:
                self.logger.error("No titles found in the response.")
                self.show_error_notification("Error", "No titles found in the response.")
                return

            if not title_list:
                self.logger.error("No titles found in the response.")
                self.show_error_notification("Error", "No titles found in the response.")
                return

            self.logger.debug(f"Processing title data: {title_list}")
            title_ids = self.invoke_database_save(title_list)

            self.current_data = data
            return title_ids
        except APIClientError as api_error:
            self.logger.error(f"API Client Error: {api_error}")
            self.show_error_notification("API Error", str(api_error))
        except Exception as e:
            self.logger.error(f"Error while fetching title from AL: {e}")
            self.show_error_notification("Error", "Unexpected error. Check logs for details.")

    def on_link_click(self, url):
        link = url.toString()
        self.link_handler.handle(link)

    def reset_offset(self):
        self.current_offset = 0


from app.qt.app_torrents import save_torrent_wrapper

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

from app.qt.app_posters import (
    get_poster_or_placeholder,
    perform_poster_link,
    sanitize_filename,
    standardize_url,
    clear_previous_posters,
)

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

from app.qt.app_aniliberty import (
    fetch_and_process_schedule,
    check_and_update_schedule,
    get_random_title,
    parse_schedule_data,
    get_schedule,
)

AnimePlayerAppVer3.save_torrent_wrapper = save_torrent_wrapper

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

AnimePlayerAppVer3.get_poster_or_placeholder = get_poster_or_placeholder
AnimePlayerAppVer3.perform_poster_link = perform_poster_link
AnimePlayerAppVer3.clear_previous_posters = clear_previous_posters
AnimePlayerAppVer3.sanitize_filename = staticmethod(sanitize_filename)
AnimePlayerAppVer3.standardize_url = staticmethod(standardize_url)

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


