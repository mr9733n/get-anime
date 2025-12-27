# app_helpers.py
import logging

from jinja2 import Template
from PyQt5.QtWidgets import QTextBrowser, QLabel, QWidget
from PyQt5.QtGui import QPixmap
from PyQt5.QtCore import Qt
from static.layout_metadata import show_mode_metadata


class TitleDisplayFactory:
    def __init__(self, app):
        self.logger = logging.getLogger(__name__)
        self.app = app

    def create(self, show_mode, title):
        """Создает UI-компоненты на основе режима отображения и возвращает количество столбцов для layout."""
        if show_mode not in show_mode_metadata:
            self.logger.warning(f"Режим отображения {show_mode} не найден. Используется 'default'.")
            show_mode = 'default'

        metadata = show_mode_metadata[show_mode]
        create_method_name = metadata.get("create_method", "create_default_widget")
        columns = metadata.get("columns", 2)

        create_method = getattr(self, create_method_name, self.create_default_widget)
        widget = create_method(title)
        return widget, columns

    def create_list_widget(self, title):
        """Создает виджет для списка тайтлов."""
        return self.app.create_title_browser(title, show_mode='titles_list')

    def create_one_title_widget(self, title):
        """Создает виджет для одного тайтла."""
        one_title_widget = QWidget(self.app)
        one_title_layout = self.app.create_title_browser(title, show_mode='one_title')
        one_title_widget.setLayout(one_title_layout)
        return one_title_widget

    def create_system_widget(self, statistics):
        """Создает виджет для системного режима."""
        system_widget = QWidget(self.app)
        system_layout = self.app.create_system_browser(statistics)
        system_widget.setLayout(system_layout)
        return system_widget

    def create_animedia_schedule_widget(self, schedule):
        """Create animedia schedule widget"""
        animedia_schedule_widget = QWidget(self.app)
        animedia_layout = self.app.create_animedia_schedule_browser(schedule)
        animedia_schedule_widget.setLayout(animedia_layout)
        return animedia_schedule_widget

    def create_animedia_titles_widget(self, titles):
        """Create animedia tiles widget"""
        animedia_titles_widget = QWidget(self.app)
        animedia_layout = self.app.create_animedia_titles_browser(titles)
        animedia_titles_widget.setLayout(animedia_layout)
        return animedia_titles_widget

    def create_default_widget(self, title):
        """Создает виджет по умолчанию."""
        return self.app.create_title_browser(title, show_mode='default')


class TitleDataFactory:
    def __init__(self, db_manager, user_id):
        self.logger = logging.getLogger(__name__)
        self.db_manager = db_manager
        self.user_id = user_id

    def get_metadata_description(self, show_mode='default'):
        """Return show_mode description"""
        try:
            return show_mode_metadata[show_mode].get("description")
        except Exception as e:
            self.logger.error(f"Error in get_metadata_description: {str(e)}")
            return ""

    def get_titles(self, show_mode='default', title_ids=None, current_offset=0, batch_size=None):
        """Возвращает данные тайтлов на основе режима отображения."""
        try:
            if show_mode not in show_mode_metadata:
                self.logger.warning(f"Режим отображения {show_mode} не найден. Используется 'default'.")
                show_mode = 'default'

            if batch_size is None:
                batch_size = show_mode_metadata[show_mode].get("batch_size", 2)

            data_fetcher_name = show_mode_metadata[show_mode].get("data_fetcher")
            pagination_modes = ['titles_genre_list', 'titles_team_member_list', 'titles_year_list', 'titles_status_list', 'titles_provider_list']

            if data_fetcher_name == 'system':
                return self.db_manager.get_statistics_from_db()

            elif str(data_fetcher_name) in [str(mode) for mode in pagination_modes]:
                if current_offset >= len(title_ids):
                    self.logger.warning(
                        f"Offset {current_offset} превышает количество доступных title_ids {len(title_ids)}. Сбрасываем offset.")
                    current_offset = 0

                if batch_size and len(title_ids) > batch_size:
                    end_idx = min(current_offset + batch_size, len(title_ids))
                    page_title_ids = title_ids[current_offset:end_idx]

                    self.logger.debug(f"Применяем пагинацию: {current_offset}:{end_idx} из {len(title_ids)} title_ids")

                    return self.db_manager.get_titles_from_db(show_all=False, title_ids=page_title_ids, offset=current_offset)
                else:
                    return self.db_manager.get_titles_from_db(show_all=False, title_ids=title_ids)

            elif data_fetcher_name and hasattr(self.db_manager, data_fetcher_name):
                data_fetcher = getattr(self.db_manager, data_fetcher_name)
                if callable(data_fetcher):
                    return data_fetcher(batch_size=batch_size, offset=current_offset)
                else:
                    return []
            elif title_ids:
                return self.db_manager.get_titles_from_db(show_all=False, offset=current_offset, title_ids=title_ids)
            else:
                return self.db_manager.get_titles_from_db(show_all=True, batch_size=batch_size, offset=current_offset)

        except Exception as e:
            self.logger.error(f"Error in get_titles: {str(e)}")
            return []

