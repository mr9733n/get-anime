from app.qt.app_state import ViewState

from providers.animedia.v0.cache_manager import AniMediaCacheStatus
from providers.animedia.v0.qt_async_worker import AsyncWorker
from utils.parsing.animedia import parse_schedule_line
from app.qt.app_constants import (
    PROVIDER_ANILIBERTY, PROVIDER_ANIMEDIA,
    SHOW_DEFAULT, SHOW_SYSTEM, SHOW_ONE_TITLE,
    SHOW_AM_SCHEDULE, SHOW_AM_TITLES,
    SCHEDULE_KEY, ALL_TITLES_KEY,
)


def _warmup_animedia_titles_and_posters(self, key: str, data_json: list[dict]) -> None:
    """
    1) гарантирует, что для каждого original_id есть TitleProviderMap (animedia, external_id -> title_id)
    2) ставит постеры в очередь на скачивание через PosterManager (ему нужен title_id)
    """
    for block in data_json or []:
        for line in (block.get("titles") or []):
            title, time_part, ep_part, rating, poster_url, original_id = parse_schedule_line(key, line)

            if not original_id:
                self.logger.debug(f"SKIP line (no original_id): key={key}, line={line}")
                continue

            data = {
                "provider": PROVIDER_ANIMEDIA,
                "original_id": original_id,
                "title": title,
                "poster_url": poster_url,
                "poster_slot": "small" if key == SCHEDULE_KEY else "medium",
                "rating": rating,
            }
            self.db_manager.process_animedia_titles(data)

def display_animedia_titles_screen(self, titles_json=None):
    st = self.view_state
    if not st or st.show_mode != SHOW_AM_TITLES:
        st = ViewState(show_mode=SHOW_AM_TITLES, am_offset=0, am_page_size=12)
        self.set_view_state(st)
    else:
        # не перезатираем, просто гарантируем show_mode
        self.set_view_state(ViewState(
            show_mode=SHOW_AM_TITLES,
            am_offset=st.am_offset,
            am_page_size=st.am_page_size,
        ))
        st = self.view_state

    if not titles_json:
        status, cached = self.animedia_cache.load(
            self.animedia_cache.cfg.all_titles_key,
            self.animedia_cache.cfg.all_titles_ttl
        )
        if status is AniMediaCacheStatus.VALID and cached:
            titles_json = cached
        else:
            self.logger.info("No valid schedule cache to restore")
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
        self.logger.error(f"Animedia warmup failed: {e}")

    total_count = self._count_animedia_items(titles_json)
    self._am_total_count = total_count
    self.current_offset = st.am_offset  # чтобы _setup_pagination_ui показывал правильную страницу
    self._setup_pagination_ui(total_count, st.am_page_size, description="AniMedia — all titles")

    self.display_titles_in_ui(visible_schedule, show_mode=SHOW_AM_TITLES)

def display_animedia_schedule_screen(self, schedule_json=None):
    st = self.view_state
    if not st or st.show_mode != SHOW_AM_SCHEDULE:
        st = ViewState(show_mode=SHOW_AM_SCHEDULE, am_offset=0, am_page_size=12)
        self.set_view_state(st)
    else:
        # не перезатираем, просто гарантируем show_mode
        self.set_view_state(ViewState(
            show_mode=SHOW_AM_SCHEDULE,
            am_offset=st.am_offset,
            am_page_size=st.am_page_size,
        ))
        st = self.view_state

    if not schedule_json:
        status, cached = self.animedia_cache.load(
            self.animedia_cache.cfg.schedule_key,
            self.animedia_cache.cfg.schedule_ttl
        )
        if status is AniMediaCacheStatus.VALID and cached:
            schedule_json = cached
        else:
            self.logger.info("No valid schedule cache to restore")
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
        self.logger.error(f"Animedia warmup failed: {e}")

    total_count = self._count_animedia_items(schedule_json)
    self._am_total_count = total_count
    self.current_offset = st.am_offset  # чтобы _setup_pagination_ui показывал правильную страницу
    self._setup_pagination_ui(total_count, st.am_page_size, description="AniMedia — расписание")

    self.display_titles_in_ui(visible_schedule, show_mode=SHOW_AM_SCHEDULE)

