# app/qt/controllers/animedia.py
from __future__ import annotations

from typing import Any, Optional, Iterable

from app.qt.app_state import ViewState
from providers.animedia.v0.cache_manager import AniMediaCacheStatus
from providers.animedia.v0.qt_async_worker import AsyncWorker
from utils.parsing.animedia import parse_schedule_line
from app.qt.app_constants import (
    PROVIDER_ANIMEDIA,
    SHOW_AM_SCHEDULE, SHOW_AM_TITLES,
    SCHEDULE_KEY, ALL_TITLES_KEY,
)

class AniMediaController:
    """
    Переходный контроллер (stage-2/3):
    - svc: доступ к db/api/ui/logger/config/playlist
    - app: доступ к orchestration-методам (display_titles, show_error_notification, invoke_database_save, ...)
    """

    def __init__(self, app: Any, svc: Any):
        self.app = app
        self.svc = svc

    @property
    def db(self):
        return self.svc.db

    @property
    def ui(self):
        return self.svc.ui

    @property
    def log(self):
        return self.svc.logger

    @property
    def api(self):
        return self.svc.api

    def _warmup_animedia_titles_and_posters(self, key: str, data_json: list[dict]) -> None:
        """
        1) гарантирует, что для каждого original_id есть TitleProviderMap (animedia, external_id -> title_id)
        2) ставит постеры в очередь на скачивание через PosterManager (ему нужен title_id)
        """
        for block in data_json or []:
            for line in (block.get("titles") or []):
                title, time_part, ep_part, rating, poster_url, original_id = parse_schedule_line(key, line)

                if not original_id:
                    self.log.debug(f"SKIP line (no original_id): key={key}, line={line}")
                    continue

                data = {
                    "provider": PROVIDER_ANIMEDIA,
                    "original_id": original_id,
                    "title": title,
                    "poster_url": poster_url,
                    "poster_slot": "small" if key == SCHEDULE_KEY else "medium",
                    "rating": rating,
                }
                self.db.process_animedia_titles(data)

    def display_animedia_titles_screen(self, titles_json=None):
        st = self.app.view_state
        if not st or st.show_mode != SHOW_AM_TITLES:
            st = ViewState(show_mode=SHOW_AM_TITLES, am_offset=0, am_page_size=12)
            self.app.set_view_state(st)
        else:
            # не перезатираем, просто гарантируем show_mode
            self.app.set_view_state(ViewState(
                show_mode=SHOW_AM_TITLES,
                am_offset=st.am_offset,
                am_page_size=st.am_page_size,
            ))
            st = self.app.view_state

        if not titles_json:
            status, cached = self.app.animedia_cache.load(
                self.app.animedia_cache.cfg.all_titles_key,
                self.app.animedia_cache.cfg.all_titles_ttl
            )
            if status is AniMediaCacheStatus.VALID and cached:
                titles_json = cached
            else:
                self.log.info("No valid schedule cache to restore")
                titles_json = []
                self.get_animedia_all_titles()

        visible_schedule = self._slice_animedia_titles(titles_json, st.am_offset, st.am_page_size)
        # ВАЖНО: прогреваем маппинг и очередь постеров до отрисовки
        try:
            self._warmup_animedia_titles_and_posters(
                key=ALL_TITLES_KEY,
                data_json=titles_json
            )

        except Exception as e:
            self.log.error(f"Animedia warmup failed: {e}")

        total_count = self._count_animedia_items(titles_json)
        self.app.am_total_count = total_count
        self.app.current_offset = st.am_offset  # чтобы _setup_pagination_ui показывал правильную страницу
        self.app.setup_pagination_ui(total_count, st.am_page_size, description="AniMedia — all titles")

        self.app.display_titles_in_ui(visible_schedule, show_mode=SHOW_AM_TITLES)

    def display_animedia_schedule_screen(self, schedule_json=None):
        st = self.app.view_state
        if not st or st.show_mode != SHOW_AM_SCHEDULE:
            st = ViewState(show_mode=SHOW_AM_SCHEDULE, am_offset=0, am_page_size=12)
            self.app.set_view_state(st)
        else:
            # не перезатираем, просто гарантируем show_mode
            self.app.set_view_state(ViewState(
                show_mode=SHOW_AM_SCHEDULE,
                am_offset=st.am_offset,
                am_page_size=st.am_page_size,
            ))
            st = self.app.view_state

        if not schedule_json:
            status, cached = self.app.animedia_cache.load(
                self.app.animedia_cache.cfg.schedule_key,
                self.app.animedia_cache.cfg.schedule_ttl
            )
            if status is AniMediaCacheStatus.VALID and cached:
                schedule_json = cached
            else:
                self.log.info("No valid schedule cache to restore")
                schedule_json = []
                self.get_animedia_new_titles()

        visible_schedule = self._slice_animedia_titles(schedule_json, st.am_offset, st.am_page_size)
        # ВАЖНО: прогреваем маппинг и очередь постеров до отрисовки
        try:
            self._warmup_animedia_titles_and_posters(
                key=SCHEDULE_KEY,
                data_json=schedule_json
            )

        except Exception as e:
            self.log.error(f"Animedia warmup failed: {e}")

        total_count = self._count_animedia_items(schedule_json)
        self.app.am_total_count = total_count
        self.app.current_offset = st.am_offset  # чтобы _setup_pagination_ui показывал правильную страницу
        self.app.setup_pagination_ui(total_count, st.am_page_size, description="AniMedia — расписание")

        self.app.display_titles_in_ui(visible_schedule, show_mode=SHOW_AM_SCHEDULE)

    @staticmethod
    def _count_animedia_items(data_json: list[dict]) -> int:
        total = 0
        for block in data_json or []:
            total += len(block.get("titles") or [])
        return total

    @staticmethod
    def _slice_animedia_titles(data_json: list[dict], offset: int, limit: int) -> list[dict]:
        """
        data_json: [{page: int, titles: [str, ...]}, ...]
        Возвращает такой же формат, но titles обрезаны по глобальному offset/limit.
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

    def get_animedia_all_titles(self):
        self.ui.show_loader("Loading AniMedia schedule...")
        self.ui.set_buttons_enabled(False)

        self.app._animedia_worker = AsyncWorker(
            self.app.animedia_adapter.get_all_titles,
            max_titles=60,
            pages=5,
        )
        self.app._animedia_worker.finished.connect(self._on_animedia_all_titles)
        self.app._animedia_worker.error.connect(self.app.actions.on_animedia_error)
        self.app._animedia_worker.start()

    def get_animedia_new_titles(self):
        self.ui.show_loader("Loading AniMedia schedule...")
        self.ui.set_buttons_enabled(False)

        self.app._animedia_worker = AsyncWorker(
            self.app.animedia_adapter.get_new_titles,
            max_titles=60,
        )
        self.app._animedia_worker.finished.connect(self._on_animedia_new_titles)
        self.app._animedia_worker.error.connect(self.app.actions.on_animedia_error)
        self.app._animedia_worker.start()

    def _on_animedia_all_titles(self, data):
        try:
            if not data:
                self.app.show_error_notification("AniMedia", "No data received.")
                return

            self.display_animedia_titles_screen(data)

        except Exception as e:
            self.log.error(f"Error in _on_animedia_all_titles: {e}")
            self.app.show_error_notification("AniMedia", "Failed to show schedule. Check logs.")
        finally:
            self.ui.hide_loader()
            self.ui.set_buttons_enabled(True)

    def _on_animedia_new_titles(self, data):
        try:
            if not data:
                self.app.show_error_notification("AniMedia", "No data received.")
                return

            self.display_animedia_schedule_screen(data)

        except Exception as e:
            self.log.error(f"Error in _on_animedia_new_titles: {e}")
            self.app.show_error_notification("AniMedia", "Failed to show schedule. Check logs.")
        finally:
            self.ui.hide_loader()
            self.ui.set_buttons_enabled(True)


