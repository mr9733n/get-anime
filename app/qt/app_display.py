# app/qt/app_display.py
from __future__ import annotations

from PyQt5.QtWidgets import QVBoxLayout, QLabel, QSystemTrayIcon, QStyle
from PyQt5.QtCore import QTimer, Qt

from app.qt.app_state import ViewState
from app.qt.app_helpers import TitleDisplayFactory, TitleDataFactory
from app.qt.app_constants import (
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


def init_ui(self, all_layout_metadata):
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

def navigate_pagination(self, go_forward=True):
    """
    Навигация по страницам текущих результатов (любых списков тайтлов)
    """
    try:
        show_mode = getattr(self, 'current_show_mode', 'default')
        batch_size = 12  # TODO: default size = 12

        if show_mode in (SHOW_AM_SCHEDULE, SHOW_AM_TITLES):
            if self._navigate_animedia_mode(self.current_show_mode, go_forward=go_forward):
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

def reset_offset(self):
    self.current_offset = 0