def _count_animedia_items(data_json: list[dict]) -> int:
    total = 0
    for block in data_json or []:
        total += len(block.get("titles") or [])
    return total

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
    self.ui_manager.show_loader("Loading AniMedia schedule...")
    self.ui_manager.set_buttons_enabled(False)

    self._animedia_worker = AsyncWorker(
        self.animedia_adapter.get_all_titles,
        max_titles=60,
        pages=5,
    )
    self._animedia_worker.finished.connect(self._on_animedia_all_titles)
    self._animedia_worker.error.connect(self._on_animedia_error)
    self._animedia_worker.start()

def get_animedia_new_titles(self):
    self.ui_manager.show_loader("Loading AniMedia schedule...")
    self.ui_manager.set_buttons_enabled(False)

    self._animedia_worker = AsyncWorker(
        self.animedia_adapter.get_new_titles,
        max_titles=60,
    )
    self._animedia_worker.finished.connect(self._on_animedia_new_titles)
    self._animedia_worker.error.connect(self._on_animedia_error)
    self._animedia_worker.start()

def _on_animedia_all_titles(self, data):
    try:
        if not data:
            self.show_error_notification("AniMedia", "No data received.")
            return

        self.display_animedia_titles_screen(data)

    except Exception as e:
        self.logger.error(f"Error in _on_animedia_all_titles: {e}")
        self.show_error_notification("AniMedia", "Failed to show schedule. Check logs.")
    finally:
        self.ui_manager.hide_loader()
        self.ui_manager.set_buttons_enabled(True)

def _on_animedia_new_titles(self, data):
    try:
        if not data:
            self.show_error_notification("AniMedia", "No data received.")
            return

        self.display_animedia_schedule_screen(data)

    except Exception as e:
        self.logger.error(f"Error in _on_animedia_new_titles: {e}")
        self.show_error_notification("AniMedia", "Failed to show schedule. Check logs.")
    finally:
        self.ui_manager.hide_loader()
        self.ui_manager.set_buttons_enabled(True)

def _on_animedia_error(self, message: str):
    try:
        self.logger.error(f"AniMedia worker error: {message}")
        self.ui_manager.hide_loader()
        self.ui_manager.set_buttons_enabled(True)
        self.show_error_notification("AniMedia error", message)

    except Exception as msg:
        self.logger.error(f"Unexpected error in _on_animedia_error: {msg}")
        self.show_error_notification("Error", f"Unexpected error. Check logs for details {msg}")
    finally:
        self.ui_manager.hide_loader()
        self.ui_manager.set_buttons_enabled(True)

def _on_animedia_result(self, data: list) -> list[int] | None:
    """
    `data` – список словарей, который вернул `get_by_title`.
    Здесь можно сохранить в БД, отобразить в UI и т.п.
    """
    try:
        if not data:
            self.show_error_notification("AniMedia", "No titles found on Animedia.")
            return

        self.logger.info(f"Animedia returned {len(data)} items")

        if isinstance(data, dict) and 'error' in data:
            self.logger.error(data['error'])
            self.show_error_notification("AniMedia scraper Error", data['error'])
            return None

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

        if not title_ids:
            self.logger.error("No title_ids returned after saving Animedia titles")
            self.show_error_notification("AniMedia", "Failed to save titles to database.")
            return

        search_text = getattr(self, "_last_search_text", "")
        self._handle_found_titles(title_ids, search_text)

    except Exception as e:
        self.logger.error(f"Error while fetching title AM: {e}")
        self.show_error_notification("Error", "Unexpected error. Check logs for details.")
    finally:
        self.ui_manager.hide_loader()
        self.ui_manager.set_buttons_enabled(True)
