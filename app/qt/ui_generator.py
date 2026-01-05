# ui_generator.py
import html
import json
import base64
import logging
import re
from urllib.parse import quote

from PyQt6.QtWidgets import QHBoxLayout
# from PyQt6.QtGui import QPixmap
# from PyQt6.QtCore import QByteArray, QBuffer
from app.qt.app_helpers import TitleBrowserFactory, TitleHtmlFactory
from utils.media.image_manager import guess_mime, convert_image


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
        self.rating_name = self.app.default_rating_name
        self.max_rating = 6

    def create_title_browser(self, title, show_mode='default'):
        """Создает элемент интерфейса для отображения информации о тайтле."""
        try:
            self.logger.debug("Начинаем создание title_browser...")

            if show_mode == 'one_title':
                self.logger.debug(f"Создаем title_browser для title_id: {title.title_id}")
                title_layout = QHBoxLayout()

                poster_label = self.title_browser_factory.create_poster_widget(title.title_id)
                title_layout.addWidget(poster_label)

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

    def generate_provider_html(self, title_id):
        """Generates HTML to display provider"""
        try:
            provider = self.db_manager.get_provider_by_title_id(title_id)
            provider_link = provider.lower()
            html = f'<span class="decorate_name">{provider}<span>'
            html_link = f'{self.blank_spase}<a href="filter_by_provider/{provider_link}" title="Filter by Provider">{html}</a>{self.blank_spase}'
            return html_link
        except Exception as e:
            error_message = f"Error in generate_provider_html: {str(e)}"
            self.logger.error(error_message)
            return ""

    def generate_studio_html(self, title_id):
        """Generates HTML to display studio"""
        try:
            # TODO: Add filtering here
            studio = self.db_manager.get_studio_by_title_id(title_id)
            if studio:
                html = f'<p>Студия: {studio}{self.blank_spase}</p>'
            else:
                html = f''
            return html
        except Exception as e:
            error_message = f"Error in generate_studio_html: {str(e)}"
            self.logger.error(error_message)
            return ""

    def generate_reload_button_html(self, title_id):
        """Generates HTML to display reload button"""
        try:
            image_html = f"""🔄"""
            # TODO: fix blank spase
            blank_spase = self.blank_spase
            reload_link = f'<a href="reload_info/{title_id}" title="Reload title">{image_html}</a>{blank_spase * 4}'
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
            rating_icons = []
            image_html_full = f"""★"""
            image_html_blank = f"""☆"""
            if ratings:
                rating_name = ratings.rating_name
                rating_value = ratings.rating_value
                for i in range(self.max_rating):
                    if i < rating_value:
                        rating_icons.append(
                            f'<a href="set_rating/{title.title_id}/{rating_name}/{i + 1}" title="Set rating">{image_html_full}</a>')
                    else:
                        rating_icons.append(
                            f'<a href="set_rating/{title.title_id}/{rating_name}/{i + 1}" title="Set rating">{image_html_blank}</a>')
            else:
                rating_name = self.rating_name
                for i in range(self.max_rating):
                    rating_icons.append(
                        f'<a href="set_rating/{title.title_id}/{rating_name}/{i + 1}" title="Set rating">{image_html_blank}</a>')

            # TODO: fix blank spase
            blank_spase = self.blank_spase
            rating_value = ''.join(rating_icons)
            watch_html = self.generate_watch_history_html(title.title_id)
            need_to_see_html = self.generate_need_to_see_html(title.title_id)
            rating_name_html = f'<a href="set_rating/{title.title_id}/{rating_name}/0" title="Reset rating">{rating_name}</a>'
            rating_html = f'{watch_html}{blank_spase}{title.title_id}{blank_spase}{need_to_see_html}{blank_spase * 2}{rating_name_html}:{blank_spase}{rating_value}'
            return rating_html
        except Exception as e:
            error_message = f"Error in generate_rating_html: {str(e)}"
            self.logger.error(error_message)
            return ""

    def generate_download_history_html(self, title_id, torrent_id):
        """Generates HTML to display download history"""
        try:
            image_html_green = self._icon("diamond", True)
            image_html_red = self._icon("diamond", False)

            # TODO: fix it later
            user_id = self.app.user_id

            if torrent_id:
                _, is_download = self.db_manager.get_history_status(user_id, title_id, torrent_id=torrent_id)
                self.logger.debug(
                    f"user_id/title_id/torrent_id: {user_id}/{title_id}/{torrent_id} Status: {bool(is_download)}")
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
            image_html_green = self._icon("square", True)
            image_html_red = self._icon("square", False)

            # TODO: fix it later
            user_id = self.app.user_id

            all_watched = self.db_manager.get_all_episodes_watched_status(user_id, title_id)
            self.logger.debug(f"user_id/title_id/episode_ids: {user_id}/{title_id}/{len(episode_ids)} Status: {bool(all_watched)}")
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
            image_html_green = self._icon("circle", True)
            image_html_red = self._icon("circle", False)

            # TODO: fix it later
            user_id = self.app.user_id

            if title_id:
                is_need_to_see = self.db_manager.get_need_to_see(user_id, title_id)
                self.logger.debug(f"user_id/title_id : {user_id}/{title_id} Status: {bool(is_need_to_see)}")
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
            image_html_green = self._icon("square", True)
            image_html_red = self._icon("square", False)

            # TODO: fix it later
            user_id = self.app.user_id

            if episode_id or title_id:
                is_watched, _ = self.db_manager.get_history_status(user_id, title_id, episode_id=episode_id)
                self.logger.debug(f"user_id/title_id/episode_id: {user_id}/{title_id}/{episode_id} Status: {bool(is_watched)}")
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
                torrent_quality_type = torrent.quality_type if torrent.quality_type else "Unknown Quality Type"
                torrent_quality = torrent.quality if torrent.quality else "Unknown Quality"
                torrent_encoder = torrent.encoder if torrent.encoder else "Unknown Encoder"
                torrent_episodes_range = torrent.episodes_range if torrent.episodes_range else "Unknown Episodes Range"
                torrent_size = torrent.size_string if torrent.size_string else "Unknown Size"
                download_html = self.generate_download_history_html(title.title_id, torrent.torrent_id)
                if torrent.url:
                    torrent_link_html = f'<a href="download_torrent/{title.title_id}/{torrent.torrent_id}/{title.code}?link={quote(torrent.url)}" title="Download torrent file">{torrent_quality_type}{blank_spase}{torrent_quality}{blank_spase}{torrent_encoder}{blank_spase}{torrent_episodes_range}{blank_spase}({torrent_size})</a>'
                else:
                    torrent_link_html = f'<a href="download_torrent/{title.title_id}/{torrent.torrent_id}/{title.code}" title="Download torrent file">{torrent_quality_type}{blank_spase}{torrent_quality}{blank_spase}{torrent_encoder}{blank_spase}{torrent_episodes_range}{blank_spase}({torrent_size})</a>'
                torrents_html += f'<li>{torrent_link_html}{blank_spase * 2}{download_html}</li>'
            torrents_html += "</ul>"

            return torrents_html
        except Exception as e:
            error_message = f"Error in generate_torrents_html: {str(e)}"
            self.logger.error(error_message)
            return ""

    def generate_reload_poster_html(self, title):
        try:
            title_id = title.title_id
            poster_size_key = "original"
            reload_poster_href = f"""reload_poster/{title_id}/{poster_size_key}"""
            text = f"""<span class="decorate_name">RELOAD POSTER<span>"""
            reload_poster_html = f'{self.blank_spase}<a href="{reload_poster_href}" title="Reload poster">{text}</a>{self.blank_spase*15}'
            return reload_poster_html
        except Exception as e:
            tid = getattr(title, "title_id", "?")
            self.logger.error(f"Error processing poster for title_id: {tid} - {e}", exc_info=True)
            return ""

    def generate_poster_html(
            self,
            title,
            need_image: bool = False,
            need_background: bool = False,
            need_placeholder: bool = False,
    ) -> str:
        """Generates HTML/CSS for poster using data-url. WEBP -> PNG fallback for Qt5."""
        try:
            if need_placeholder:
                title_id = 2
                alt = "placeholder"
            else:
                title_id = getattr(title, "title_id", None)
                if not title_id:
                    return ""
                code = getattr(title, "code", "") or ""
                alt = f"{title_id}.{code}"

            size_key = "original"
            blob = self.app.get_poster_or_placeholder(title_id, size_key=size_key)
            if not blob:
                return ""
            mime = guess_mime(blob) or "application/octet-stream"
            if "webp" in mime.lower():
                converted = convert_image(blob)  # bytes PNG
                if not converted:
                    return ""
                blob = converted
                mime = "image/png"
            b64 = base64.b64encode(blob).decode("ascii")
            data_url = f"data:{mime};base64,{b64}"
            if need_image:
                return (
                    f'<img src="{data_url}" '
                    f'alt="{html.escape(alt)}" '
                    f'style="float:left; margin-right:20px;" />'
                )
            if need_background:
                return f'background-image: url("{data_url}");'
            return ""
        except Exception as e:
            tid = getattr(title, "title_id", "?")
            self.logger.error(f"Error processing poster for title_id: {tid} - {e}", exc_info=True)
            return ""

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
                    role_translation = {
                        'voice': 'Озвучка',
                        'translator': 'Перевод',
                        'timing': 'Тайминг'
                    }

                    team_roles_html = []
                    for role, members_json in team_data.items():
                        members = json.loads(members_json)
                        if members:
                            linked_members = [
                                f'<a href="filter_by_team_member/{member}" title="Filter by team member">{member}</a>'
                                for member in members
                            ]

                            role_html = f"{role_translation.get(role, role.capitalize())}: {', '.join(linked_members)}"
                            team_roles_html.append(role_html)

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
            day_name = getattr(title, 'day_name', None)
            if not day_name:
                return ""
            return f'<span class="decorate_name">{self.blank_spase}{day_name}{self.blank_spase}</span>'
        except Exception as e:
            self.logger.error(f"Error in generate_day_of_week_html: {e}")
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
                name = (episode.name or "").strip()
                num = episode.episode_number

                if not name:
                    episode_name = f"Серия {num}"
                elif re.search(r'\b(серия|episode)\b', name, re.IGNORECASE):
                    episode_name = name
                else:
                    episode_name = f"{num}. {name}"
                skip_opening = episode.skips_opening if episode.skips_opening else []
                skip_ending = episode.skips_ending if episode.skips_ending else []

                episode_skip_data = {
                    "episode_number": episode.episode_number,
                    "skip_opening": skip_opening,
                    "skip_ending": skip_ending
                }

                global_skip_data["episode_skips"].append(episode_skip_data)

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
                    episode_links.append((episode.episode_id, episode_name, link, episode_skip_data_encoded))
                else:
                    self.logger.warning(
                        f"Нет ссылки для эпизода '{episode_name}' для выбранного качества '{selected_quality}'"
                    )

            watch_all_episodes_html = self.generate_watch_all_episodes_html(title.title_id, episode_ids)

            if episode_links:
                episodes_html = (
                    f'<p class="header_episodes">{watch_all_episodes_html}{blank_space * 2}'
                    f'Episodes:{blank_space * 4}{play_all_html}</p><ul>'
                )

                for episode_id, episode_name, link, episode_skip_data_encoded in episode_links:
                    watched_html = self.generate_watch_history_html(title.title_id, episode_id=episode_id)
                    link_encoded = base64.urlsafe_b64encode(link.encode()).decode()
                    # Передаём в URL именно данные пропусков для этого эпизода

                    link_lower = (link or "").lower()
                    if ".m3u8" in link_lower:
                        action = "play_m3u8"
                    else:
                        action = "open_web"

                    episodes_html += (
                        f'<p class="episodes">{watched_html}{blank_space * 2}'
                        f'<a href="{action}/{title.title_id}/[{episode_skip_data_encoded}]/[{link_encoded}]" '
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
                    'links': list(self.app.discovered_links),
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
        """Generates Playlist link -
        M3U with encoded skip data,
        URL as is.
        """
        try:
            self.app.stream_video_url = title.host_for_player
            playlist = self.app.ensure_playlist_bundle(title.title_id)
            if not playlist:
                return "No playlist available"

            links = []

            streams_file = playlist.get("streams_file")
            web_file = playlist.get("web_file")
            streams_count = int(playlist.get("streams_count") or 0)
            web_count = int(playlist.get("web_count") or 0)

            if streams_file and streams_count > 0:
                links.append(
                    f'<a href="play_all/{title.title_id}/{streams_file}/[{skip_data_encoded}]" '
                    f'title="Watch all episodes">Play all</a>'
                )

            if web_file and web_count > 0:
                links.append(
                    f'<a href="play_all/{title.title_id}/{web_file}/[{skip_data_encoded}]" '
                    f'title="Open player pages">Open web</a>'
                )

            return " / ".join(links) if links else "No playlist available"

        except Exception as e:
            self.logger.error(f"Error in generate_play_all_html: {str(e)}")
            return ""

    def _icon(self, shape: str, active: bool) -> str:
        if shape == "square":
            ch = "ø" if active else "o"
        elif shape == "circle":
            ch = "☑" if active else "✎"
        elif shape == "diamond":
            ch = "◆" if active else "◇"
        else:
            ch = "☀" if active else "☼"

        return (
            f"<span style='"
            f"display:inline-block;"
            f"width:1.3em;"
            f"text-align:center;"
            f"font-size:16pt;"
            f"line-height:1;"
            f"font-family: Segoe UI, Arial, sans-serif;"
            f"color:#000;"
            f"text-decoration:none;"
            f"vertical-align:middle;"
            f"'>"
            f"{ch}</span>"
        )
