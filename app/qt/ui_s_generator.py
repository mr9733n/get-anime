# ui_s_generator.py
import html
import logging
import re
from typing import Tuple, Optional
from urllib.parse import quote
from PyQt5.QtWidgets import QTextBrowser, QVBoxLayout, QWidget, QLineEdit, QPushButton, QHBoxLayout, QComboBox
from utils.runtime_manager import restart_application, LogWindow


# Константы для стилей
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
        border: 1px solid #0078d4;  /* синий цвет при фокусе */
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
        padding: 6px;
        font-size: 14px;
        color: #000;
    }
    QComboBox:hover {
        border: 1px solid #0078d4;
    }
    QComboBox::drop-down {
        border: none;
        width: 20px;
        background: #e0e0e0;
    }
    QComboBox::down-arrow {
        image: url(down_arrow.png); /* Можно заменить на иконку, если нужно */
        width: 16px;
        height: 16px;
    }
"""


class UISGenerator:
    def __init__(self, app, db_manager):
        self.logger = logging.getLogger(__name__)
        self.app = app
        self.db_manager = db_manager
        self.current_template = getattr(self.app, "current_template", "default")
        self.template_apply_button = None
        self.template_selector = None
        self.log_window = None
        self.log_button = None
        self.add_studio_button = None
        self.title_ids_input = None
        self.studio_input = None
        self.delete_title_input = None
        self.delete_title_button = None

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
            if hasattr(self.app, "db_manager") and hasattr(self.app.db_manager, "app_state_manager"):
                current_state = self.app.db_manager.app_state_manager.load_state()

                # Если стейт пуст, пробуем взять из self.app
                if not current_state:
                    self.logger.warning("Состояние приложения пустое, используем self.app.current_template")
                    return self.current_template, {}

                # Проверяем, есть ли ключ template_name
                template_name = current_state.get("template_name", "default")

                # Убираем лишние кавычки, если есть
                if isinstance(template_name, str) and template_name.startswith('"') and template_name.endswith('"'):
                    template_name = template_name.strip('"')

                return template_name, current_state

        except Exception as e:
            self.logger.error(f"Error in get_current_template: {e}")

        return "default", {}  # Если ошибка, возвращаем шаблон по умолчанию и пустой state

    def create_template_selector(self, parent):
        """Создает выпадающий список с доступными шаблонами и устанавливает текущий."""
        try:
            combo_box = QComboBox(parent)
            combo_box.setMaximumWidth(200)
            combo_box.setStyleSheet(COMBOBOX_STYLE)

            # Загружаем список шаблонов
            templates = self.db_manager.get_available_templates()

            # Получаем текущий шаблон
            current_template, _ = self.get_current_template()

            # Очистка пробелов и приведение к одному регистру
            templates = [t.strip() for t in templates]
            current_template = current_template.strip()

            # Сортируем так, чтобы default был первым (если есть)
            if "default" in templates:
                templates.remove("default")
                templates.insert(0, "default")

            # Добавляем шаблоны в QComboBox
            combo_box.addItems(templates)

            # Устанавливаем текущий шаблон
            if current_template in templates:
                index = templates.index(current_template)
                combo_box.setCurrentIndex(index)
                self.logger.info(f"Выбран текущий шаблон: {current_template} (index: {index})")
            else:
                self.logger.warning(f"Текущий шаблон '{current_template}' отсутствует в списке!")

            return combo_box
        except Exception as e:
            self.logger.error(f"Ошибка в create_template_selector: {e}")
            return None

    def switch_template(self):
        """Переключает текущий шаблон, сохраняя в state и перезапуская приложение."""
        try:
            template_name = self.template_selector.currentText()

            # Загружаем текущее состояние
            _, current_state = self.get_current_template()

            # Гарантируем, что current_state — это dict
            if not isinstance(current_state, dict):
                current_state = {}

            # Обновляем только template_name
            current_state["template_name"] = template_name

            # Сохраняем обновленный state
            self.app.db_manager.app_state_manager.save_state(current_state)
            self.logger.info(f"Шаблон сохранен в state: {template_name}")

            # Перезапускаем приложение
            self.logger.info("Перезапуск приложения для применения шаблона...")
            restart_application()

        except Exception as e:
            self.logger.error(f"Ошибка при переключении шаблона: {e}")

    def create_animedia_schedule_browser(self, schedule):
        try:
            animedia_schedule_layout = QVBoxLayout()

            container_widget = QWidget(self.app)
            container_layout = QVBoxLayout(container_widget)

            animedia_schedule_browser = QTextBrowser(container_widget)
            animedia_schedule_browser.anchorClicked.connect(self.app.on_link_click)
            animedia_schedule_browser.setOpenExternalLinks(True)
            animedia_schedule_browser.setStyleSheet("""
                text-align: left;
                border: 1px solid #444;
                color: #000;
                font-size: 12pt;
                font-weight: normal;
                background: rgba(255, 255, 255, 0.5);
            """)

            animedia_schedule_browser.setHtml(self._generate_animedia_schedule_html(schedule))

            container_layout.addWidget(animedia_schedule_browser)  # <-- ЭТОГО НЕ ХВАТАЛО
            animedia_schedule_layout.addWidget(container_widget)

            return animedia_schedule_layout
        except Exception as e:
            self.logger.error(f"Error create_animedia_schedule_browser: {e}")
            return None

    def create_system_browser(self, statistics, template):
        """Создает системный экран, отображающий количество всех тайтлов и франшиз."""
        try:
            self.logger.debug("Начинаем создание system_browser...")
            # Создаем главный вертикальный layout для системного экрана
            system_layout = QVBoxLayout()

            # Создаем контейнерный виджет и layout для него
            container_widget = QWidget(self.app)
            container_layout = QVBoxLayout()
            container_widget.setLayout(container_layout)
            # Создаем QTextBrowser для отображения информации о тайтлах и франшизах
            system_browser = QTextBrowser(self.app)
            system_browser.setPlainText(f"Title: SYSTEM")
            # system_browser.setProperty('title_id', title.title_id)
            system_browser.anchorClicked.connect(self.app.on_link_click)
            system_browser.setOpenExternalLinks(True)
            system_browser.setStyleSheet(
                """
                text-align: left;
                border: 1px solid #444;
                color: #000;
                font-size: 14pt;
                font-weight: bold;
                position: relative;
                background: rgba(255, 255, 255, 0.5);  /* Полупрозрачный желтый фон */
                """
            )

            system_browser.setHtml(self._generate_statistics_html(statistics, template))
            # Добавляем system_browser в layout контейнера
            container_layout.addWidget(system_browser)

            bottom_layout = QHBoxLayout()

            self.template_selector = self.create_template_selector(container_widget)
            self.template_apply_button = self.create_button("APPLY", container_widget, self.switch_template, max_width=100)

            self.studio_input = self.create_line_edit("STUDIO NAME", container_widget, max_width=180)
            self.title_ids_input = self.create_line_edit("TITLE ID", container_widget, max_width=120)
            self.add_studio_button = self.create_button("ADD", container_widget, self.add_studio_to_db, max_width=100)

            # TODO: Disabled for a while
            bottom_layout.addStretch()
            bottom_layout.addWidget(self.template_selector)
            bottom_layout.addWidget(self.template_apply_button)
            bottom_layout.addWidget(self.studio_input)
            bottom_layout.addWidget(self.title_ids_input)
            bottom_layout.addWidget(self.add_studio_button)
            bottom_layout.addStretch()

            bottom_layout2 = QHBoxLayout()
            self.delete_title_input = self.create_line_edit(
                "DELETE TITLE IDs (comma-separated)", container_widget, max_width=260
            )
            self.delete_title_button = self.create_button(
                "DELETE", container_widget, self.delete_titles_from_db, max_width=100
            )
            self.log_button = self.create_button("SHOW LOGS", container_widget, self.show_log_window, max_width=130)

            bottom_layout2.addStretch()
            bottom_layout2.addWidget(self.delete_title_input)
            bottom_layout2.addWidget(self.delete_title_button)
            bottom_layout2.addWidget(self.log_button)
            bottom_layout2.addStretch()

            container_layout.addLayout(bottom_layout)
            container_layout.addLayout(bottom_layout2)

            # Добавляем контейнерный виджет в основной layout
            system_layout.addWidget(container_widget)

            return system_layout
        except Exception as e:
            self.logger.error(f"Error create_system_browser: {e}")
            return None

    def show_log_window(self):
        if self.log_window is None or not self.log_window.isVisible():
            self.log_window = LogWindow("logs/debug_log.txt", self.current_template)
            self.log_window.closed.connect(lambda: self.log_button.setText("SHOW LOGS"))  # Подключаем сигнал
            self.log_window.show()
            self.log_button.setText("HIDE LOGS")  # Меняем текст кнопки
        else:
            self.log_window.close()
            self.log_window = None  # Сбрасываем переменную
            self.log_button.setText("SHOW LOGS")  # Возвращаем текст кнопки

    def add_studio_to_db(self):
        """Функция для добавления новой студии в базу данных."""
        studio_name = self.studio_input.text().strip()
        title_ids_str = self.title_ids_input.text().strip()

        try:
            # Проверка на пустой ввод
            if not studio_name or not title_ids_str:
                self.logger.error("Ошибка ввода: Пожалуйста, введите название студии и title_id(ы).")
                return

            # Преобразование title_ids из строки в список ключевых слов
            keywords = title_ids_str.split(',')
            keywords = [kw.strip() for kw in keywords]

            # Проверка, что ключевые слова содержат только целые числа
            if all(kw.isdigit() for kw in keywords):
                title_ids = [int(kw) for kw in keywords]
                self._handle_found_titles(title_ids, studio_name)

                self.logger.debug(f"Saved title_ids: {title_ids} with studio name {studio_name}")
            else:
                self.logger.error("Ошибка ввода: Все title_ids должны быть целыми числами.")
                return

        except Exception as e:
            self.logger.error(f"Ошибка при добавлении студии в базу данных: {e}")

    def _handle_found_titles(self, title_ids, studio_name):
        """Обработка сохранения студий для одного или нескольких title_ids."""
        if len(title_ids) == 1:
            # Если найден только один title_id, передаем его как единственное значение
            self.db_manager.save_studio_to_db([title_ids[0]], studio_name)
        else:
            # Если найдено несколько title_ids, передаем их все
            self.db_manager.save_studio_to_db(title_ids, studio_name)

        self.logger.debug(f"Обработка завершена для title_ids: {title_ids} с названием студии: {studio_name}")

    @staticmethod
    def _parse_line(s: str) -> Tuple[str, str, str, Optional[str], str]:
        """
        Возвращает:
            title, time_part, ep_part, poster_url, original_id
        """
        m = re.search(r"(https?://\S+\.(?:webp|jpg|jpeg|png))", s, flags=re.IGNORECASE)
        poster = m.group(1) if m else None
        core = s[:m.start()].strip() if m else s
        parts = [p.strip() for p in core.split("\u00B7")]
        title = parts[0] if len(parts) > 0 else ""
        time_part = parts[1] if len(parts) > 1 else ""
        ep_part = parts[2] if len(parts) > 2 else ""
        original_id = parts[3] if len(parts) > 3 else ""

        return title, time_part, ep_part, poster, original_id

    def _generate_animedia_schedule_html(self, schedule):
        if not schedule:
            return "<div style='padding:20px; font-size:14pt;'>Нет данных расписания AniMedia.</div>"

        rows = []
        rows.append("""
        <style>
        .am-title {
            color: #1f2933;        /* тёплый тёмно-серый, не чёрный */
            font-weight: 600;     /* вместо 600 */
            font-size: 14pt; 
            text-decoration: none;
        }
        .am-title:hover {
            text-decoration: underline;
        }
        .am-meta {
            margin-left: 6px;
            font-size: 12pt;
            font-weight: 600;
        }
        .am-time {
            color: #4b5563;        /* спокойный серо-графитовый */
        }
        .am-ep {
            color: #6b7280;        /* светлее времени */
        }
        </style>

        <div style="padding:18px;">
          <div style="font-size:20pt; font-weight:bold; margin-bottom:10px;">
            AniMedia — обновления
          </div>
          <div style="opacity:0.8; margin-bottom:18px; font-weight:bold;">
            Нажми на название, чтобы выполнить поиск в AniMedia.
          </div>
        """)

        for block in schedule:
            page = block.get("page")
            titles = block.get("titles") or []
            if not titles:
                continue

            if not page == 0:
                rows.append(f"<div style='margin:16px 0 8px; font-size:14pt; font-weight:bold;'>Новые серии аниме [{page}]</div>")
            else:
                rows.append(f"<div style='margin:16px 0 8px; font-size:14pt; font-weight:bold;'>Сегодня выйдет</div>")
            rows.append("<ul style='margin-left:16px; line-height:1.4;'>")

            for line in titles:
                title, time_part, ep_part, poster, original_id = self._parse_line(line)
                safe_title = html.escape(title)
                href = "am_search/" + quote(title) + "/" + original_id

                time_html = f"<span class='am-time'>{html.escape(time_part)}</span>" if time_part else ""
                ep_html = f"<span class='am-ep'>{html.escape(ep_part)}</span>" if ep_part else ""

                meta_html = ""
                if time_html or ep_html:
                    meta_html = f"<span class='am-meta'> {time_html}{' — ' if time_html and ep_html else ''}{ep_html}</span>"

                # TODO: download posters
                # img_html = f"<img src='{poster}' width='42' style='vertical-align:middle; margin-right:8px; border-radius:4px;'/>" if poster else ""
                img_html = ""

                rows.append(
                    f"<li style='margin:6px 0;'>"
                    f"{img_html}"
                    f"<a href='{href}' class='am-title'>{safe_title}</a>"
                    f"{meta_html}"
                    f"</li>"
                )

            rows.append("</ul>")
        rows.append("</div>")
        return "\n".join(rows)

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
            # Разделяем строку на элементы
            blocked_titles_entries = blocked_titles.split(',')
            # Формируем HTML список из элементов
            blocked_titles_list = ''.join(
                f'<li>{entry.strip()}</li>' for entry in blocked_titles_entries
            )
        # Логирование статистики
        self.logger.debug(f"Количество тайтлов: {titles_count}, Количество франшиз: {franchises_count}")
        self.logger.debug(f"Количество эпизодов: {episodes_count}, Количество постеров: {posters_count}")
        self.logger.debug(
            f"Количество уникальных переводчиков: {unique_translators_count}, Количество команд: {teams_count}")
        self.logger.debug(f"Количество заблокированных тайтлов: {blocked_titles_count}")
        self.logger.debug(f"blocked_titles: {blocked_titles}")

        # HTML контент для отображения статистики
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

    def delete_titles_from_db(self):
        """Удаление одного или нескольких тайтлов по списку title_id через запятую."""
        title_ids_str = self.delete_title_input.text().strip()

        try:
            if not title_ids_str:
                self.logger.error("Пустой ввод: укажите хотя бы один title_id для удаления.")
                return

            # просто пробрасываем строку в db_manager — он сам разберёт
            if not hasattr(self.db_manager, "delete_titles"):
                self.logger.error("db_manager.delete_titles не реализован.")
                return

            result = self.db_manager.delete_titles(title_ids_str)

            deleted = result.get("deleted", [])
            not_found = result.get("not_found", [])

            if deleted:
                self.logger.info(f"Удалены тайтлы: {deleted}")
            if not_found:
                self.logger.warning(f"Тайтлы не найдены в БД и не были удалены: {not_found}")

            # можно очистить поле после успешного вызова
            self.delete_title_input.clear()

        except Exception as e:
            self.logger.error(f"Ошибка при удалении тайтлов: {e}")
