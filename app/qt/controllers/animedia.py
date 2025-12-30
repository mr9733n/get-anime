# app/qt/controllers/animedia.py
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable, Any

from app.qt.app_state import ViewState
from app.qt.app_constants import (
    PROVIDER_ANIMEDIA,
    SHOW_AM_SCHEDULE, SHOW_AM_TITLES,
    SCHEDULE_KEY, ALL_TITLES_KEY,
)
from app.qt.protocols import (
    IDisplayController,
    IStateController,
    IUIManager,
    IDBManager,
)
from providers.animedia.v0.cache_manager import AniMediaCacheStatus
from utils.parsing.animedia import parse_schedule_line

if TYPE_CHECKING:
    from logging import Logger
    from app.qt.app_context import AppContext
    from providers.animedia.v0.adapter import AniMediaAdapter
    from providers.animedia.v0.cache_manager import AniMediaCacheManager


@dataclass
class AniMediaControllerDeps:
    """Явные зависимости AniMediaController"""
    logger: Logger
    db: IDBManager
    ui: IUIManager
    context: AppContext
    animedia_adapter: AniMediaAdapter
    animedia_cache: AniMediaCacheManager

    # Lazy callbacks
    get_display_controller: Callable[[], IDisplayController] | None = None
    get_state_controller: Callable[[], IStateController] | None = None
    get_actions_controller: Callable[[], Any] | None = None  # для on_animedia_error


