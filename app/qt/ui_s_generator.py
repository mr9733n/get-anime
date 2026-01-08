# ui_s_generator.py
import logging
from PyQt6.QtWidgets import (
    QTextBrowser, QVBoxLayout, QWidget, QLineEdit,
    QPushButton, QHBoxLayout, QComboBox, QMessageBox
)

from utils.runtime.runtime_manager import restart_application
from app.qt.system_windows.settings_window import SettingsWindow
from app.qt.system_windows.audit_window import AuditLogWindow
from app.qt.system_windows.deleted_window import DeletedWindow
from app.qt.system_windows.log_window import LogWindow


LINE_EDIT_STYLE = """
    QLineEdit {
        background: rgba(255, 255, 255, 1.0);
        border: 1px solid #dcdcdc;
        border-radius: 6px;
        padding: 6px;
        font-size: 14px;
        color: #000;
    }
    QLineEdit:focus {
        border: 1px solid #0078d4;
    }
"""
BUTTON_STYLE = """
    QPushButton {
        color: #fff;
        padding: 8px 16px;
        border: none;
        border-radius: 8px;
        font-size: 14px;
        font-weight: bold;
        background: rgba(74, 74, 74, 1.0);
        width: 100px;
    }
    QPushButton:hover {
        background-color: #5c5c5c;
        border: 1px solid #888;
    }
    QPushButton:pressed {
        background-color: #000;
        border: 1px solid #555;
    }
"""
COMBOBOX_STYLE = """
    QComboBox {
        background: rgba(255, 255, 255, 1.0);
        border: 1px solid #dcdcdc;
        border-radius: 6px;
        padding: 6px 24px 6px 6px;
        font-size: 14px;
        color: #000;
        min-width: 80px;
    }
    QComboBox:hover {
        border: 1px solid #0078d4;
    }
    QComboBox::drop-down {
        subcontrol-origin: padding;
        subcontrol-position: top right;
        width: 20px;
        border-left: 1px solid #dcdcdc;
        background: #e0e0e0;
        border-top-right-radius: 6px;
        border-bottom-right-radius: 6px;
    }
    QComboBox::down-arrow {
        width: 10px;
        height: 10px;
    }
    QComboBox QAbstractItemView {
        background-color: #ffffff;
        border: 1px solid #dcdcdc;
        selection-background-color: #5c5c5c;
        color: #000;
        selection-color: #fff;
        outline: none;
    }
    QComboBox QAbstractItemView::item {
        padding: 6px;
        min-height: 24px;
        color: #000;
    }
    QComboBox QAbstractItemView::item:selected {
        background-color: #5c5c5c;
        color: #fff;
    }
"""


