# ui_s_generator.py
import logging

from PyQt5.QtWidgets import QTextBrowser, QVBoxLayout, QWidget


class UISGenerator:
    def __init__(self, app, db_manager):
        self.logger = logging.getLogger(__name__)
        self.app = app
        self.db_manager = db_manager

    def create_system_browser(self, statistics):
        """Создает системный экран, отображающий количество всех тайтлов и франшиз."""
        try:
            self.logger.debug("Начинаем создание system_browser...")
            # Создаем главный вертикальный layout для системного экрана
            system_layout = QVBoxLayout()
            # Создаем виджет, чтобы обернуть все элементы вместе
            container_widget = QWidget(self.app)
            container_layout = QVBoxLayout(container_widget)
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
            # HTML контент для отображения статистики
            html_content = f'''
            <div style="font-size: 20pt;">
                <p>Application version: {app_version}</p>
                <p>Application DB statistics:</p>
            </div>
            <div style="margin: 30px;">
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
            system_browser.setHtml(html_content)
            # Добавляем элементы в layout контейнера
            container_layout.addWidget(system_browser)
            # Добавляем контейнер в основной layout
            system_layout.addWidget(container_widget)
            return system_layout
        except Exception as e:
            self.logger.error(f"Error create_system_browser: {e}")
            return None