class AniMediaController:
    """
    Контроллер для работы с AniMedia.
    Управляет расписанием и каталогом тайтлов с AniMedia.
    """

    def __init__(self, deps: AniMediaControllerDeps):
        self._deps = deps
        self._display: IDisplayController | None = None
        self._state: IStateController | None = None
        self._actions: Any | None = None
        self._worker = None  # AsyncWorker instance

    # === Lazy Dependencies ===

    @property
    def display(self) -> IDisplayController:
        if self._display is None:
            if self._deps.get_display_controller:
                self._display = self._deps.get_display_controller()
            else:
                raise RuntimeError("DisplayController not configured")
        return self._display

    @property
    def state(self) -> IStateController:
        if self._state is None:
            if self._deps.get_state_controller:
                self._state = self._deps.get_state_controller()
            else:
                raise RuntimeError("StateController not configured")
        return self._state

    @property
    def actions(self):
        """Для доступа к on_animedia_error."""
        if self._actions is None:
            if self._deps.get_actions_controller:
                self._actions = self._deps.get_actions_controller()
        return self._actions

    # === Simple Properties ===

    @property
    def log(self) -> Logger:
        return self._deps.logger

    @property
    def db(self) -> IDBManager:
        return self._deps.db

    @property
    def ui(self) -> IUIManager:
        return self._deps.ui

    @property
    def ctx(self) -> AppContext:
        return self._deps.context

    @property
    def adapter(self) -> AniMediaAdapter:
        return self._deps.animedia_adapter

    @property
    def cache(self) -> AniMediaCacheManager:
        return self._deps.animedia_cache

    # === Public API: Display Screens ===

    def display_animedia_schedule_screen(self, schedule_json: list | None = None) -> None:
        """Отображает экран расписания AniMedia."""
        st = self._ensure_view_state(SHOW_AM_SCHEDULE)

        if not schedule_json:
            schedule_json = self._load_from_cache(
                SCHEDULE_KEY,
                self.cache.cfg.schedule_ttl,
            )
            if not schedule_json:
                self.get_animedia_new_titles()
                return

        self._display_animedia_screen(
            data_json=schedule_json,
            show_mode=SHOW_AM_SCHEDULE,
            cache_key=SCHEDULE_KEY,
            poster_size="small",
            description="AniMedia — расписание",
        )

    def display_animedia_titles_screen(self, titles_json: list | None = None) -> None:
        """Отображает экран всех тайтлов AniMedia."""
        st = self._ensure_view_state(SHOW_AM_TITLES)

        if not titles_json:
            titles_json = self._load_from_cache(
                ALL_TITLES_KEY,
                self.cache.cfg.all_titles_ttl,
            )
            if not titles_json:
                self.get_animedia_all_titles()
                return

        self.ctx.am_last_loaded_page = max(
            (e.get("page", 0) for e in titles_json),
            default=0
        )
        self.log.debug(f"Last loaded page: {self.ctx.am_last_loaded_page}")

        self._display_animedia_screen(
            data_json=titles_json,
            show_mode=SHOW_AM_TITLES,
            cache_key=ALL_TITLES_KEY,
            poster_size="medium",
            description="AniMedia — все тайтлы",
        )

    # === Public API: Data Fetching ===

    def get_animedia_new_titles(self) -> None:
        """Асинхронно загружает новые тайтлы (расписание)."""
        self._start_async_worker(
            method=self.adapter.get_new_titles,
            callback=self._on_animedia_new_titles,
            loader_message="Loading AniMedia schedule...",
            max_titles=60,
        )

    def get_animedia_all_titles(self) -> None:
        """Асинхронно загружает все тайтлы."""
        self._start_async_worker(
            method=self.adapter.get_all_titles,
            callback=self._on_animedia_all_titles,
            loader_message="Loading AniMedia catalog...",
            max_titles=60,
            pages=5,
        )

    def load_more_titles(self) -> None:
        """Загрузить следующую порцию тайтлов."""
        self._start_async_worker(
            method=self.adapter.load_more_titles,
            callback=self._on_more_titles_loaded,
            loader_message="Loading AniMedia More catalog...",
            pages=5,
        )

    # === Private: Display Helpers ===

    def _ensure_view_state(self, show_mode: str) -> ViewState:
        """Гарантирует правильный ViewState для режима."""
        st = self.ctx.view_state

        if not st or st.show_mode != show_mode:
            st = ViewState(show_mode=show_mode, am_offset=0, am_page_size=12)
        else:
            st = ViewState(
                show_mode=show_mode,
                am_offset=st.am_offset,
                am_page_size=st.am_page_size,
            )

        self.state.set_view_state(st)
        return st

    def _load_from_cache(self, key: str, ttl: int) -> list | None:
        """Загружает данные из кэша."""
        self.log.debug(f"Loading from cache: key={key}, ttl={ttl}")
        status, cached = self.cache.load(key, ttl)
        self.log.debug(f"Cache status={status}, cached={bool(cached)}")

        if status is AniMediaCacheStatus.VALID and cached:
            return cached
        self.log.info(f"No valid cache for key={key}")
        return None

    def _display_animedia_screen(
            self,
            data_json: list,
            show_mode: str,
            cache_key: str,
            poster_size: str,
            description: str,
    ) -> None:
        """Общая логика отображения AniMedia экрана."""
        st = self.ctx.view_state or ViewState(show_mode=show_mode)

        # Срез данных для текущей страницы
        visible_data = self._slice_animedia_titles(
            data_json, st.am_offset, st.am_page_size
        )

        # Прогреваем маппинг и очередь постеров
        self._warmup_titles_and_posters(cache_key, data_json, poster_size)

        # Настраиваем пагинацию
        total_count = self._count_animedia_items(data_json)
        self.ctx.am_total_count = total_count
        self.ctx.current_offset = st.am_offset
        self.display.setup_pagination_ui(total_count, st.am_page_size, description)

        # Отображаем
        self.display.display_titles_in_ui(visible_data, show_mode=show_mode)

    def _warmup_titles_and_posters(
            self,
            key: str,
            data_json: list[dict],
            poster_size: str,
    ) -> None:
        """
        Прогревает маппинг тайтлов и очередь постеров.
        Гарантирует, что для каждого original_id есть запись в TitleProviderMap.
        """
        try:
            for block in data_json or []:
                for line in (block.get("titles") or []):
                    title, time_part, ep_part, rating, poster_url, original_id = \
                        parse_schedule_line(key, line)

                    if not original_id:
                        continue

                    data = {
                        "provider": PROVIDER_ANIMEDIA,
                        "original_id": original_id,
                        "title": title,
                        "poster_url": poster_url,
                        "poster_slot": poster_size,
                        "rating": rating,
                    }
                    self.db.process_animedia_titles(data)

        except Exception as e:
            self.log.error(f"Animedia warmup failed: {e}")

    # === Private: Async Workers ===

    def _start_async_worker(
            self,
            method: Callable,
            callback: Callable,
            loader_message: str,
            **kwargs,
    ) -> None:
        """Запускает асинхронный воркер."""
        from providers.animedia.v0.qt_async_worker import AsyncWorker

        self.ui.show_loader(loader_message)
        self.ui.set_buttons_enabled(False)

        self._worker = AsyncWorker(method, **kwargs)
        self._worker.finished.connect(callback)
        self._worker.error.connect(self._on_animedia_error)
        self._worker.start()

    def _on_animedia_new_titles(self, data: list) -> None:
        """Callback для результатов загрузки расписания."""
        try:
            if not data:
                self.display.show_error_notification("AniMedia", "No data received.")
                self.ui.hide_loader()
                self.ui.set_buttons_enabled(True)
                return

            self.display_animedia_schedule_screen(data)

        except Exception as e:
            self.log.error(f"Error in _on_animedia_new_titles: {e}")
            self.display.show_error_notification("AniMedia", "Failed to show schedule.")
        finally:
            self.ui.hide_loader()
            self.ui.set_buttons_enabled(True)

    def _on_animedia_all_titles(self, data: list) -> None:
        """Callback для результатов загрузки каталога."""
        try:
            if not data:
                self.display.show_error_notification("AniMedia", "No data received.")
                self.ui.hide_loader()
                self.ui.set_buttons_enabled(True)

                return

            self.display_animedia_titles_screen(data)

        except Exception as e:
            self.log.error(f"Error in _on_animedia_all_titles: {e}")
            self.display.show_error_notification("AniMedia", "Failed to show catalog.")
        finally:
            self.ui.hide_loader()
            self.ui.set_buttons_enabled(True)

    def _on_more_titles_loaded(self, data: list) -> None:
        """Callback для результатов загрузки "more" каталога."""
        try:
            if not data:
                self.display.show_error_notification("AniMedia more", "No data received.")
                self.ui.hide_loader()
                self.ui.set_buttons_enabled(True)
                return

            self.display_animedia_titles_screen(data)

        except Exception as e:
            self.log.error(f"Error in _on_all_titles_loaded: {e}")
            self.display.show_error_notification("AniMedia more", "Failed to show more catalog.")
        finally:
            self.ui.hide_loader()
            self.ui.set_buttons_enabled(True)


    def _on_animedia_error(self, message: str) -> None:
        """Callback для ошибок воркера."""
        self.log.error(f"AniMedia worker error: {message}")
        self.ui.hide_loader()
        self.ui.set_buttons_enabled(True)
        self.display.show_error_notification("AniMedia error", message)

    # === Private: Data Processing ===

    @staticmethod
    def _count_animedia_items(data_json: list[dict]) -> int:
        """Подсчитывает общее количество элементов."""
        total = 0
        for block in data_json or []:
            total += len(block.get("titles") or [])
        return total

    @staticmethod
    def _slice_animedia_titles(
            data_json: list[dict],
            offset: int,
            limit: int,
    ) -> list[dict]:
        """
        Срезает данные по глобальному offset/limit.
        Возвращает структуру [{page: int, titles: [str, ...]}, ...].
        """
        if not data_json or limit <= 0:
            return []

        out: list[dict] = []
        remain_skip = offset
        remain_take = limit

        for block in data_json:
            titles = block.get("titles") or []
            if not titles:
                continue

            if remain_skip >= len(titles):
                remain_skip -= len(titles)
                continue

            start = remain_skip
            chunk = titles[start:start + remain_take]
            remain_take -= len(chunk)
            remain_skip = 0

            out.append({"page": block.get("page"), "titles": chunk})

            if remain_take <= 0:
                break

        return out