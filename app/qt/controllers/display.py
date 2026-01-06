# app/qt/controllers/display.py
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable

from PyQt6.QtWidgets import QVBoxLayout, QLabel, QSystemTrayIcon

from core.queries.title_enricher import enrich_titles_for_render
from app.qt.app_state import ViewState
from app.qt.app_helpers import TitleDisplayFactory, TitleDataFactory
from app.qt.app_constants import (
    SHOW_DEFAULT, SHOW_SYSTEM, SHOW_ONE_TITLE,
    SHOW_AM_SCHEDULE, SHOW_AM_TITLES, DEFAULT_TEMPLATE,
    APP_WIDTH, APP_HEIGHT, APP_X_POS, APP_Y_POS,
)
from app.qt.protocols import (
    IUIManager,
    IUIGenerator,
    IUISystemGenerator,
    IUIAnimediaGenerator,
    IPosterController,
    IStateController,
    IAniLibertyController,
    IDBManager,
)
from app.qt.ui_notify import Notifier

if TYPE_CHECKING:
    from logging import Logger
    from app.qt.app_context import AppContext
    from PyQt6.QtWidgets import QWidget


@dataclass
class DisplayControllerDeps:
    """Явные зависимости DisplayController"""
    logger: Logger
    db: IDBManager
    ui: IUIManager
    context: AppContext

    # UI генераторы
    ui_generator: IUIGenerator
    ui_am_generator: IUIAnimediaGenerator
    ui_s_generator: IUISystemGenerator

    # Ссылки на родительский виджет (для создания child widgets)
    parent_widget: QWidget

    # Callbacks для межконтроллерного взаимодействия
    # (устанавливаются после создания всех контроллеров)
    get_poster_controller: Callable[[], IPosterController] | None = None
    get_state_controller: Callable[[], IStateController] | None = None
    get_aniliberty_controller: Callable[[], IAniLibertyController] | None = None


