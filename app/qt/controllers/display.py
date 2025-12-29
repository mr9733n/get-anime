# app/qt/controllers/display.py
from __future__ import annotations

from typing import Any
from PyQt5.QtWidgets import QVBoxLayout, QLabel, QSystemTrayIcon, QStyle
from PyQt5.QtCore import QTimer, Qt

from app.qt.app_state import ViewState
from app.qt.app_helpers import TitleDisplayFactory, TitleDataFactory
from app.qt.app_constants import (
    SHOW_DEFAULT, SHOW_SYSTEM, SHOW_ONE_TITLE,
    SHOW_AM_SCHEDULE, SHOW_AM_TITLES, DEFAULT_TEMPLATE,
    APP_WIDTH, APP_HEIGHT, APP_X_POS, APP_Y_POS,
)


class DisplayController:
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

    def init_ui(self, all_layout_metadata):
        self.app.setWindowTitle(f'Anime Player App {self.app.app_version}')
        self.app.setGeometry(APP_X_POS, APP_Y_POS, APP_WIDTH, APP_HEIGHT)
        self.app.setMinimumSize(APP_WIDTH, APP_HEIGHT)

        if self.app.current_template == DEFAULT_TEMPLATE:
            self.app.setStyleSheet("""
                QWidget {
                    background-color: rgba(240, 240, 240, 1.0);
                }
            """)
        elif self.app.current_template == "no_background_night":
            self.app.setStyleSheet("""
                QWidget {
                    background-color: rgba(140, 140, 140, 1.0);
                }
            """)
        elif self.app.current_template == "no_background":
            self.app.setStyleSheet("""
                QWidget {
                    background-color: rgba(220, 220, 220, 1.0);
                }
            """)
        main_layout = QVBoxLayout()

        self.ui.setup_main_layout(main_layout, all_layout_metadata, self.app.callbacks)
        self.app.setLayout(main_layout)

        self.app.title_search_entry = self.ui.parent_widgets.get("title_input")
        self.app.quality_dropdown = self.ui.parent_widgets.get("quality_dropdown")

    def show_error_notification(self, title, message):
        """Показывает всплывающее уведомление об ошибке."""
        self.error_label = QLabel(message, self.app)
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

        self.tray_icon = QSystemTrayIcon(self.app)
        self.tray_icon.setIcon(self.app.style().standardIcon(QStyle.SP_MessageBoxWarning))

        self.error_label.show()
        self.tray_icon.show()

        QTimer.singleShot(5000, self.error_label.hide)
        QTimer.singleShot(5000, self.tray_icon.hide)
        self.tray_icon.showMessage(title, message, QSystemTrayIcon.Warning, 5000)

    def refresh_display(self):
        try:
            q = self.app.quality_dropdown.currentText()
            self.app.clear_previous_posters()

            state = self.app.view_state
            if state.show_mode == SHOW_AM_SCHEDULE:
                self.app.display_animedia_schedule_screen()
                return
            elif state.show_mode == SHOW_AM_TITLES:
                self.app.display_animedia_titles_screen()
                return
            elif state.show_mode == SHOW_SYSTEM:
                self.display_titles(show_mode=SHOW_SYSTEM)
                return

            if state.title_id is not None:
                titles = self.db.get_titles_from_db(title_id=state.title_id)
            elif state.title_ids:
                titles = self.db.get_titles_from_db(title_ids=state.title_ids)
            elif state.day_of_week is not None:
                titles = self.db.get_titles_from_db(day_of_week=state.day_of_week)
            else:
                titles = self.app.current_titles or []

            updated = [self.update_title_links(t, q) for t in titles]
            self.display_titles_in_ui(updated)

        except Exception as e:
            self.log.error(f"Ошибка REFRESH: {e}")

    def update_title_links(self, title, selected_quality):
        """Обновляет ссылки на эпизоды для заданного качества."""
        if selected_quality == 'fhd':
            title.current_links = [ep.hls_fhd for ep in title.episodes if ep.hls_fhd]
        elif selected_quality == 'hd':
            title.current_links = [ep.hls_hd for ep in title.episodes if ep.hls_hd]
        elif selected_quality == 'sd':
            title.current_links = [ep.hls_sd for ep in title.episodes if ep.hls_sd]
        else:
            self.log.warning(f"Неизвестное качество: {selected_quality}, используем ссылки по умолчанию.")

        # Логирование обновленных ссылок
        self.log.debug(f"Обновлены ссылки для тайтла {title.title_id}: {title.current_links}")
        return title

    def navigate_pagination(self, go_forward=True):
        """
        Навигация по страницам текущих результатов (любых списков тайтлов)
        """
        try:
            show_mode = getattr(self.app, 'current_show_mode', 'default')
            batch_size = 12  # TODO: default size = 12

            if show_mode in (SHOW_AM_SCHEDULE, SHOW_AM_TITLES):
                if self.app.navigate_animedia_mode(self.app.current_show_mode, go_forward=go_forward):
                    return

            if self.app.current_title_ids and len(self.app.current_title_ids) > batch_size:
                total_count = len(self.app.current_title_ids)
                self.app.current_offset = self._update_pagination_offset(total_count, batch_size, go_forward)
                self.log.debug(
                    f"Navigation: offset={self.app.current_offset}, batch_size={batch_size}, total={total_count}")
                self.display_titles(title_ids=self.app.current_title_ids, batch_size=batch_size, show_mode=show_mode)
            else:
                total_count = self.db.get_total_titles_count(show_mode=show_mode)
                self.app.current_offset = self._update_pagination_offset(total_count, batch_size, go_forward)
                self.log.debug(
                    f"Navigation: offset={self.app.current_offset}, batch_size={batch_size}, total={total_count}")
                self.display_titles(batch_size=batch_size, show_mode=show_mode)

        except Exception as e:
            self.log.error(f"Ошибка при навигации по результатам: {e}")

    def display_titles(self, title_ids=None, batch_size=None, show_mode='default', show_previous=False, show_next=False,
                       start=False):
        try:
            self.ui.show_loader("Loading titles...")
            self.ui.set_buttons_enabled(False)

            if not isinstance(title_ids, list):
                try:
                    title_ids = list(title_ids) if title_ids is not None else None
                except TypeError:
                    title_ids = title_ids

            if start:
                self.log.debug(
                    f"START: current_offset: {self.app.current_offset} - titles_batch_size: {self.app.titles_batch_size}")

            if show_next or show_previous:
                statistics = self.db.get_statistics_from_db() if show_next else None
                total_available_titles = statistics.get('titles_count', 0) if show_next else 0

                if show_next:
                    self.app.current_offset = self._update_pagination_offset(
                        total_available_titles,
                        self.app.titles_batch_size,
                        go_forward=True
                    )
                    self.log.debug(
                        f"NEXT: current_offset: {self.app.current_offset} - titles_batch_size: {self.app.titles_batch_size}")
                elif show_previous:
                    self.app.current_offset = max(0, self.app.current_offset - self.app.titles_batch_size)
                    self.log.debug(
                        f"PREV: current_offset: {self.app.current_offset} - titles_batch_size: {self.app.titles_batch_size}")

            data_factory = TitleDataFactory(self.db, self.app.user_id)
            titles = data_factory.get_titles(
                show_mode=show_mode,
                title_ids=title_ids,
                current_offset=self.app.current_offset,
                batch_size=batch_size
            )

            # self.app.current_title_ids = [t.title_id for t in titles if getattr(t, "title_id", None) is not None]
            # self.app.set_view_state(ViewState(show_mode=show_mode, title_ids=self.app.current_title_ids))
            page_ids = [t.title_id for t in titles if getattr(t, "title_id", None) is not None]

            # Если display_titles вызван с title_ids — это "зафиксированная выборка" (например поиск)
            if title_ids is not None:
                self.app.current_title_ids = list(title_ids)
                self.app.set_view_state(ViewState(show_mode=show_mode, title_ids=self.app.current_title_ids))
            else:
                # Для обычных режимов списков пагинация идет через DB count, поэтому выборку НЕ храним
                self.app.current_title_ids = None
                self.app.set_view_state(ViewState(show_mode=show_mode, title_ids=page_ids))

            description = data_factory.get_metadata_description(show_mode=show_mode)
            show_modes = ['titles_list', 'franchise_list', 'need_to_see_list', 'ongoing_list']

            if not titles and description:
                self.log.info("Нет доступных данных для отображения, сбрасываем оффсет.")
                self.app.current_offset = 0
                self.app.total_titles = 0
                return

            if title_ids and len(title_ids) > 0:
                if self.app.current_offset >= len(title_ids):
                    self.log.warning(
                        f"Offset {self.app.current_offset} превышает количество доступных title_ids {len(title_ids)}. Сбрасываем offset.")
                    self.app.current_offset = 0

                if batch_size:
                    self.setup_pagination_ui(len(title_ids), batch_size, description)
                else:
                    pagination_widget = self.ui.parent_widgets.get("pagination_widget")
                    if pagination_widget:
                        pagination_widget.setVisible(False)
            elif show_mode in show_modes:
                self.log.info(f"Was sent to display {show_mode} ")
                count_titles = self.db.get_total_titles_count(show_mode=show_mode)
                self.setup_pagination_ui(count_titles, batch_size, description)
            else:
                pagination_widget = self.ui.parent_widgets.get("pagination_widget")
                if pagination_widget:
                    pagination_widget.setVisible(False)

            self.display_titles_in_ui(titles, show_mode)
            self.log.debug(f"Was sent to display {show_mode} {len(titles)} titles.")
            if isinstance(self.app.total_titles, list):
                self.log.debug(f"self.total_titles: {len(self.app.total_titles)}")
            else:
                self.log.debug(
                    f"self.total_titles is not a list, but {type(self.app.total_titles).__name__}: {self.app.total_titles}")

        except Exception as e:
            self.log.error(f"Ошибка display_titles: {e}")
        finally:
            self.ui.hide_loader()
            self.ui.set_buttons_enabled(True)

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
            if self.app.current_offset + batch_size >= total_count:
                self.log.info("End of the list, return to beginning")
                return 0
            else:
                return self.app.current_offset + batch_size
        else:
            return max(0, self.app.current_offset - batch_size)

    def setup_pagination_ui(self, count_titles, batch_size, description=None):
        """
        Настраивает отображение пагинации в UI.

        Args:
            count_titles: общее количество элементов
            batch_size: размер страницы
            description: описание текущего режима отображения
        """
        total_pages = (count_titles + batch_size - 1) // batch_size  # Округление вверх
        current_page = (self.app.current_offset // batch_size) + 1

        # Обновляем информацию о пагинации в UI
        self.ui.update_pagination_info(current_page, total_pages, count_titles, description)

        # Показываем виджет пагинации только если страниц больше одной
        pagination_widget = self.ui.parent_widgets.get("pagination_widget")
        self.log.debug(f"pagination_widget exists? {bool(pagination_widget)}")
        if pagination_widget:
            pagination_widget.setVisible(total_pages > 1)

    def display_titles_in_ui(self, titles, show_mode='default', row_start=0, col_start=0):
        if self.app.posters_layout is None:
            self.log.error("posters_layout is None: UI not initialized. Call init_ui() first.")
            return

        try:
            special_modes = {SHOW_SYSTEM, SHOW_AM_SCHEDULE, SHOW_AM_TITLES}
            self.app.clear_previous_posters()

            factory = TitleDisplayFactory(self.app)

            if show_mode in special_modes:
                widget, _ = factory.create(show_mode, titles)  # titles тут целиком список блоков/данных
                self.app.posters_layout.addWidget(widget, 0, 0, 1, 2)
            elif len(titles) == 1:
                widget, _ = factory.create(SHOW_ONE_TITLE, titles[0])
                self.app.posters_layout.addWidget(widget, 0, 0, 1, 2)
            else:
                for index, title in enumerate(titles):
                    title_widget, num_columns = factory.create(show_mode, title)
                    row = (index + row_start) // num_columns
                    column = (index + col_start) % num_columns
                    self.app.posters_layout.addWidget(title_widget, row, column)

            self.log.debug(f"Displayed {show_mode} with {len(titles)} titles.")
            app_state = self.app.get_current_state()
            QTimer.singleShot(100, lambda: self.app.state_manager.save_state(app_state))
        except Exception as e:
            self.log.error(f"Ошибка display_titles_in_ui: {e}")

    def display_info(self, title_id):
        """Отображает информацию о конкретном тайтле."""
        try:
            self.ui.show_loader("Loading title...")
            self.ui.set_buttons_enabled(False)

            self.app.clear_previous_posters()
            titles = self.db.get_titles_from_db(title_id=title_id)

            if not titles or titles[0] is None:
                self.log.error(f"Title with title_id {title_id} not found in the database.")
                return

            self.app.total_titles = titles
            self.app.set_view_state(ViewState(show_mode=SHOW_DEFAULT, title_id=title_id))

            pagination_widget = self.ui.parent_widgets.get("pagination_widget")
            if pagination_widget:
                pagination_widget.setVisible(False)

            self.display_titles_in_ui(titles)
        except Exception as e:
            self.log.error(f"Error display_info: {e}")

        finally:
            self.ui.hide_loader()
            self.ui.set_buttons_enabled(True)

    def display_titles_for_day(self, day_of_week, force_reload=False):
        """
        Отображает тайтлы для указанного дня недели.

        Args:
            day_of_week (int): День недели.
            force_reload (bool): Принудительно загрузить данные с сервера.
        """
        try:
            self.ui.show_loader("Loading schedule...")
            self.ui.set_buttons_enabled(False)

            self.app.clear_previous_posters()
            self.app.set_view_state(ViewState(show_mode=SHOW_DEFAULT, day_of_week=day_of_week))

            pagination_widget = self.ui.parent_widgets.get("pagination_widget")
            if pagination_widget:
                pagination_widget.setVisible(False)

            titles = None
            if not force_reload:
                titles = self.db.get_titles_from_db(show_all=False, day_of_week=day_of_week)
                self.log.debug(f"day_of_week: {day_of_week}, titles from DB: {len(titles)}")
            if titles:
                self.app.total_titles = {title.title_id for title in titles}
                self.display_titles_in_ui(titles)
            else:
                status, new_title_ids = self.app.fetch_and_process_schedule(day_of_week)
                if status and new_title_ids:
                    titles = self.db.get_titles_from_db(day_of_week=day_of_week)
                    self.app.total_titles = {title.title_id for title in titles}
                    self.display_titles_in_ui(titles)
                else:
                    self.display_titles(start=True)

        except Exception as e:
            self.log.error(f"Error displaying titles for day: {e}")
        finally:
            self.ui.hide_loader()
            self.ui.set_buttons_enabled(True)

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
        template = self.app.current_template
        self.log.debug(f"Пытаемся создать system_browser с параметрами: {len(statistics)}")
        return self.app.ui_s_generator.create_system_browser(statistics, template)

    def create_animedia_schedule_browser(self, schedule):
        """
        Прокси-метод, который делегирует создание animedia_schedule_browser в UIAMGenerator.
        """
        self.log.debug(f"Пытаемся создать animedia_schedule_browser с параметрами: {len(schedule)}")
        return self.app.ui_am_generator.create_animedia_schedule_browser(schedule)

    def create_animedia_titles_browser(self, titles):
        """
        Прокси-метод, который делегирует создание animedia_titles_browser в UIAMGenerator.
        """
        self.log.debug(f"Пытаемся создать animedia_titles_browser с параметрами: {len(titles)}")
        return self.app.ui_am_generator.create_animedia_titles_browser(titles)

    def create_title_browser(self, title, show_mode=SHOW_DEFAULT):
        """
        Прокси-метод, который делегирует создание title_browser в UIGenerator.
        """
        return self.app.ui_generator.create_title_browser(title, show_mode=show_mode)

    def reset_offset(self):
        self.app.current_offset = 0