class UISGenerator:
    def __init__(self, app):
        self.logger = logging.getLogger(__name__)
        self.app = app
        self.system = None
        self.current_template = getattr(self.app, "current_template", "default")

        # UI elements
        self.template_apply_button = None
        self.template_selector = None
        self.log_window = None
        self.log_button = None
        self.add_studio_button = None
        self.title_ids_input = None
        self.studio_input = None
        self.delete_title_input = None
        self.delete_title_button = None
        self.settings_window = None
        self.settings_button = None
        self.optimize_button = None
        self.trash_button = None
        self.trash_window = None
        self.audit_button = None
        self.audit_window = None

    def create_line_edit(self, placeholder_text, parent, max_width=150):
        """Создает QLineEdit с предустановленным стилем."""
        line_edit = QLineEdit(parent)
        line_edit.setPlaceholderText(placeholder_text)
        line_edit.setStyleSheet(LINE_EDIT_STYLE)
        line_edit.setMaximumWidth(max_width)
        return line_edit

    def create_button(self, text, parent, callback, max_width=150):
        """Создает QPushButton с предустановленным стилем и обработчиком событий."""
        button = QPushButton(text, parent)
        button.setMaximumWidth(max_width)
        button.setStyleSheet(BUTTON_STYLE)
        button.clicked.connect(callback)
        return button

    def get_current_template(self):
        """Возвращает текущий шаблон из состояния приложения или из текущего атрибута self.app."""
        try:
            if self.system is not None and hasattr(self.system, "get_current_template_and_state"):
                name, st = self.system.get_current_template_and_state()
                return name, (st or {})

        except Exception as e:
            self.logger.error(f"Error in get_current_template: {e}")

        return "default", {}

    def create_template_selector(self, parent):
        """Создает выпадающий список с доступными шаблонами и устанавливает текущий."""
        combo_box = QComboBox(parent)
        combo_box.setMaximumWidth(200)
        combo_box.setStyleSheet(COMBOBOX_STYLE)

        try:
            if not self.system:
                # fallback: чтобы UI не ломался
                combo_box.addItems(["default"])
                combo_box.setCurrentIndex(0)
                self.logger.warning("SystemController is not set yet; template selector fallback to ['default']")
                return combo_box

            templates = self.system.list_templates() or ["default"]
            current_template, _ = self.get_current_template()

            templates = [t.strip() for t in templates if t and t.strip()]
            if not templates:
                templates = ["default"]

            current_template = (current_template or "default").strip()

            if "default" in templates:
                templates.remove("default")
                templates.insert(0, "default")

            combo_box.addItems(templates)

            if current_template in templates:
                combo_box.setCurrentIndex(templates.index(current_template))
            else:
                self.logger.warning(f"Текущий шаблон '{current_template}' отсутствует в списке!")

            return combo_box

        except Exception as e:
            self.logger.error(f"Ошибка в create_template_selector: {e}", exc_info=True)
            # fallback
            combo_box.clear()
            combo_box.addItems(["default"])
            combo_box.setCurrentIndex(0)
            return combo_box

    def switch_template(self):
        """Переключает текущий шаблон, сохраняя в state и перезапуская приложение."""
        try:
            template_name = self.template_selector.currentText()
            if not self.system:
                self.logger.error("SystemController is not set")
                return
            self.system.switch_template(template_name)



            self.logger.info(f"Шаблон сохранен в state: {template_name}")
            self.logger.info("Перезапуск приложения для применения шаблона...")
            restart_application()

        except Exception as e:
            self.logger.error(f"Ошибка при переключении шаблона: {e}")

    def create_system_browser(self, statistics, template):
        """Создает системный экран, отображающий количество всех тайтлов и франшиз."""
        try:
            self.logger.debug("Начинаем создание system_browser...")
            system_layout = QVBoxLayout()

            container_widget = QWidget(self.app)
            container_layout = QVBoxLayout()
            container_widget.setLayout(container_layout)

            system_browser = QTextBrowser(self.app)
            system_browser.setPlainText(f"Title: SYSTEM")

            system_browser.anchorClicked.connect(self.app.on_link_click)
            system_browser.setOpenExternalLinks(True)
            is_dark = template in ("no_background_night", "night", "dark")  # подстрой под свои имена

            text_color = "#eee" if is_dark else "#000"
            bg = "rgba(20, 20, 20, 0.55)" if is_dark else "rgba(255, 255, 255, 0.5)"
            border = "rgba(160, 160, 160, 0.45)" if is_dark else "#444"

            system_browser.setStyleSheet(f"""
                QTextBrowser {{
                    text-align: left;
                    border: 1px solid {border};
                    color: {text_color};
                    font-size: 14pt;
                    font-weight: bold;
                    position: relative;
                    background: {bg};
                }}
                /* Ссылки */
                QTextBrowser a {{
                    color: {"#7cb7ff" if is_dark else "#000a9f"};
                    text-decoration: underline;
                }}
                QTextBrowser a:hover {{
                    color: {"#a6d3ff" if is_dark else "#0078d4"};
                }}
            """)

            system_browser.setHtml(self._generate_statistics_html(statistics, template))
            container_layout.addWidget(system_browser)

            bottom_layout = QHBoxLayout()
            self.template_selector = self.create_template_selector(container_widget)
            self.template_apply_button = self.create_button("APPLY", container_widget, self.switch_template, max_width=100)
            self.studio_input = self.create_line_edit("STUDIO NAME", container_widget, max_width=180)
            self.title_ids_input = self.create_line_edit("TITLE ID", container_widget, max_width=120)
            self.add_studio_button = self.create_button("ADD", container_widget, self.add_studio_to_db, max_width=100)
            self.log_button = self.create_button("SHOW LOGS", container_widget, self.show_log_window, max_width=130)

            # TODO: Disabled for a while
            bottom_layout.addStretch()
            bottom_layout.addWidget(self.template_selector)
            bottom_layout.addWidget(self.template_apply_button)
            bottom_layout.addWidget(self.studio_input)
            bottom_layout.addWidget(self.title_ids_input)
            bottom_layout.addWidget(self.add_studio_button)
            bottom_layout.addWidget(self.log_button)
            bottom_layout.addStretch()

            bottom_layout2 = QHBoxLayout()
            self.delete_title_input = self.create_line_edit("DELETE TITLE IDs (comma-separated)", container_widget, max_width=200)
            self.delete_title_button = self.create_button("DELETE", container_widget, self.delete_titles_from_db, max_width=100)
            self.trash_button = self.create_button("DELETED", container_widget, self.show_trash_window, max_width=100)
            self.optimize_button = self.create_button("OPTIMIZE DB", container_widget, self.optimize_database, 130)
            self.settings_button = self.create_button("SETTINGS", container_widget, self.show_settings_window, 110)
            self.audit_button = self.create_button("AUDIT", container_widget, self.show_audit_window, max_width=100)


            bottom_layout2.addStretch()
            bottom_layout2.addWidget(self.delete_title_input)
            bottom_layout2.addWidget(self.delete_title_button)
            bottom_layout2.addWidget(self.trash_button)
            bottom_layout2.addWidget(self.audit_button)
            bottom_layout2.addWidget(self.optimize_button)
            bottom_layout2.addWidget(self.settings_button)
            bottom_layout2.addStretch()

            container_layout.addLayout(bottom_layout)
            container_layout.addLayout(bottom_layout2)
            system_layout.addWidget(container_widget)

            return system_layout
        except Exception as e:
            self.logger.error(f"Error create_system_browser: {e}")
            return None

    def show_log_window(self):
        if self.log_window is None or not self.log_window.isVisible():
            self.log_window = LogWindow("logs/debug_log.txt", self.current_template)
            self.log_window.closed.connect(lambda: self.log_button.setText("SHOW LOGS"))
            self.log_window.show()
            self.log_button.setText("HIDE LOGS")
        else:
            self.log_window.close()
            self.log_window = None
            self.log_button.setText("SHOW LOGS")

    def show_settings_window(self):
        """Открывает окно настроек."""
        if self.settings_window is None or not self.settings_window.isVisible():
            self.settings_window = SettingsWindow(
                config_manager=self.app.config_manager,
                config_file=self.app.config_manager.config_file,
                system_controller=self.system,
                theme=self.current_template,
                on_close=lambda: self.settings_button.setText("SETTINGS"),
                on_settings_changed=self._on_settings_saved,
            )
            self.settings_window.show()
            self.settings_button.setText("HIDE")
        else:
            self.settings_window.close()
            self.settings_window = None
            self.settings_button.setText("SETTINGS")

    def show_audit_window(self):
        if getattr(self, "audit_window", None) is not None and self.audit_window.isVisible():
            self.audit_window.close()
            self.audit_window = None
            return

        self.audit_window = AuditLogWindow(
            system_controller=self.system,
            button_style=BUTTON_STYLE,
            line_edit_style=LINE_EDIT_STYLE,
            theme=self.current_template,
        )

        self.audit_window.show()

    def show_trash_window(self):
        if self.trash_window is not None and self.trash_window.isVisible():
            self.trash_window.close()
            self.trash_window = None
            return

        self.trash_window = DeletedWindow(
            system_controller=self.system,
            button_style=BUTTON_STYLE,
            line_edit_style=LINE_EDIT_STYLE,
            theme=self.current_template,
        )

        self.trash_window.show()

    def add_studio_to_db(self):
        """Функция для добавления новой студии в базу данных."""
        studio_name = self.studio_input.text().strip()
        title_ids_str = self.title_ids_input.text().strip()

        try:
            if not studio_name or not title_ids_str:
                self.logger.error("Ошибка ввода: Пожалуйста, введите название студии и title_id(ы).")
                return

            keywords = title_ids_str.split(',')
            keywords = [kw.strip() for kw in keywords]

            if all(kw.isdigit() for kw in keywords):
                title_ids = [int(kw) for kw in keywords]
                self._handle_found_titles(title_ids, studio_name)

                self.logger.debug(f"Saved title_ids: {title_ids} with studio name {studio_name}")
            else:
                self.logger.error("Ошибка ввода: Все title_ids должны быть целыми числами.")
                return

        except Exception as e:
            self.logger.error(f"Ошибка при добавлении студии в базу данных: {e}")

    def delete_titles_from_db(self):
        """Удаление одного или нескольких тайтлов по списку title_id через запятую."""
        title_ids_str = self.delete_title_input.text().strip()

        try:
            if not title_ids_str:
                self.logger.error("Пустой ввод: укажите хотя бы один title_id для удаления.")
                return

            if self.system is None:
                self.logger.error("SystemController.trash_titles not available.")
                return

            reply = QMessageBox.question(
                self.app,
                "Confirm move to trash",
                f"Переместить в корзину: {title_ids_str}?\n\nЭто НЕ удалит данные физически.\nВосстановление возможно.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                self.logger.info("Удаление отменено пользователем.")
                return

            result = self.system.trash_titles(title_ids_str)
            deleted = result.get("deleted", [])
            not_found = result.get("not_found", [])

            if deleted:
                self.logger.info(f"Удалены тайтлы: {deleted}")
            if not_found:
                self.logger.warning(f"Тайтлы не найдены в БД и не были удалены: {not_found}")

            self.delete_title_input.clear()

        except Exception as e:
            self.logger.error(f"Ошибка при удалении тайтлов: {e}")

    def optimize_database(self):
        """Оптимизирует БД напрямую."""
        try:
            if not self.system:
                self.logger.error("SystemController is not set; cannot optimize DB")
                if hasattr(self.app, "show_error_notification"):
                    self.app.show_error_notification("Optimize DB", "System controller is not ready")
                return

            result = self.system.optimize_db()
            if result["status"] == "ok":
                saved_kb = (result["size_before"] - result["size_after"]) / 1024
                msg = f"Optimized! Saved {saved_kb:.1f}KB"
                self.logger.info(f"Database optimized, saved {saved_kb:.1f}KB")
                if hasattr(self.app, "show_error_notification"):
                    self.app.show_error_notification("Database optimized", msg)

            else:
                self.logger.error(f"Optimize failed: {result.get('error')}")
        except Exception as e:
            self.logger.error(f"Failed to optimize database: {e}")

    def _on_settings_saved(self):
        """Callback после сохранения настроек — перезапуск."""
        self.logger.info("Settings saved. Saving state + restarting...")

        try:
            # сохранить текущий state через сервисы (новая архитектура)
            if hasattr(self.app, "svc") and self.app.svc:
                self.app.svc.save_state(self.app.get_current_state())
        except Exception as e:
            self.logger.error(f"Failed to save state before restart: {e}")

        restart_application()

    def _handle_found_titles(self, title_ids, studio_name):
        """Обработка сохранения студий для одного или нескольких title_ids."""
        if self.system:
            self.system.add_studio(studio_name=studio_name, title_ids=title_ids)

        self.logger.debug(f"Обработка завершена для title_ids: {title_ids} с названием студии: {studio_name}")

    def _generate_statistics_html(self, statistics, template):
        """Создает HTML-контент для отображения статистики."""
        # Информация о версии приложения
        app_version = self.app.app_version
        # Извлечение статистики из аргумента statistics
        titles_count = statistics.get('titles_count', 0)
        franchises_count = statistics.get('franchises_count', 0)
        episodes_count = statistics.get('episodes_count', 0)
        posters_count = statistics.get('posters_count', 0)
        unique_translators_count = statistics.get('unique_translators_count', 0)
        teams_count = statistics.get('unique_teams_count', 0)
        blocked_titles_count = statistics.get('blocked_titles_count', 0)
        blocked_titles = statistics.get('blocked_titles', [])
        history_total_count = statistics.get('history_total_count', 0)
        history_total_watch_changes = statistics.get('history_total_watch_changes', 0)
        history_total_download_changes = statistics.get('history_total_download_changes', 0)
        need_to_see_count = statistics.get('need_to_see_count', 0)
        blocked_titles_list = ""

        template_name = template
        self.logger.debug(f"template for reload: {template}")
        # TODO:
        reset_offset_status = True

        if blocked_titles:
            blocked_titles_entries = blocked_titles.split(',')
            blocked_titles_list = ''.join(
                f'<li>{entry.strip()}</li>' for entry in blocked_titles_entries
            )

        self.logger.debug(f"Количество тайтлов: {titles_count}, Количество франшиз: {franchises_count}")
        self.logger.debug(f"Количество эпизодов: {episodes_count}, Количество постеров: {posters_count}")
        self.logger.debug(
            f"Количество уникальных переводчиков: {unique_translators_count}, Количество команд: {teams_count}")
        self.logger.debug(f"Количество заблокированных тайтлов: {blocked_titles_count}")
        self.logger.debug(f"blocked_titles: {blocked_titles}")

        return f'''
         <div style="font-size: 20pt;">
             <p>Application version: {app_version}</p>
             <p>Application DB statistics:</p>
         </div>
         <div style="margin: 30px;">
             <p><a href="reload_template/{template_name}">Reload template</a></p>
             <p><a href="reset_offset/{reset_offset_status}">Reset offset</a></p>
             <p>Количество тайтлов: {titles_count}</p>
             <p>Количество франшиз: {franchises_count}</p>
             <p>Количество эпизодов: {episodes_count}</p>
             <p>Количество постеров: {posters_count}</p>
             <p>Количество уникальных переводчиков: {unique_translators_count}</p>
             <p>Количество команд переводчиков: {teams_count}</p>
             <p>Количество заблокированных тайтлов: {blocked_titles_count}</p>
             <p>History total count: {history_total_count}</p>
             <p>History total watch_changes: {history_total_watch_changes}</p>
             <p>History total download changes: {history_total_download_changes}</p>
             <p>Need to see: {need_to_see_count}</p>
             <div class="blocked-titles">
                 <p>Заблокированные тайтлы (no more updates):</p>
                 <ul>{blocked_titles_list}</ul>
             </div>
         </div>
         '''
