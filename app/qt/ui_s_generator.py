# ui_s_generator.py
import logging
from tempfile import template

from PyQt5.QtWidgets import QTextBrowser, QVBoxLayout, QWidget, QLineEdit, QPushButton, QHBoxLayout, QGroupBox


class UISGenerator:
    def __init__(self, app, db_manager):
        self.add_studio_button = None
        self.title_ids_input = None
        self.studio_input = None
        self.logger = logging.getLogger(__name__)
        self.app = app
        self.db_manager = db_manager

    def create_system_browser(self, statistics):
        """Создает системный экран, отображающий количество всех тайтлов и франшиз."""
        try:
            self.logger.debug("Начинаем создание system_browser...")
            # Создаем главный вертикальный layout для системного экрана
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
                text-shadow: 1px 1px 2px #FFF;  /* Тень для выделения текста */
                background: rgba(255, 255, 0, 0.5);  /* Полупрозрачный желтый фон */
                """
            )
            system_browser.setHtml(self._generate_statistics_html(statistics))
            # Добавляем system_browser в layout контейнера
            container_layout.addWidget(system_browser)

            input_layout = QHBoxLayout()
            # Поле ввода для добавления новой студии
            self.studio_input = QLineEdit(container_widget)
            self.studio_input.setPlaceholderText("STUDIO NAME")
            self.title_ids_input = QLineEdit(container_widget)
            self.title_ids_input.setPlaceholderText("TITLE ID")
            # Установка стилей для полей ввода
            line_edit_style = """
                    QLineEdit {
                text-shadow: 1px 1px 2px #FFF;  /* Тень для выделения текста */
                background: rgba(255, 255, 255);  /* Полупрозрачный желтый фон */
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
            self.title_ids_input.setStyleSheet(line_edit_style)
            self.studio_input.setStyleSheet(line_edit_style)

            # Установка минимальных и максимальных размеров для полей ввода
            self.title_ids_input.setMaximumWidth(150)
            self.studio_input.setMaximumWidth(150)

            # Кнопка для сохранения новой студии
            self.add_studio_button = QPushButton("ADD", container_widget)
            self.add_studio_button.setMaximumWidth(150)
            # Установка стилей для кнопки "#4a4a4a", "#5c5c5c", "#000"
            self.add_studio_button.setStyleSheet("""
                QPushButton {
                    color: #fff;
                    padding: 8px 16px;
                    border: none;
                    border-radius: 8px;
                    font-size: 14px;
                    font-weight: bold;
                    background: rgba(74, 74 , 74);

                    width = 100px;
                }
                QPushButton:hover {
                    background-color: #5c5c5c;
                    border: 1px solid #888;
                }
                QPushButton:pressed {
                    background-color: #000;
                    border: 1px solid #555;
                }
                """)
            # Добавляем обработчик клика для кнопки
            self.add_studio_button.clicked.connect(self.add_studio_to_db)

            input_layout.addWidget(self.studio_input)
            input_layout.addWidget(self.title_ids_input)
            input_layout.addWidget(self.add_studio_button)

            # Добавляем input_layout в контейнерный layout
            container_layout.addLayout(input_layout)

            # Добавляем контейнерный виджет в основной layout
            system_layout.addWidget(container_widget)

            return system_layout
        except Exception as e:
            self.logger.error(f"Error create_system_browser: {e}")
            return None

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


    def _generate_statistics_html(self, statistics):
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
        # TODO: fix this
        template_name = 'default'

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