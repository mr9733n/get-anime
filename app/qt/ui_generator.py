import re
import subprocess

from PyQt5.QtWidgets import QTextBrowser, QLabel, QHBoxLayout, QVBoxLayout, QWidget
from PyQt5.QtGui import QPixmap
from PyQt5.QtCore import Qt, QByteArray, QBuffer, QTimer
from app.qt.ui_manger import UIManager
import base64
import logging
from jinja2 import Template

class UIGenerator:
    def __init__(self, app, db_manager):
        self.logger = logging.getLogger(__name__)
        self.app = app
        self.db_manager = db_manager
        self.blank_spase = '&nbsp;'
        # TODO: fix this rating system
        self.rating_name = 'CMERS'
        self.max_rating = 6

    def create_title_browser(self, title, show_description=False, show_one_title=False, show_list=False,
                             show_franchise=False):
        """Создает элемент интерфейса для отображения информации о тайтле.
        :param title:
        :param show_description:
        :param show_one_title:
        :param show_list:
        :param show_franchise:
        :return:
        """
        try:
            self.logger.debug("Начинаем создание title_browser...")
            title_browser = QTextBrowser(self.app)
            title_browser.setPlainText(f"Title: {title.name_en}")
            title_browser.setOpenExternalLinks(True)
            title_browser.setProperty('title_id', title.title_id)
            title_browser.anchorClicked.connect(self.app.on_link_click)
            # Общие настройки для различных режимов отображения
            if show_one_title:
                # Создаем горизонтальный layout для отображения деталей тайтла
                title_layout = QHBoxLayout()
                self.logger.debug(f"Создаем title_browser для title_id: {title.title_id}")
                # Постер слева
                poster_label = QLabel(self.app)
                poster_data = self.app.get_poster_or_placeholder(title.title_id)
                if poster_data:
                    pixmap = QPixmap()
                    if pixmap.loadFromData(poster_data):
                        poster_label.setPixmap(pixmap.scaled(455, 650, Qt.KeepAspectRatio))
                    else:
                        self.logger.error(f"Error: Failed to load pixmap from data for title_id: {title.title_id}")
                        poster_label.setPixmap(QPixmap("static/no_image.png").scaled(455, 650, Qt.KeepAspectRatio))
                else:
                    poster_label.setPixmap(QPixmap("static/no_image.png").scaled(455, 650, Qt.KeepAspectRatio))
                title_layout.addWidget(poster_label)
                # Информация о тайтле справа
                title_browser.setFixedSize(455, 650)
                html_content = self.get_title_html(title, show_description=True, show_more_link=False)
                title_browser.setHtml(html_content)
                # Добавляем title_browser в layout
                title_layout.addWidget(title_browser)
                return title_layout
            elif show_list or show_franchise:
                self.logger.debug(
                    f"Create title_browser {'show_list' if show_list else 'show_franchise'}, title_id: {title.title_id}")
                title_browser.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
                title_browser.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
                title_browser.setStyleSheet(
                    """
                    text-align: right;
                    border: 1px solid #444;
                    width: 100%;
                    height: 100%;
                    position: relative;
                    background: rgba(255, 255, 0, 0.5);  /* Полупрозрачный желтый фон */
                    """
                )
                html_content = self.get_title_html(title, show_text_list=True)
                title_browser.setHtml(html_content)
                return title_browser
            else:
                self.logger.debug(f"Создаем title_browser для title_id: {title.title_id}")
                title_browser.setFixedSize(455, 650)  # Размер плитки
                html_content = self.get_title_html(title, show_description, show_more_link=True)
                title_browser.setHtml(html_content)
                return title_browser
        except Exception as e:
            error_message = f"Error in create_title_browser: {str(e)}"
            self.logger.error(error_message)

    def get_title_html(self, title, show_description=False, show_more_link=False, show_text_list=False):
        """Генерирует HTML для отображения информации о тайтле."""
        try:
            # Общие компоненты, которые всегда требуются
            reload_html = self.generate_reload_button_html(title.title_id)
            rating_html = self.generate_rating_html(title)
            announce_html = self.generate_announce_html(title)
            status_html = self.generate_status_html(title)
            description_html = self.generate_description_html(title) if show_description else ""
            genres_html = self.generate_genres_html(title)
            year_html = self.generate_year_html(title)
            type_html = self.generate_type_html(title)
            episodes_html = self.generate_episodes_html(title)
            torrents_html = self.generate_torrents_html(title)

            titles_html, one_title_html, show_text_list_html, styles_css = self.db_manager.get_template()

            if show_more_link and titles_html:
                poster_html = self.generate_poster_html(title, need_background=True)
                show_more_html = self.generate_show_more_html(title.title_id)
                template = Template(titles_html)
                html_content = template.render(
                    title=title,
                    styles_css=styles_css,
                    poster_html=poster_html,
                    reload_html=reload_html,
                    rating_html=rating_html,
                    show_more_html=show_more_html,
                    announce_html=announce_html,
                    status_html=status_html,
                    description_html=description_html,
                    genres_html=genres_html,
                    year_html=year_html,
                    type_html=type_html,
                    episodes_html=episodes_html,
                    torrents_html=torrents_html,
                    new_line='<br /><br /><br /><br />'
                )
                return html_content

            if show_text_list and show_text_list_html:
                year_html = self.generate_year_html(title, show_text_list=True)
                template = Template(show_text_list_html)
                html_content = template.render(
                    title=title,
                    styles_css=styles_css,
                    year_html=year_html,
                )
                return html_content

            elif one_title_html:
                poster_html = self.generate_poster_html(title, need_placeholder=True)
                template = Template(one_title_html)
                html_content = template.render(
                    title=title,
                    styles_css=styles_css,
                    poster_html=poster_html,
                    reload_html=reload_html,
                    rating_html=rating_html,
                    announce_html=announce_html,
                    status_html=status_html,
                    description_html=description_html,
                    genres_html=genres_html,
                    year_html=year_html,
                    type_html=type_html,
                    episodes_html=episodes_html,
                    torrents_html=torrents_html,
                )
                return html_content

        except Exception as e:
            error_message = f"Error in get_title_html: {str(e)}"
            self.logger.error(error_message)
            return ""

    def generate_reload_button_html(self, title_id):
        """Generates HTML to display reload button"""
        try:
            image_base64 = self.prepare_generate_poster_html(7)
            # TODO: fix blank spase
            blank_spase = self.blank_spase

            reload_link = f'<a href="reload_info/{title_id}" title="Reload title"><img src="data:image/png;base64,{image_base64}" /></a>{blank_spase * 16}'
            return reload_link
        except Exception as e:
            error_message = f"Error in generate_reload_button_html: {str(e)}"
            self.logger.error(error_message)

    def generate_show_more_html(self, title_id):
        """Generates HTML to display 'show more' link"""
        try:
            return f'<a href=display_info/{title_id}>Подробнее</a>'
        except Exception as e:
            error_message = f"Error in generate_show_more_html: {str(e)}"
            self.logger.error(error_message)

    def generate_rating_html(self, title):
        """Generates HTML to display ratings and allows updating"""
        try:
            ratings = self.db_manager.get_rating_from_db(title.title_id)
            rating_star_images = []
            poster_base64_full = self.prepare_generate_poster_html(4)
            poster_base64_blank = self.prepare_generate_poster_html(3)
            image_html_full = f'<img src="data:image/png;base64,{poster_base64_full}" />'
            image_html_blank = f'<img src="data:image/png;base64,{poster_base64_blank}" />'

            if ratings:
                rating_name = ratings.rating_name
                rating_value = ratings.rating_value
                for i in range(self.max_rating):
                    if i < rating_value:
                        rating_star_images.append(
                            f'<a href="set_rating/{title.title_id}/{rating_name}/{i + 1}">{image_html_full}</a>')
                    else:
                        rating_star_images.append(
                            f'<a href="set_rating/{title.title_id}/{rating_name}/{i + 1}">{image_html_blank}</a>')
            else:
                rating_name = self.rating_name
                for i in range(self.max_rating):
                    rating_star_images.append(
                        f'<a href="set_rating/{title.title_id}/{rating_name}/{i + 1}">{image_html_blank}</a>')

            # TODO: fix blank spase
            blank_spase = self.blank_spase
            rating_value = ''.join(rating_star_images)
            watch_html = self.generate_watch_history_html(title.title_id)
            need_to_see_html = self.generate_nee_to_see_html(title.title_id)
            return f'{watch_html}{blank_spase}{title.title_id}{blank_spase}{need_to_see_html}{blank_spase * 4}{rating_name}:{blank_spase}{rating_value}'
        except Exception as e:
            error_message = f"Error in generate_rating_html: {str(e)}"
            self.logger.error(error_message)

    def generate_download_history_html(self, title_id, torrent_id):
        """Generates HTML to display download history"""
        try:
            image_base64_green = self.prepare_generate_poster_html(9)
            image_base64_red = self.prepare_generate_poster_html(8)
            image_html_green = f'<img src="data:image/png;base64,{image_base64_green}" alt="Set download status" />'
            image_html_red = f'<img src="data:image/png;base64,{image_base64_red}" alt="Set download status" />'
            # TODO: fix it later
            user_id = self.app.user_id

            if torrent_id:
                _, is_download = self.db_manager.get_history_status(user_id, title_id, torrent_id=torrent_id)
                self.logger.debug(
                    f"user_id/title_id/torrent_id: {user_id}/{title_id}/{torrent_id} Status:{is_download}")
                if is_download:
                    html = f'<a href="set_download_status/{user_id}/{title_id}/{torrent_id}" title="Set download status">{image_html_green}</a>'
                    return html
                return f'<a href="set_download_status/{user_id}/{title_id}/{torrent_id}" title="Set download status">{image_html_red}</a>'
        except Exception as e:
            error_message = f"Error in generate_download_history_html: {str(e)}"
            self.logger.error(error_message)

    def generate_watch_all_episodes_html(self, title_id, episode_ids):
        """Generates HTML to display watch history"""
        try:
            image_base64_watched = self.prepare_generate_poster_html(6)
            image_base64_blank = self.prepare_generate_poster_html(5)
            image_html_green = f'<img src="data:image/png;base64,{image_base64_watched}" alt="Set watch all episodes" />'
            image_html_red = f'<img src="data:image/png;base64,{image_base64_blank}" alt="Set watch all episodes" />'
            # TODO: fix it later
            user_id = self.app.user_id

            all_watched = self.db_manager.get_all_episodes_watched_status(user_id, title_id)
            self.logger.debug(f"user_id/title_id/episode_ids: {user_id}/{title_id}/{len(episode_ids)} Status:{all_watched}")
            if all_watched:
                return f'<a href="set_watch_all_episodes_status/{user_id}/{title_id}/{episode_ids}" title="Set watch all episodes">{image_html_green}</a>'
            return f'<a href="set_watch_all_episodes_status/{user_id}/{title_id}/{episode_ids}" title="Set watch all episodes">{image_html_red}</a>'
        except Exception as e:
            error_message = f"Error in generate_watch_all_episodes_html: {str(e)}"
            self.logger.error(error_message)

    def generate_nee_to_see_html(self, title_id):
        """Generates HTML to display watch history"""
        try:
            image_base64_green = self.prepare_generate_poster_html(11)
            image_base64_red = self.prepare_generate_poster_html(10)
            image_html_green = f'<img src="data:image/png;base64,{image_base64_green}" alt="Need to see" />'
            image_html_red = f'<img src="data:image/png;base64,{image_base64_red}" alt="Need to see" />'
            # TODO: fix it later
            user_id = self.app.user_id

            if title_id:
                is_need_to_see = self.db_manager.get_need_to_see(user_id, title_id)
                self.logger.debug(f"user_id/title_id : {user_id}/{title_id} Status:{is_need_to_see}")
                if is_need_to_see:
                    return f'<a href="set_need_to_see/{user_id}/{title_id}" title="Set need to see">{image_html_green}</a>'
                return f'<a href="set_need_to_see/{user_id}/{title_id}" title="Set need to see">{image_html_red}</a>'
        except Exception as e:
            error_message = f"Error in generate_nee_to_see_html: {str(e)}"
            self.logger.error(error_message)

    def generate_watch_history_html(self, title_id, episode_id=None):
        """Generates HTML to display watch history"""
        try:
            image_base64_watched = self.prepare_generate_poster_html(6)
            image_base64_blank = self.prepare_generate_poster_html(5)
            image_html_green = f'<img src="data:image/png;base64,{image_base64_watched}" alt="Set watch status" />'
            image_html_red = f'<img src="data:image/png;base64,{image_base64_blank}" alt="Set watch status" />'
            # TODO: fix it later
            user_id = self.app.user_id

            if episode_id or title_id:
                is_watched, _ = self.db_manager.get_history_status(user_id, title_id, episode_id=episode_id)
                self.logger.debug(f"user_id/title_id/episode_id: {user_id}/{title_id}/{episode_id} Status:{is_watched}")
                if is_watched:
                    return f'<a href="set_watch_status/{user_id}/{title_id}/{episode_id}" title="Set watch status">{image_html_green}</a>'
                return f'<a href="set_watch_status/{user_id}/{title_id}/{episode_id}" title="Set watch status">{image_html_red}</a>'
        except Exception as e:
            error_message = f"Error in generate_watch_history_html: {str(e)}"
            self.logger.error(error_message)

    def generate_play_all_html(self, title):
        """Generates M3U Playlist link"""
        try:
            self.app.stream_video_url = title.host_for_player
            playlist = self.app.playlists.get(title.title_id)
            if playlist:
                sanitized_title = playlist['sanitized_title']
                discovered_links = playlist['links']
                if discovered_links:
                    filename = self.app.playlist_manager.save_playlist([sanitized_title], discovered_links,
                                                                   self.app.stream_video_url)

                    self.logger.debug(
                        f"Playlist for title {sanitized_title} was sent for saving with filename: {filename}.")
                    return f'<a href="play_all/{title.title_id}/{filename}">Play all</a>'
                else:
                    self.logger.error(f"No links found for title {sanitized_title}, skipping saving.")
                    return "No playlist available"
            else:
                return "No playlist available"
        except Exception as e:
            error_message = f"Error in generate_play_all_html: {str(e)}"
            self.logger.error(error_message)

    def generate_torrents_html(self, title):
        """Generates HTML to display a list of torrents for a title."""
        try:
            self.app.torrent_data = {}
            # TODO: fix blank spase
            blank_spase = self.blank_spase
            torrents = self.db_manager.get_torrents_from_db(title.title_id)

            if not torrents:
                return "<p>Torrents not available</p>"

            torrents_html = "<ul>"
            for torrent in torrents:
                torrent_quality = torrent.quality if torrent.quality else "Unknown Quality"
                torrent_size = torrent.size_string if torrent.size_string else "Unknown Size"
                torrent_link = torrent.url if torrent.url else "#"
                download_html = self.generate_download_history_html(title.title_id, torrent.torrent_id)
                torrent_link_html = f'<a href="{torrent_link}" target="_blank">{torrent_quality} ({torrent_size})</a>'
                torrents_html += f'<li>{torrent_link_html}{blank_spase * 4}{download_html}</li>'
                self.app.torrent_data = torrent.title_id, title.code, torrent.torrent_id
            torrents_html += "</ul>"

            return torrents_html
        except Exception as e:
            error_message = f"Error in generate_torrents_html: {str(e)}"
            self.logger.error(error_message)

    def prepare_generate_poster_html(self, title_id):
        try:
            poster_data = self.app.get_poster_or_placeholder(title_id)
            pixmap = QPixmap()
            if not pixmap.loadFromData(poster_data):
                self.logger.error(f"Error: Failed to load image data for title_id: {title_id}")
                return None

            # Используем QBuffer для сохранения в байтовый массив
            byte_array = QByteArray()
            buffer = QBuffer(byte_array)
            buffer.open(QBuffer.WriteOnly)
            if not pixmap.save(buffer, 'PNG'):
                self.logger.error(f"Error: Failed to save image as PNG for title_id: {title_id}")
                return None

            # Преобразуем данные в Base64
            poster_base64 = base64.b64encode(byte_array.data()).decode('utf-8')
            return poster_base64

        except Exception as e:
            self.logger.error(f"Error processing poster for title_id: {title_id} - {e}")
            return None

    def generate_poster_html(self, title, need_image=False, need_background=False, need_placeholder=False):
        """Generates HTML for the poster in Base64 format or returns a placeholder."""
        try:
            # Попытка получить постер из базы данных
            if need_placeholder:
                poster_base64 = self.prepare_generate_poster_html(2)
            else:
                poster_base64 = self.prepare_generate_poster_html(title.title_id)
            if need_image:
                return f'<img src="data:image/png;base64,{poster_base64}" alt="{title.title_id}.{title.code}" style=\"float: left; margin-right: 20px;\"" />'
            elif need_background:
                return f'background-image: url("data:image/png;base64,{poster_base64}");'

            # TODO: fix this return
            return f"background-image: url('static/background.png');"
        except Exception as e:
            self.logger.error(f"Error processing poster for title_id: {title.title_id} - {e}")
            # TODO: fix this return
            return f"background-image: url('static/background.png');"

    def generate_genres_html(self, title):
        """Генерирует HTML для отображения жанров."""
        try:
            if hasattr(title, 'genre_names') and title.genre_names:
                try:
                    # Используем жанры в виде списка строк
                    genres_list = title.genre_names
                    genres = ', '.join(genres_list) if genres_list else "Жанры отсутствуют"
                except Exception as e:
                    self.logger.error(f"Ошибка при генерации HTML жанров: {e}")
                    genres = "Жанры отсутствуют"
            else:
                genres = "Жанры отсутствуют"

            return f"""<p>Жанры: {genres}</p>"""

        except Exception as e:
            error_message = f"Error in generate_genres_html: {str(e)}"
            self.logger.error(error_message)

    def generate_announce_html(self, title):
        """Генерирует HTML для отображения анонса."""
        try:
            title_announced = title.announce if title.announce else 'Анонс отсутствует'
            return f"""<p>Анонс: {title_announced}</p>"""

        except Exception as e:
            error_message = f"Error in generate_announce_html: {str(e)}"
            self.logger.error(error_message)

    def generate_status_html(self, title):
        """Генерирует HTML для отображения статуса."""
        try:
            title_status = title.status_string if title.status_string else "Статус отсутствует"
            return f"""<p>Статус: {title_status}</p>"""

        except Exception as e:
            error_message = f"Error in generate_status_html: {str(e)}"
            self.logger.error(error_message)

    def generate_description_html(self, title):
        """Генерирует HTML для отображения описания, если оно есть."""
        try:
            if title.description:
                return f"""<p>Описание: {title.description}</p>"""
            else:
                return ""
        except Exception as e:
            error_message = f"Error in generate_description_html: {str(e)}"
            self.logger.error(error_message)

    def generate_year_html(self, title, show_text_list=False):
        """Генерирует HTML для отображения года выпуска."""
        try:
            title_year = title.season_year if title.season_year else "Год отсутствует"
            if show_text_list:
                return f"""{title_year}"""
            else:
                return f"""<p>Год выпуска: {title_year}</p>"""
        except Exception as e:
            error_message = f"Error in generate_year_html: {str(e)}"
            self.logger.error(error_message)

    def generate_type_html(self, title):
        """Генерирует HTML для отображения типа аниме."""
        try:
            title_type = title.type_full_string if title.type_full_string else ""
            return f"""<p>{title_type}</p>"""
        except Exception as e:
            error_message = f"Error in generate_type_html: {str(e)}"
            self.logger.error(error_message)

    def generate_episodes_html(self, title):
        """Генерирует HTML для отображения информации об эпизодах на основе выбранного качества."""
        try:
            selected_quality = self.app.quality_dropdown.currentText()
            self.app.discovered_links = []
            self.app.sanitized_titles = []
            # TODO: fix blank space
            blank_space = self.blank_spase
            episode_ids = []
            episode_links = []
            for i, episode in enumerate(title.episodes):
                episode_name = episode.name if episode.name else f'Серия {i + 1}'
                link = None
                if selected_quality == 'fhd':
                    link = episode.hls_fhd
                elif selected_quality == 'hd':
                    link = episode.hls_hd
                elif selected_quality == 'sd':
                    link = episode.hls_sd
                else:
                    self.logger.error(f"Неизвестное качество: {selected_quality}")
                    continue
                if link:
                    episode_ids.append(episode.episode_id)
                    episode_links.append((episode.episode_id, episode_name, link))
                else:
                    self.logger.warning(
                        f"Нет ссылки для эпизода '{episode_name}' для выбранного качества '{selected_quality}'")
            watch_all_episodes_html = self.generate_watch_all_episodes_html(title.title_id, episode_ids)
            play_all_html = self.generate_play_all_html(title)
            if episode_links:
                episodes_html = f'<p class="header_episodes">{watch_all_episodes_html}{blank_space * 4}Episodes:{blank_space * 6}{play_all_html}</p><ul>'
                for episode_id, episode_name, link in episode_links:
                    watched_html = self.generate_watch_history_html(title.title_id, episode_id=episode_id)
                    episodes_html += f'<p class="episodes">{watched_html}{blank_space * 4}<a href="{link}" target="_blank">{episode_name}</a></p>'
                    self.app.discovered_links.append(link)
            else:
                episodes_html = f'<p class="header_episodes">Episodes:{blank_space * 6}{play_all_html}</p><ul>'
                episodes_html += f'<li>Нет доступных ссылок для выбранного качества: {selected_quality}</li>'
            episodes_html += "</ul>"
            # Добавляем имя эпизода в sanitized_titles
            sanitized_name = self.app.sanitize_filename(title.code)
            self.app.sanitized_titles.append(sanitized_name)
            # Обновляем плейлисты, если есть обнаруженные ссылки
            if self.app.discovered_links:
                self.app.playlists[title.title_id] = {
                    'links': self.app.discovered_links,
                    'sanitized_title': sanitized_name
                }
            self.logger.debug(f"discovered_links: {len(self.app.discovered_links)}")
            self.logger.debug(f"sanitized_name: {sanitized_name}")
            return episodes_html
        except Exception as e:
            error_message = f"Error in generate_episodes_html: {str(e)}"
            self.logger.error(error_message)