class TitleHtmlFactory:
    def __init__(self, app, template_name):
        self.logger = logging.getLogger(__name__)
        self.app = app
        self.current_template = template_name

    def generate_html(self, title, show_mode):
        """Генерирует HTML для отображения информации о тайтле в зависимости от show_mode."""
        try:
            self.logger.debug(f"Начинаем генерацию HTML для режима: {show_mode} с title_id: {title.title_id}")

            if show_mode not in show_mode_metadata:
                self.logger.warning(f"Режим отображения {show_mode} не найден. Используется 'default'.")
                show_mode = 'default'

            generator_name = show_mode_metadata[show_mode]["generator"]
            generator = getattr(self, generator_name, None)

            if not callable(generator):
                raise ValueError(f"Генератор {generator_name} не является вызываемой функцией.")

            html_content = generator(title)
            self.logger.debug(f"Генерация HTML завершена для режима: {show_mode}")
            return html_content

        except Exception as e:
            self.logger.error(f"Error in generate_html: {str(e)}")
            return ""

    def _generate_one_title_html(self, title):
        """Генерирует HTML для отображения одного тайтла."""
        try:
            provider_html = self.app.ui_generator.generate_provider_html(title.title_id)
            studio_html = self.app.ui_generator.generate_studio_html(title.title_id)
            reload_html = self.app.ui_generator.generate_reload_button_html(title.title_id)
            rating_html = self.app.ui_generator.generate_rating_html(title)
            announce_html = self.app.ui_generator.generate_announce_html(title)
            status_html = self.app.ui_generator.generate_status_html(title)
            description_html = self.app.ui_generator.generate_description_html(title)
            genres_html = self.app.ui_generator.generate_genres_html(title)
            team_html = self.app.ui_generator.generate_team_html(title)
            year_html = self.app.ui_generator.generate_year_html(title)
            type_html = self.app.ui_generator.generate_type_html(title)
            franchise_html = self.app.ui_generator.generate_franchise_html(title)
            episodes_html = self.app.ui_generator.generate_episodes_html(title)
            torrents_html = self.app.ui_generator.generate_torrents_html(title)

            _, one_title_html, _, styles_css = self.app.ui_generator.db_manager.get_template(self.current_template)
            poster_html = self.app.ui_generator.generate_poster_html(title, need_placeholder=True)
            reload_poster_html = self.app.ui_generator.generate_reload_poster_html(title)
            template = Template(one_title_html)
            html_content = template.render(
                title=title,
                styles_css=styles_css,
                poster_html=poster_html,
                reload_poster_html=reload_poster_html,
                provider_html=provider_html,
                reload_html=reload_html,
                rating_html=rating_html,
                announce_html=announce_html,
                status_html=status_html,
                studio_html=studio_html,
                team_html=team_html,
                description_html=description_html,
                genres_html=genres_html,
                year_html=year_html,
                type_html=type_html,
                franchise_html=franchise_html,
                episodes_html=episodes_html,
                torrents_html=torrents_html,

            )
            return html_content
        except Exception as e:
            self.logger.error(f"Error in _generate_one_title_html: {str(e)}")
            return ""

    def _generate_list_html(self, title):
        """Генерирует HTML для отображения списка тайтлов."""
        try:
            year_html = self.app.ui_generator.generate_year_html(title, show_text_list=True)
            status_html = self.app.ui_generator.generate_status_html(title, show_text_list=True)
            _, _, show_text_list_html, styles_css = self.app.ui_generator.db_manager.get_template(self.current_template)
            template = Template(show_text_list_html)
            html_content = template.render(
                title=title,
                styles_css=styles_css,
                year_html=year_html,
                status_html=status_html,
            )
            return html_content
        except Exception as e:
            self.logger.error(f"Error in _generate_list_html: {str(e)}")
            return ""

    def _generate_default_html(self, title):
        """Генерирует HTML по умолчанию."""
        try:
            self.logger.debug(f"Начинаем генерацию HTML по умолчанию для title_id: {title.title_id}")
            provider_html = self.app.ui_generator.generate_provider_html(title.title_id)
            reload_html = self.app.ui_generator.generate_reload_button_html(title.title_id)
            rating_html = self.app.ui_generator.generate_rating_html(title)
            announce_html = self.app.ui_generator.generate_announce_html(title)
            status_html = self.app.ui_generator.generate_status_html(title)
            description_html = ""
            genres_html = self.app.ui_generator.generate_genres_html(title)
            year_html = self.app.ui_generator.generate_year_html(title)
            type_html = self.app.ui_generator.generate_type_html(title)
            franchise_html = self.app.ui_generator.generate_franchise_html(title)
            episodes_html = self.app.ui_generator.generate_episodes_html(title)
            torrents_html = self.app.ui_generator.generate_torrents_html(title)

            titles_html, _, _, styles_css = self.app.ui_generator.db_manager.get_template(self.current_template)
            poster_html = self.app.ui_generator.generate_poster_html(title, need_background=True)
            reload_poster_html = self.app.ui_generator.generate_reload_poster_html(title)
            show_more_html = self.app.ui_generator.generate_show_more_html(title.title_id)

            template = Template(titles_html)
            html_content = template.render(
                title=title,
                styles_css=styles_css,
                poster_html=poster_html,
                reload_poster_html=reload_poster_html,
                provider_html=provider_html,
                reload_html=reload_html,
                rating_html=rating_html,
                show_more_html=show_more_html,
                announce_html=announce_html,
                status_html=status_html,
                description_html=description_html,
                genres_html=genres_html,
                year_html=year_html,
                type_html=type_html,
                franchise_html=franchise_html,
                episodes_html=episodes_html,
                torrents_html=torrents_html,
                new_line='<br /><br /><br /><br />'
            )
            return html_content
        except Exception as e:
            self.logger.error(f"Error in _generate_default_html: {str(e)}")
            return ""


