# ui_generator.py
import json
import base64
import logging

from PyQt5.QtWidgets import QHBoxLayout
from PyQt5.QtGui import QPixmap
from PyQt5.QtCore import QByteArray, QBuffer
from app.qt.app_helpers import TitleBrowserFactory, TitleHtmlFactory


class UIGenerator:
    def __init__(self, app, db_manager, template_name):
        self.logger = logging.getLogger(__name__)
        self.app = app
        self.db_manager = db_manager
        self.current_template = template_name
        self.title_html_factory = TitleHtmlFactory(app, self.current_template)
        self.title_browser_factory = TitleBrowserFactory(app)
        self.blank_spase = '&nbsp;'
        # TODO: fix this rating system
        self.rating_name = 'CMERS'
        self.max_rating = 6

    def create_title_browser(self, title, show_mode='default'):
        """Создает элемент интерфейса для отображения информации о тайтле."""
        try:
            self.logger.debug("Начинаем создание title_browser...")

            if show_mode == 'one_title':
                self.logger.debug(f"Создаем title_browser для title_id: {title.title_id}")
                title_layout = QHBoxLayout()

                # Используем фабрику для создания постера
                poster_label = self.title_browser_factory.create_poster_widget(title.title_id)
                title_layout.addWidget(poster_label)

                # Создаем виджет title_browser
                title_browser = self.title_browser_factory.create_title_browser_widget(title, 'one_title')
                title_layout.addWidget(title_browser)

                return title_layout
            else:
                return self.title_browser_factory.create_title_browser_widget(title, show_mode)

        except Exception as e:
            error_message = f"Error in create_title_browser: {str(e)}"
            self.logger.error(error_message)
            return None

    def get_title_html(self, title, show_mode='default'):
        """Генерирует HTML для отображения информации о тайтле, используя фабрику HTML.
        """
        return self.title_html_factory.generate_html(title, show_mode)

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

    def generate_reload_button_html(self, title_id):
        """Generates HTML to display reload button"""
        try:
            # TODO: remove unused logic
            # image_base64 = self.prepare_generate_poster_html(7)
            # image_html = f'<img src="data:image/png;base64,{image_base64}" />'
            image_html = f"""🔄"""
            # TODO: fix blank spase
            blank_spase = self.blank_spase
            # TODO: remove unused logic
            # if image not symbol
            # reload_link = f'<a href="reload_info/{title_id}" title="Reload title">{image_html}</a>{blank_spase * 16}'
            reload_link = f'<a href="reload_info/{title_id}" title="Reload title">{image_html}</a>{blank_spase * 6}'
            return reload_link
        except Exception as e:
            error_message = f"Error in generate_reload_button_html: {str(e)}"
            self.logger.error(error_message)
            return ""

    def generate_show_more_html(self, title_id):
        """Generates HTML to display 'show more' link"""
        try:
            return f'<a href=display_info/{title_id}>Подробнее</a>'
        except Exception as e:
            error_message = f"Error in generate_show_more_html: {str(e)}"
            self.logger.error(error_message)
            return ""

    def generate_rating_html(self, title):
        """Generates HTML to display ratings and allows updating"""
        try:
            ratings = self.db_manager.get_rating_from_db(title.title_id)
            rating_star_images = []
            # TODO: remove unused logic
            # poster_base64_full = self.prepare_generate_poster_html(4)
            # poster_base64_blank = self.prepare_generate_poster_html(3)
            # image_html_full = f'<img src="data:image/png;base64,{poster_base64_full}" />'
            # image_html_blank = f'<img src="data:image/png;base64,{poster_base64_blank}" />'
            image_html_full = f"""★"""
            image_html_blank = f"""☆"""
            if ratings:
                rating_name = ratings.rating_name
                rating_value = ratings.rating_value
                for i in range(self.max_rating):
                    if i < rating_value:
                        rating_star_images.append(
                            f'<a href="set_rating/{title.title_id}/{rating_name}/{i + 1}" title="Set rating">{image_html_full}</a>')
                    else:
                        rating_star_images.append(
                            f'<a href="set_rating/{title.title_id}/{rating_name}/{i + 1}" title="Set rating">{image_html_blank}</a>')
            else:
                rating_name = self.rating_name
                for i in range(self.max_rating):
                    rating_star_images.append(
                        f'<a href="set_rating/{title.title_id}/{rating_name}/{i + 1}" title="Set rating">{image_html_blank}</a>')

            # TODO: fix blank spase
            blank_spase = self.blank_spase
            rating_value = ''.join(rating_star_images)
            watch_html = self.generate_watch_history_html(title.title_id)
            need_to_see_html = self.generate_need_to_see_html(title.title_id)
            # if image not symbol
            # rating_html = f'{watch_html}{blank_spase}{title.title_id}{blank_spase}{need_to_see_html}{blank_spase * 4}{rating_name}:{blank_spase}{rating_value}'
            rating_html = f'{watch_html}{blank_spase}{title.title_id}{blank_spase}{need_to_see_html}{blank_spase * 2}{rating_name}:{blank_spase}{rating_value}'
            return rating_html
        except Exception as e:
            error_message = f"Error in generate_rating_html: {str(e)}"
            self.logger.error(error_message)
            return ""

    def generate_download_history_html(self, title_id, torrent_id):
        """Generates HTML to display download history"""
        try:
            # TODO: remove unused logic
            # image_base64_green = self.prepare_generate_poster_html(9)
            # image_base64_red = self.prepare_generate_poster_html(8)
            # image_html_green = f'<img src="data:image/png;base64,{image_base64_green}" alt="Set download status" />'
            # image_html_red = f'<img src="data:image/png;base64,{image_base64_red}" alt="Set download status" />'
            image_html_green = f"""◆"""
            image_html_red = f"""◇"""
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
            return ""
        except Exception as e:
            error_message = f"Error in generate_download_history_html: {str(e)}"
            self.logger.error(error_message)
            return ""

    def generate_watch_all_episodes_html(self, title_id, episode_ids):
        """Generates HTML to display watch history"""
        try:
            # TODO: remove unused logic
            # image_base64_watched = self.prepare_generate_poster_html(6)
            # image_base64_blank = self.prepare_generate_poster_html(5)
            # image_html_green = f'<img src="data:image/png;base64,{image_base64_watched}" alt="Set watch all episodes" />'
            # image_html_red = f'<img src="data:image/png;base64,{image_base64_blank}" alt="Set watch all episodes" />'
            image_html_green = f"""🔳"""
            image_html_red = f"""🔲"""
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
            return ""

    def generate_need_to_see_html(self, title_id):
        """Generates HTML to display watch history"""
        try:
            # TODO: remove unused logic
            # image_base64_green = self.prepare_generate_poster_html(11)
            # image_base64_red = self.prepare_generate_poster_html(10)
            # image_html_green = f'<img src="data:image/png;base64,{image_base64_green}" alt="Need to see" />'
            # image_html_red = f'<img src="data:image/png;base64,{image_base64_red}" alt="Need to see" />'
            image_html_green = f"""⚫"""
            image_html_red = f"""⚪"""
            # TODO: fix it later
            user_id = self.app.user_id

            if title_id:
                is_need_to_see = self.db_manager.get_need_to_see(user_id, title_id)
                self.logger.debug(f"user_id/title_id : {user_id}/{title_id} Status:{is_need_to_see}")
                if is_need_to_see:
                    return f'<a href="set_need_to_see/{user_id}/{title_id}" title="Set need to see">{image_html_green}</a>'
                return f'<a href="set_need_to_see/{user_id}/{title_id}" title="Set need to see">{image_html_red}</a>'
            return ""
        except Exception as e:
            error_message = f"Error in generate_nee_to_see_html: {str(e)}"
            self.logger.error(error_message)
            return ""

    def generate_watch_history_html(self, title_id, episode_id=None):
        """Generates HTML to display watch history"""
        try:
            # TODO: remove unused logic
            # image_base64_watched = self.prepare_generate_poster_html(6)
            # image_base64_blank = self.prepare_generate_poster_html(5)
            # image_html_green = f'<img src="data:image/png;base64,{image_base64_watched}" alt="Set watch status" />'
            # image_html_red = f'<img src="data:image/png;base64,{image_base64_blank}" alt="Set watch status" />'
            image_html_green = f"""🔳"""
            image_html_red = f"""🔲"""
            # TODO: fix it later
            user_id = self.app.user_id

            if episode_id or title_id:
                is_watched, _ = self.db_manager.get_history_status(user_id, title_id, episode_id=episode_id)
                self.logger.debug(f"user_id/title_id/episode_id: {user_id}/{title_id}/{episode_id} Status:{is_watched}")
                if is_watched:
                    return f'<a href="set_watch_status/{user_id}/{title_id}/{episode_id}" title="Set watch status">{image_html_green}</a>'
                return f'<a href="set_watch_status/{user_id}/{title_id}/{episode_id}" title="Set watch status">{image_html_red}</a>'
            return ""
        except Exception as e:
            error_message = f"Error in generate_watch_history_html: {str(e)}"
            self.logger.error(error_message)
            return ""

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
                torrent_link_html = f'<a href="{torrent_link}" target="_blank" title="DDownload torrent file">{torrent_quality} ({torrent_size})</a>'
                torrents_html += f'<li>{torrent_link_html}{blank_spase * 4}{download_html}</li>'
                self.app.torrent_data = torrent.title_id, title.code, torrent.torrent_id
            torrents_html += "</ul>"

            return torrents_html
        except Exception as e:
            error_message = f"Error in generate_torrents_html: {str(e)}"
            self.logger.error(error_message)
            return ""

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

            # TODO: fix this return: no static files in production version
            return f"background-image: url('static/background.png');"
        except Exception as e:
            self.logger.error(f"Error processing poster for title_id: {title.title_id} - {e}")
            # TODO: fix this return: no static files in production version
            return f"background-image: url('static/background.png');"

    def generate_genres_html(self, title):
        """Генерирует HTML для отображения жанров с поддержкой кликабельных ссылок."""
        try:
            if hasattr(title, 'genre_names') and title.genre_names and hasattr(title, 'genre_ids') and title.genre_ids:
                try:
                    linked_genres = []
                    for genre_name, genre_id in zip(title.genre_names, title.genre_ids):
                        linked_genres.append(f'<a href="filter_by_genre/{genre_id}" title="Filter by genre">{genre_name}</a>')
                    genres = ', '.join(linked_genres) if linked_genres else "Жанры отсутствуют"
                except Exception as e:
                    self.logger.error(f"Ошибка при генерации HTML жанров: {e}")
                    genres = "Жанры отсутствуют"
            else:
                genres = "Жанры отсутствуют"
            return f"""<p>Жанры: {genres}</p>"""

        except Exception as e:
            error_message = f"Error in generate_genres_html: {str(e)}"
            self.logger.error(error_message)
            return ""

    def generate_team_html(self, title):
        """Генерирует HTML для отображения team_data с поддержкой кликабельных ссылок и разбивкой по ролям."""
        try:
            team_data = self.db_manager.get_team_from_db(title.title_id)
            if team_data:
                try:
                    # Словарь для перевода ролей
                    role_translation = {
                        'voice': 'Озвучка',
                        'translator': 'Перевод',
                        'timing': 'Тайминг'
                    }

                    # Генерируем HTML для каждой роли
                    team_roles_html = []
                    for role, members_json in team_data.items():
                        members = json.loads(members_json)
                        if members:
                            # Создаем кликабельные ссылки для членов команды
                            linked_members = [
                                f'<a href="filter_by_team_member/{member}" title="Filter by team member">{member}</a>'
                                for member in members
                            ]

                            # Формируем строку для каждой роли
                            role_html = f"{role_translation.get(role, role.capitalize())}: {', '.join(linked_members)}"
                            team_roles_html.append(role_html)

                    # Объединяем роли, если есть
                    team_data_html = '<br>'.join(team_roles_html) if team_roles_html else "Данные о команде отсутствуют"
                except Exception as e:
                    self.logger.error(f"Ошибка при генерации HTML команды: {e}")
                    team_data_html = "Данные о команде отсутствуют"
            else:
                team_data_html = "Данные о команде отсутствуют"

            return f"""<p>{team_data_html}</p>"""

        except Exception as e:
            error_message = f"Ошибка в generate_team_html: {str(e)}"
            self.logger.error(error_message)
            return "<p>Ошибка при загрузке данных о команде</p>"

    def generate_announce_html(self, title):
        """Генерирует HTML для отображения анонса."""
        try:
            day_html = self.generate_day_of_week_html(title)

            if hasattr(title, 'announce') and title.announce:
                announce_part = f"{title.announce}"
            else:
                announce_part = ""
            if day_html and announce_part:
                combined_text = f"{day_html}{self.blank_spase}{announce_part}"
            else:
                combined_text = day_html or announce_part

            return f"<p>{combined_text}</p>"

        except Exception as e:
            error_message = f"Error in generate_announce_html: {str(e)}"
            self.logger.error(error_message)
            return ""

    def generate_day_of_week_html(self, title):
        """Генерирует HTML для отображения дня недели тайтла."""
        try:
            day_number = getattr(title, 'day_of_week', None)
            day_part = ""

            try:
                day_number = int(day_number)
            except (ValueError, TypeError):
                self.logger.warning(f"Некорректный номер дня недели: {day_number}")
                return ""

            if day_number is not None:
                days_of_week = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
                if isinstance(day_number, int) and 0 <= day_number < len(days_of_week):
                    day_name = days_of_week[day_number]
                    day_part = f'<span class="day_name">{self.blank_spase}{day_name}{self.blank_spase}</span>'

                return day_part
            else:
                self.logger.warning(f"Некорректный номер дня недели: {day_number}")
                return ""

        except Exception as e:
            error_message = f"Error in generate_day_of_week_html: {str(e)}"
            self.logger.error(error_message)
            return ""

    def generate_status_html(self, title, show_text_list=False):
        """Генерирует HTML для отображения статуса."""
        try:
            title_status = title.status_string if title.status_string else "Статус отсутствует"
            title_code = title.status_code
            status_html = f'<a href="filter_by_status/{title_code}" title="Filter by status">{title_status}</a>'
            if title_code == 1:  # В работе
                status_icon = f"📺"
            elif title_code == 2:  # Завершен
                status_icon = f"🎬"
            else:
                status_icon = ""
            if show_text_list:
                return f"""{status_icon}"""
            else:
                return f"""<p>Статус: {status_html}{status_icon}</p>"""

        except Exception as e:
            error_message = f"Error in generate_status_html: {str(e)}"
            self.logger.error(error_message)
            return ""

    def generate_year_html(self, title, show_text_list=False):
        """Генерирует HTML для отображения года выпуска."""
        try:
            title_year = title.season_year if title.season_year else "Год отсутствует"
            year_html = f'<a href="filter_by_year/{title_year}" title="Filter by year">{title_year}</a>'

            if show_text_list:
                return f"""{year_html}"""
            else:
                return f"""<p>Год выпуска: {year_html}</p>"""
        except Exception as e:
            error_message = f"Error in generate_year_html: {str(e)}"
            self.logger.error(error_message)
            return ""

    def generate_franchise_html(self, title):
        """Генерирует HTML для отображения франшиз, связанных с указанным тайтлом."""
        try:
            franchise_titles = self.db_manager.get_franchises_from_db(title_id=title.title_id)

            if not franchise_titles:
                return ""

            franchise_title_ids = [fr.title_id for fr in franchise_titles]

            filtered_franchises = [fr for fr in franchise_titles if fr.title_id != title.title_id]

            if not filtered_franchises:
                return ""

            franchise_titles_html = (f'<p class="header_p">'
                                     f'<a href="filter_by_franchise/{franchise_title_ids}" '
                                     f'title="Filter by Franchise list">Franchises</a>'
                                     f':{self.blank_spase * 6}</p><ul>')

            for franchise_release in filtered_franchises:
                title_id = franchise_release.title_id
                title_en_name = franchise_release.name_en
                title_ru_name = franchise_release.name_ru

                franchise_titles_html += (
                    f'<li><a href="display_info/{title_id}" '
                    f'title="{title_id}|{title_en_name}|{title_ru_name}">'
                    f'{title_ru_name}</a></li>'
                )
                self.logger.debug(f"display_info/{title_id}/{title_en_name}/{title_ru_name}")

            franchise_titles_html += '</ul>'
            return franchise_titles_html

        except Exception as e:
            error_message = f"Error in generate_franchise_html: {str(e)}"
            self.logger.error(error_message)
            return ""

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
            return ""

    def generate_type_html(self, title):
        """Генерирует HTML для отображения типа аниме."""
        try:
            title_type = title.type_full_string if title.type_full_string else ""
            return f"""<p>{title_type}</p>"""
        except Exception as e:
            error_message = f"Error in generate_type_html: {str(e)}"
            self.logger.error(error_message)
            return ""

    def generate_episodes_html(self, title):
        """Генерирует HTML для отображения информации об эпизодах на основе выбранного качества."""
        try:
            selected_quality = self.app.quality_dropdown.currentText()
            self.app.discovered_links = []
            self.app.sanitized_titles = []
            blank_space = self.blank_spase
            episode_ids = []
            episode_links = []

            # Глобальный набор для play_all, если он вам нужен
            global_skip_data = {"episode_skips": []}
            for episode in title.episodes:
                global_skip_data["episode_skips"].append({
                    "episode_number": episode.episode_number,
                    "skip_opening": episode.skips_opening if episode.skips_opening else [],
                    "skip_ending": episode.skips_ending if episode.skips_ending else []
                })
            global_skip_data_encoded = base64.urlsafe_b64encode(json.dumps(global_skip_data).encode()).decode()
            play_all_html = self.generate_play_all_html(title, global_skip_data_encoded)

            for i, episode in enumerate(title.episodes):
                episode_name = episode.name if episode.name else f'Серия {episode.episode_number}'
                skip_opening = episode.skips_opening if episode.skips_opening else []
                skip_ending = episode.skips_ending if episode.skips_ending else []

                # Собираем данные о пропусках для конкретного эпизода
                episode_skip_data = {
                    "episode_number": episode.episode_number,
                    "skip_opening": skip_opening,
                    "skip_ending": skip_ending
                }
                # Добавляем данные в глобальный набор для возможности «play all»
                global_skip_data["episode_skips"].append(episode_skip_data)

                # Кодируем данные о пропусках для конкретного эпизода
                episode_skip_data_encoded = base64.urlsafe_b64encode(
                    json.dumps(episode_skip_data).encode()
                ).decode()

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
                    # Сохраняем кортеж, где дополнительно передаём закодированные данные пропусков для данного эпизода
                    episode_links.append((episode.episode_id, episode_name, link, episode_skip_data_encoded))
                else:
                    self.logger.warning(
                        f"Нет ссылки для эпизода '{episode_name}' для выбранного качества '{selected_quality}'"
                    )


            watch_all_episodes_html = self.generate_watch_all_episodes_html(title.title_id, episode_ids)

            if episode_links:
                episodes_html = (
                    # TODO: remove unused logic
                    # if image not symbol
                    # f'<p class="header_episodes">{watch_all_episodes_html}{blank_space * 4}'
                    f'<p class="header_episodes">{watch_all_episodes_html}{blank_space * 2}'
                    f'Episodes:{blank_space * 6}{play_all_html}</p><ul>'
                )

                for episode_id, episode_name, link, episode_skip_data_encoded in episode_links:
                    watched_html = self.generate_watch_history_html(title.title_id, episode_id=episode_id)
                    link_encoded = base64.urlsafe_b64encode(link.encode()).decode()
                    # Передаём в URL именно данные пропусков для этого эпизода
                    episodes_html += (
                        # TODO: remove unused logic
                        # if image not symbol
                        # f'<p class="episodes">{watched_html}{blank_space * 4}'
                        f'<p class="episodes">{watched_html}{blank_space * 2}'
                        f'<a href="play_m3u8/{title.title_id}/[{episode_skip_data_encoded}]/[{link_encoded}]" '
                        f'target="_blank" title="Watch episode">{episode_name}</a></p>'
                    )
                    self.logger.debug(f"play_m3u8/{title.title_id}/[{episode_skip_data_encoded}]/[{link_encoded}]")
                    self.app.discovered_links.append(link)
                episodes_html += "</ul>"
            else:
                episodes_html = (
                    f'<p class="header_episodes">Episodes:{blank_space * 6}{play_all_html}</p><ul>'
                    f'<li>Нет доступных ссылок для выбранного качества: {selected_quality}</li></ul>'
                )

            sanitized_name = self.app.sanitize_filename(title.code)
            self.app.sanitized_titles.append(sanitized_name)

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
            return ""

    def generate_play_all_html(self, title, skip_data_encoded):
        """Generates M3U Playlist link with encoded skip data."""
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
                    return f'<a href="play_all/{title.title_id}/{filename}/[{skip_data_encoded}]" title="Watch all episodes">Play all</a>'
                else:
                    self.logger.error(f"No links found for title {sanitized_title}, skipping saving.")
                    return "No playlist available"
            else:
                return "No playlist available"
        except Exception as e:
            error_message = f"Error in generate_play_all_html: {str(e)}"
            self.logger.error(error_message)
            return ""