class DisplayController:
    """
    Контроллер отображения контента.
    Центральный контроллер для UI — другие контроллеры зависят от него.
    """

    def __init__(self, deps: DisplayControllerDeps):
        self._deps = deps

        # Кэшированные ссылки (lazy init через callbacks)
        self._poster: IPosterController | None = None
        self._state: IStateController | None = None
        self._aniliberty: IAniLibertyController | None = None

        # Transient UI elements
        self._error_label: QLabel | None = None
        self._tray_icon: QSystemTrayIcon | None = None

        self._notifier = Notifier(self.parent)

    # === Lazy-loaded dependencies ===

    @property
    def poster(self) -> IPosterController:
        """Ленивая загрузка PosterController (избегаем циклических зависимостей)"""
        if self._poster is None:
            if self._deps.get_poster_controller:
                self._poster = self._deps.get_poster_controller()
            else:
                raise RuntimeError("PosterController not configured")
        return self._poster

    @property
    def state(self) -> IStateController:
        """Ленивая загрузка StateController"""
        if self._state is None:
            if self._deps.get_state_controller:
                self._state = self._deps.get_state_controller()
            else:
                raise RuntimeError("StateController not configured")
        return self._state

    @property
    def aniliberty(self) -> IAniLibertyController:
        """Ленивая загрузка AniLibertyController"""
        if self._aniliberty is None:
            if self._deps.get_aniliberty_controller:
                self._aniliberty = self._deps.get_aniliberty_controller()
            else:
                raise RuntimeError("AniLibertyController not configured")
        return self._aniliberty

    # === Simple properties ===

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
    def parent(self) -> QWidget:
        return self._deps.parent_widget

    # === Public API: Initialization ===

    def init_ui(self, all_layout_metadata: list, callbacks: dict) -> None:
        """Инициализирует главный UI."""
        self.parent.setWindowTitle(f'Anime Player App {self.ctx.app_version}')
        self.parent.setGeometry(APP_X_POS, APP_Y_POS, APP_WIDTH, APP_HEIGHT)
        self.parent.setMinimumSize(APP_WIDTH, APP_HEIGHT)

        self._apply_template_style()

        main_layout = QVBoxLayout()
        self.ui.setup_main_layout(main_layout, all_layout_metadata, callbacks)
        self.parent.setLayout(main_layout)

        # Сохраняем ссылки на виджеты в контексте
        self.ctx.title_search_entry = self.ui.parent_widgets.get("title_input")
        self.ctx.quality_dropdown = self.ui.parent_widgets.get("quality_dropdown")

    def _apply_template_style(self) -> None:
        """Применяет стиль в зависимости от шаблона."""
        styles = {
            DEFAULT_TEMPLATE: "background-color: rgba(240, 240, 240, 1.0);",
            "no_background_night": "background-color: rgba(140, 140, 140, 1.0);",
            "no_background": "background-color: rgba(220, 220, 220, 1.0);",
        }
        style = styles.get(self.ctx.current_template, styles[DEFAULT_TEMPLATE])
        self.parent.setStyleSheet(f"QWidget {{ {style} }}")

    # === Public API: Error Notifications ===

    def show_error_notification(self, title: str, message: str) -> None:
        self._notifier.error(title, message)

    # === Public API: Display Methods ===

    def display_info(self, title_id: int) -> None:
        """Отображает информацию о конкретном тайтле."""
        try:
            self.ui.show_loader("Loading title...")
            self.ui.set_buttons_enabled(False)

            self.poster.clear_previous_posters()
            titles = self.db.get_titles_from_db(title_id=title_id)

            if not titles or titles[0] is None:
                self.log.error(f"Title with title_id {title_id} not found in the database.")
                return

            self.ctx.total_titles = titles
            self.state.set_view_state(ViewState(show_mode=SHOW_DEFAULT, title_id=title_id))

            self._hide_pagination()
            self.display_titles_in_ui(titles)

        except Exception as e:
            self.log.error(f"Error display_info: {e}")
        finally:
            self.ui.hide_loader()
            self.ui.set_buttons_enabled(True)

    def display_titles(
            self,
            title_ids: list[int] | None = None,
            batch_size: int | None = None,
            show_mode: str = "default",
            show_previous: bool = False,
            show_next: bool = False,
            start: bool = False,
    ) -> None:
        """Отображает список тайтлов с пагинацией."""
        try:
            self.ui.show_loader("Loading titles...")
            self.ui.set_buttons_enabled(False)

            # Нормализуем title_ids
            title_ids = self._normalize_title_ids(title_ids)

            if start:
                self.log.debug(
                    f"START: offset={self.ctx.current_offset}, batch={self.ctx.titles_batch_size}"
                )

            # Обрабатываем навигацию
            if show_next or show_previous:
                self._handle_navigation(show_next)

            # Получаем данные
            data_factory = TitleDataFactory(self.db, self.ctx.user_id)
            titles = data_factory.get_titles(
                show_mode=show_mode,
                title_ids=title_ids,
                current_offset=self.ctx.current_offset,
                batch_size=batch_size,
            )
            # Обновляем состояние
            self._update_view_state(titles, title_ids, show_mode)

            # Проверяем наличие данных
            description = data_factory.get_metadata_description(show_mode=show_mode)
            if not titles and description:
                self.log.info("Нет данных для отображения, сбрасываем offset.")
                self.ctx.current_offset = 0
                self.ctx.total_titles = []
                return

            # Настраиваем пагинацию
            self._setup_pagination_for_mode(title_ids, batch_size, show_mode, description)

            # Отображаем
            self.display_titles_in_ui(titles, show_mode)
            self.log.debug(f"Displayed {show_mode} with {len(titles)} titles.")

        except Exception as e:
            self.log.error(f"Ошибка display_titles: {e}")
        finally:
            self.ui.hide_loader()
            self.ui.set_buttons_enabled(True)

    def display_titles_in_ui(
            self,
            titles: list,
            show_mode: str = "default",
            row_start: int = 0,
            col_start: int = 0,
    ) -> None:
        """Отображает тайтлы в UI grid."""
        if self.ctx.posters_layout is None:
            self.log.error("posters_layout is None: UI not initialized.")
            return

        try:
            special_modes = {SHOW_SYSTEM, SHOW_AM_SCHEDULE, SHOW_AM_TITLES}
            self.poster.clear_previous_posters()
            if show_mode not in special_modes:
                titles = enrich_titles_for_render(self.db, self.ctx.user_id, titles)

            # cache template for this render pass (avoid UI->DB calls)
            special_modes = {SHOW_SYSTEM, SHOW_AM_SCHEDULE, SHOW_AM_TITLES}
            list_modes = {'titles_list', 'franchise_list', 'need_to_see_list', 'ongoing_list'}

            kind = "titles"
            if show_mode == SHOW_ONE_TITLE:
                kind = "one_title"
            elif show_mode in list_modes:
                kind = "text_list"

            self.ctx._template_cache = self.db.get_template(self.ctx.current_template, kind=kind)

            factory = TitleDisplayFactory(self.parent)

            if show_mode in special_modes:
                widget, _ = factory.create(show_mode, titles)
                self.ctx.posters_layout.addWidget(widget, 0, 0, 1, 2)
            elif len(titles) == 1:
                widget, _ = factory.create(SHOW_ONE_TITLE, titles[0])
                self.ctx.posters_layout.addWidget(widget, 0, 0, 1, 2)
            else:
                for index, title in enumerate(titles):
                    title_widget, num_columns = factory.create(show_mode, title)
                    row = (index + row_start) // num_columns
                    column = (index + col_start) % num_columns
                    self.ctx.posters_layout.addWidget(title_widget, row, column)

            self.log.debug(f"Displayed {show_mode} with {len(titles)} titles.")

            # Emit signal через parent
            if hasattr(self.parent, 'state_changed'):
                self.parent.state_changed.emit()

        except Exception as e:
            self.log.error(f"Ошибка display_titles_in_ui: {e}")

    def display_titles_for_day(self, day_of_week: int, force_reload: bool = False) -> None:
        """Отображает тайтлы для указанного дня недели."""
        try:
            self.ui.show_loader("Loading schedule...")
            self.ui.set_buttons_enabled(False)

            self.poster.clear_previous_posters()
            self.state.set_view_state(ViewState(show_mode=SHOW_DEFAULT, day_of_week=day_of_week))
            self._hide_pagination()

            titles = None
            if not force_reload:
                titles = self.db.get_titles_from_db(show_all=False, day_of_week=day_of_week)
                self.log.debug(f"day_of_week: {day_of_week}, titles from DB: {len(titles)}")

            if titles:
                self.ctx.total_titles = {title.title_id for title in titles}
                self.display_titles_in_ui(titles)
            else:
                self._fetch_and_display_schedule(day_of_week)

        except Exception as e:
            self.log.error(f"Error displaying titles for day: {e}")
        finally:
            self.ui.hide_loader()
            self.ui.set_buttons_enabled(True)

    def refresh_display(self) -> None:
        """Обновляет текущее отображение."""
        try:
            quality = self.ctx.quality_dropdown.currentText() if self.ctx.quality_dropdown else "hd"
            self.poster.clear_previous_posters()

            state = self.ctx.view_state
            if not state:
                self.display_titles(start=True)
                return

            if state.show_mode == SHOW_AM_SCHEDULE:
                # Вызываем через callback, чтобы избежать циклической зависимости
                if hasattr(self.parent, 'display_animedia_schedule_screen'):
                    self.parent.display_animedia_schedule_screen()
                return
            elif state.show_mode == SHOW_AM_TITLES:
                if hasattr(self.parent, 'display_animedia_titles_screen'):
                    self.parent.display_animedia_titles_screen()
                return
            elif state.show_mode == SHOW_SYSTEM:
                self.display_titles(show_mode=SHOW_SYSTEM)
                return

            titles = self._get_titles_for_state(state)
            updated = [self._update_title_links(t, quality) for t in titles]
            self.display_titles_in_ui(updated)

        except Exception as e:
            self.log.error(f"Ошибка REFRESH: {e}")

    # === Public API: Navigation ===

    def navigate_pagination(self, go_forward: bool = True) -> None:
        """Навигация по страницам текущих результатов."""
        try:
            self.ui.show_loader("Loading titles...")
            self.ui.set_buttons_enabled(False)

            show_mode = self.ctx.current_show_mode or "default"
            batch_size = 12

            if show_mode in (SHOW_AM_SCHEDULE, SHOW_AM_TITLES):
                if self.state.navigate_animedia_mode(show_mode, go_forward=go_forward):
                    return

            if self.ctx.current_title_ids and len(self.ctx.current_title_ids) > batch_size:
                total_count = len(self.ctx.current_title_ids)
                self.ctx.current_offset = self._calc_new_offset(total_count, batch_size, go_forward)
                self.display_titles(
                    title_ids=self.ctx.current_title_ids,
                    batch_size=batch_size,
                    show_mode=show_mode,
                )
            else:
                total_count = self.db.get_total_titles_count(show_mode=show_mode)
                self.ctx.current_offset = self._calc_new_offset(total_count, batch_size, go_forward)
                self.display_titles(batch_size=batch_size, show_mode=show_mode)

        except Exception as e:
            self.log.error(f"Ошибка при навигации: {e}")
        finally:
            self.ui.hide_loader()
            self.ui.set_buttons_enabled(True)

    def setup_pagination_ui(
            self,
            count_titles: int,
            batch_size: int,
            description: str | None = None,
    ) -> None:
        """Настраивает отображение пагинации в UI."""
        total_pages = (count_titles + batch_size - 1) // batch_size
        current_page = (self.ctx.current_offset // batch_size) + 1

        self.ui.update_pagination_info(current_page, total_pages, count_titles, description or "")

        pagination_widget = self.ui.parent_widgets.get("pagination_widget")
        if pagination_widget:
            pagination_widget.setVisible(total_pages > 1)

    def reset_offset(self) -> None:
        """Сбрасывает offset пагинации."""
        self.ctx.current_offset = 0

    # === Public API: Layout Helpers ===

    def clear_layout(self, layout) -> None:
        """Рекурсивно очищает все элементы из layout."""
        if layout is not None:
            while layout.count():
                item = layout.takeAt(0)
                widget_to_remove = item.widget()
                if widget_to_remove is not None:
                    widget_to_remove.deleteLater()
                elif item.layout() is not None:
                    self.clear_layout(item.layout())

    # === Public API: Browser Creation (делегирование в генераторы) ===

    def create_title_browser(self, title, show_mode: str = SHOW_DEFAULT):
        """Создаёт браузер для тайтла."""
        return self._deps.ui_generator.create_title_browser(title, show_mode=show_mode)

    def create_system_browser(self, statistics: dict):
        """Создаёт system browser."""
        template = self.ctx.current_template
        return self._deps.ui_s_generator.create_system_browser(statistics, template)

    def create_animedia_schedule_browser(self, schedule: list):
        """Создаёт AniMedia schedule browser."""
        return self._deps.ui_am_generator.create_animedia_schedule_browser(schedule)

    def create_animedia_titles_browser(self, titles: list):
        """Создаёт AniMedia titles browser."""
        return self._deps.ui_am_generator.create_animedia_titles_browser(titles)

    # === Private Methods ===

    def _normalize_title_ids(self, title_ids) -> list[int] | None:
        """Приводит title_ids к списку."""
        if title_ids is None:
            return None
        if isinstance(title_ids, list):
            return title_ids
        try:
            return list(title_ids)
        except TypeError:
            return title_ids

    def _handle_navigation(self, show_next: bool) -> None:
        """Обрабатывает навигацию вперёд/назад."""
        if show_next:
            statistics = self.db.get_statistics_from_db()
            total_available = statistics.get('titles_count', 0)
            self.ctx.current_offset = self._calc_new_offset(
                total_available,
                self.ctx.titles_batch_size,
                go_forward=True,
            )
        else:
            self.ctx.current_offset = max(0, self.ctx.current_offset - self.ctx.titles_batch_size)

    def _update_view_state(
            self,
            titles: list,
            title_ids: list[int] | None,
            show_mode: str,
    ) -> None:
        """Обновляет ViewState после получения данных."""
        page_ids = [t.title_id for t in titles if getattr(t, "title_id", None) is not None]

        if title_ids is not None:
            self.ctx.current_title_ids = list(title_ids)
            self.state.set_view_state(ViewState(show_mode=show_mode, title_ids=self.ctx.current_title_ids))
        else:
            self.ctx.current_title_ids = None
            self.state.set_view_state(ViewState(show_mode=show_mode, title_ids=page_ids))

    def _setup_pagination_for_mode(
            self,
            title_ids: list[int] | None,
            batch_size: int | None,
            show_mode: str,
            description: str | None,
    ) -> None:
        """Настраивает пагинацию в зависимости от режима."""
        list_modes = {'titles_list', 'franchise_list', 'need_to_see_list', 'ongoing_list'}

        if title_ids and len(title_ids) > 0:
            if self.ctx.current_offset >= len(title_ids):
                self.ctx.current_offset = 0

            if batch_size:
                self.setup_pagination_ui(len(title_ids), batch_size, description)
            else:
                self._hide_pagination()
        elif show_mode in list_modes:
            count_titles = self.db.get_total_titles_count(show_mode=show_mode)
            self.setup_pagination_ui(count_titles, batch_size or self.ctx.titles_batch_size, description)
        else:
            self._hide_pagination()

    def _hide_pagination(self) -> None:
        """Скрывает виджет пагинации."""
        pagination_widget = self.ui.parent_widgets.get("pagination_widget")
        if pagination_widget:
            pagination_widget.setVisible(False)

    def _calc_new_offset(self, total_count: int, batch_size: int, go_forward: bool) -> int:
        """Вычисляет новый offset для пагинации."""
        if go_forward:
            if self.ctx.current_offset + batch_size >= total_count:
                return 0
            return self.ctx.current_offset + batch_size
        return max(0, self.ctx.current_offset - batch_size)

    def _get_titles_for_state(self, state: ViewState) -> list:
        """Получает тайтлы для текущего состояния."""
        if state.title_id is not None:
            return self.db.get_titles_from_db(title_id=state.title_id)
        elif state.title_ids:
            return self.db.get_titles_from_db(title_ids=state.title_ids)
        elif state.day_of_week is not None:
            return self.db.get_titles_from_db(day_of_week=state.day_of_week)
        return self.ctx.current_titles or []

    def _update_title_links(self, title, selected_quality: str):
        """Обновляет ссылки на эпизоды для заданного качества."""
        quality_map = {
            'fhd': lambda ep: ep.hls_fhd,
            'hd': lambda ep: ep.hls_hd,
            'sd': lambda ep: ep.hls_sd,
        }

        getter = quality_map.get(selected_quality)
        if getter:
            title.current_links = [getter(ep) for ep in title.episodes if getter(ep)]
        else:
            self.log.warning(f"Неизвестное качество: {selected_quality}")

        return title

    def _fetch_and_display_schedule(self, day_of_week: int) -> None:
        """Загружает расписание и отображает."""
        status, new_title_ids = self.aniliberty.fetch_and_process_schedule(day_of_week)
        if status and new_title_ids:
            titles = self.db.get_titles_from_db(day_of_week=day_of_week)
            self.ctx.total_titles = {title.title_id for title in titles}
            self.display_titles_in_ui(titles)
        else:
            self.display_titles(start=True)