class TitleBrowserFactory:
    def __init__(self, app):
        self.logger = logging.getLogger(__name__)
        self.app = app

    def create_title_browser_widget(self, title, show_mode):
        """Создает и настраивает виджет QTextBrowser для отображения информации о тайтле."""
        metadata = show_mode_metadata.get(show_mode, show_mode_metadata['default'])
        create_method_name = metadata.get("create_method", "create_default_widget")
        create_method = getattr(self, create_method_name, self.create_default_widget)
        return create_method(title, show_mode)

    def create_one_title_widget(self, title, show_mode):
        title_browser = QTextBrowser(self.app)
        title_browser.setPlainText(f"Title: {title.name_en}")
        title_browser.setOpenExternalLinks(True)
        title_browser.setProperty('title_id', title.title_id)
        title_browser.anchorClicked.connect(self.app.on_link_click)
        title_browser.setFixedSize(455, 650)
        html_content = self.app.ui_generator.get_title_html(title, show_mode)
        title_browser.setHtml(html_content)
        return title_browser

    def create_list_widget(self, title, show_mode):
        """Создает виджет для списка тайтлов."""
        title_browser = QTextBrowser(self.app)
        title_browser.setPlainText(f"Title: {title.name_en}")
        title_browser.setOpenExternalLinks(True)
        title_browser.setProperty('title_id', title.title_id)
        title_browser.anchorClicked.connect(self.app.on_link_click)

        title_browser.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        title_browser.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        title_browser.setStyleSheet("""
            text-align: right;
            border: 1px solid #444;
            width: 100%;
            height: 100%;
            position: relative;
            background: rgba(255, 255, 255, 0.5);  /* Полупрозрачный фон */
        """)

        html_content = self.app.ui_generator.get_title_html(title, show_mode)
        title_browser.setHtml(html_content)

        return title_browser

    def create_default_widget(self, title, show_mode):
        """Создает виджет по умолчанию."""
        title_browser = QTextBrowser(self.app)
        title_browser.setPlainText(f"Title: {title.name_en}")
        title_browser.setOpenExternalLinks(True)
        title_browser.setProperty('title_id', title.title_id)
        title_browser.anchorClicked.connect(self.app.on_link_click)

        title_browser.setFixedSize(455, 650)
        html_content = self.app.ui_generator.get_title_html(title, show_mode)
        title_browser.setHtml(html_content)

        return title_browser

    def create_poster_widget(self, title_id):
        """Создает и настраивает QLabel для отображения постера тайтла."""
        poster_label = QLabel(self.app)
        poster_data = self.app.get_poster_or_placeholder(title_id)
        if poster_data:
            pixmap = QPixmap()
            if pixmap.loadFromData(poster_data):
                poster_label.setPixmap(pixmap.scaled(455, 650, Qt.KeepAspectRatio))
            else:
                self.app.logger.error(f"Error: Failed to load pixmap from data for title_id: {title_id}")
                poster_label.setPixmap(QPixmap("static/no_image.png").scaled(455, 650, Qt.KeepAspectRatio))
        else:
            poster_label.setPixmap(QPixmap("static/no_image.png").scaled(455, 650, Qt.KeepAspectRatio))
        return poster_label