# app_handlers.py
import ast
import base64
from urllib.parse import urlparse, parse_qs, unquote
from PyQt5.QtCore import QTimer

from providers.animedia.v0.cache_manager import AniMediaCacheManager


class LinkActionHandler:
    def __init__(self,
                 logger,
                 db_manager,
                 animedia_cache: AniMediaCacheManager,
                 titles_list_batch_size,
                 display_info,
                 display_titles,
                 play_link,
                 play_playlist_wrapper,
                 save_torrent_wrapper,
                 reset_offset,
                 get_search_by_title_animedia):

        self.logger = logger
        self.db_manager = db_manager
        self.titles_list_batch_size = titles_list_batch_size
        self.display_info = display_info
        self.display_titles = display_titles
        self.play_link = play_link
        self.play_playlist_wrapper = play_playlist_wrapper
        self.save_torrent_wrapper = save_torrent_wrapper
        self.reset_offset = reset_offset
        self.get_search_by_title_animedia = get_search_by_title_animedia

        self.animedia_cache = animedia_cache

        self.dispatch = {
            'display_info': self._handle_display_info,
            'am_search': self._handle_am_search,
            'filter_by_franchise': self._handle_filter_by_franchise,
            'filter_by_genre': self._handle_filter_by_genre,
            'filter_by_team_member': self._handle_filter_by_team_member,
            'filter_by_year': self._handle_filter_by_year,
            'filter_by_status': self._handle_filter_by_status,
            'filter_by_provider': self._handle_filter_by_provider,
            'reload_template': self._handle_reload_template,
            'reset_offset': self._handle_reset_offset,
            'reload_info': self._handle_display_info,
            'set_download_status': self._handle_set_download_status,
            'set_need_to_see': self._handle_set_need_to_see,
            'set_watch_status': self._handle_set_watch_status,
            'set_watch_all_episodes_status': self._handle_set_watch_all_episodes_status,
            'set_rating': self._handle_set_rating,
            'play_all': self._handle_play_all,
            'play_m3u8': self._handle_play_m3u8,
            'download_torrent': self._handle_torrent_download
        }

    def handle(self, link):
        try:
            parts = link.split('/')
            action = parts[0]

            handler = self.dispatch.get(action)
            if handler:
                return handler(parts)
            else:
                self.logger.error(f"Unknown link type: {link}")
                return None
        except Exception as e:
            self.logger.error(f"Error handling link: {e}")
            return None

    def _handle_torrent_download(self, parts):
        """
        Обрабатывает ссылки на скачивание торрентов.

        Формат ссылки:
        download_torrent/9978/35565/tougen-anki?link=/api/v1/anime/torrents/{hash}/file

        parts = ['download_torrent', '9978', '35565', 'tougen-anki?link=/api/v1/...']

        ИСПРАВЛЕНО:
        1. Правильный парсинг parts (это list, а не строка)
        2. Корректная обработка URL с query параметрами
        """
        try:
            if len(parts) < 4:
                self.logger.error(f"Invalid torrent link structure: {parts}")
                return

            title_id = int(parts[1])
            torrent_id = int(parts[2])
            last_part = parts[3] if len(parts) == 4 else '/'.join(parts[3:])

            if '?' not in last_part:
                self.logger.error(f"No query parameters in link: {last_part}")
                return

            title_code, query_string = last_part.split('?', 1)
            query_params = parse_qs(query_string)

            if 'link' not in query_params:
                self.logger.error(f"No 'link' parameter in query: {query_string}")
                return

            torrent_link = unquote(query_params['link'][0])

            if not torrent_link:
                self.logger.error(f"Empty torrent link for title_id={title_id}")
                return

            self.logger.info(f"Downloading torrent: title_id={title_id}, torrent_id={torrent_id}")
            self.logger.debug(f"Torrent URL: {torrent_link}")
            self.save_torrent_wrapper(torrent_link, title_code, torrent_id)
            QTimer.singleShot(100, lambda: self.display_info(title_id))

        except ValueError as e:
            self.logger.error(f"Invalid numeric value in torrent link: {e}")
        except Exception as e:
            self.logger.error(f"Error handling torrent download: {e}", exc_info=True)

    def _handle_display_info(self, parts):
        title_id = int(parts[1])
        QTimer.singleShot(100, lambda: self.display_info(title_id))

    def _handle_am_search(self, parts):
        title = str(parts[1])
        original_id = str(parts[2])
        self.animedia_cache.invalidate_item(self.animedia_cache.cfg.vlink_key, original_id)
        QTimer.singleShot(100, lambda: self.get_search_by_title_animedia(title))

    def _handle_filter_by_franchise(self, parts):
        title_ids = ast.literal_eval(parts[1])
        self.logger.debug(f"Filtering by franchise for title_ids: {title_ids}")
        QTimer.singleShot(100, lambda: self.display_titles(title_ids=title_ids))

    def _handle_filter_by_genre(self, parts):
        genre_id = parts[1]
        self.logger.debug(f"Filtering by genre: {genre_id}")
        title_ids = self.db_manager.get_titles_by_genre(genre_id)
        if title_ids:
            QTimer.singleShot(100, lambda: self.display_titles(
                show_mode='titles_genre_list',
                batch_size=self.titles_list_batch_size,
                title_ids=title_ids
            ))
        else:
            self.logger.warning(f"No titles found with genre: '{genre_id}'")

    def _handle_filter_by_team_member(self, parts):
        team_member = parts[1]
        self.logger.debug(f"Filtering by team_member: {team_member}")
        title_ids = self.db_manager.get_titles_by_team_member(team_member)
        if title_ids:
            QTimer.singleShot(100, lambda: self.display_titles(show_mode='titles_team_member_list',
                                                               batch_size=self.titles_list_batch_size,
                                                               title_ids=title_ids))
        else:
            self.logger.warning(f"No titles found with team_member: '{team_member}'")

    def _handle_filter_by_year(self, parts):
        year = int(parts[1])
        self.logger.debug(f"Filtering by year: {year}")
        title_ids = self.db_manager.get_titles_by_year(year)
        if title_ids:
            QTimer.singleShot(100, lambda: self.display_titles(show_mode='titles_year_list',
                                                               batch_size=self.titles_list_batch_size,
                                                               title_ids=title_ids))
        else:
            self.logger.warning(f"No titles found with year: '{year}'")
    def _handle_filter_by_status(self, parts):
        status_code = int(parts[1])
        self.logger.debug(f"Filtering by status: {status_code}, type: {type(status_code)}")
        title_ids = self.db_manager.get_titles_by_status(status_code)
        self.logger.debug(f"Query returned {len(title_ids)} titles: {title_ids[:5] if title_ids else []}")
        if title_ids:
            QTimer.singleShot(100, lambda: self.display_titles(show_mode='titles_status_list',
                                                               batch_size=self.titles_list_batch_size,
                                                               title_ids=title_ids))
        else:
            self.logger.warning(f"No titles found with status: '{status_code}'")
    def _handle_filter_by_provider(self, parts):
        provider_code = parts[1]
        self.logger.debug(f"Filtering by provider: {provider_code}")
        title_ids = self.db_manager.get_title_ids_by_provider(provider_code)
        self.logger.debug(f"Query returned {len(title_ids)} titles: {title_ids[:5] if title_ids else []}")
        if title_ids:
            QTimer.singleShot(100, lambda: self.display_titles(show_mode='titles_provider_list',
                                                               batch_size=self.titles_list_batch_size,
                                                               title_ids=title_ids))
        else:
            self.logger.warning(f"No titles found with provider: '{provider_code}'")

    def _handle_reload_template(self, parts):
        template_name = parts[1]
        self.db_manager.save_template(template_name)
        QTimer.singleShot(100, lambda: self.display_titles(start=True))

    def _handle_reset_offset(self, parts):
        reset_status = parts[1]
        if reset_status:
            self.reset_offset()
            QTimer.singleShot(100, lambda: self.display_titles(start=True))

    def _handle_set_download_status(self, parts):
        if len(parts) >= 4:
            user_id = int(parts[1])
            title_id = int(parts[2])
            torrent_id = int(parts[3]) if len(parts) > 3 and parts[3] != 'None' else None
            self.logger.debug(
                f"Setting user:{user_id} download status for title_id, torrent_id: {title_id}, {torrent_id}")
            _, current_download_status = self.db_manager.get_history_status(user_id=user_id, title_id=title_id,
                                                                            torrent_id=torrent_id)
            new_download_status = not current_download_status
            self.logger.debug(
                f"Setting download status for user_id: {user_id}, title_id: {title_id}, torrent_id: {torrent_id}, status: {new_download_status}")
            self.db_manager.save_watch_status(user_id=user_id, title_id=title_id, torrent_id=torrent_id,
                                              is_download=new_download_status)
            QTimer.singleShot(100, lambda: self.display_info(title_id))
        else:
            self.logger.error(f"Invalid set_download_status/ link structure: {parts}")

    def _handle_set_need_to_see(self, parts):
        if len(parts) >= 3:
            user_id = int(parts[1])
            title_id = int(parts[2])
            self.logger.debug(f"Setting user:{user_id} need to see status for title_id: {title_id}")
            current_status = self.db_manager.get_need_to_see(user_id=user_id, title_id=title_id)
            new_watch_status = not current_status
            self.logger.debug(
                f"Setting watch status for user_id: {user_id}, title_id: {title_id}, status: {new_watch_status}")
            self.db_manager.save_need_to_see(user_id=user_id, title_id=title_id, need_to_see=new_watch_status)
            QTimer.singleShot(100, lambda: self.display_info(title_id))
        else:
            self.logger.error(f"Invalid set_need_to_see/ link structure: {parts}")

    def _handle_set_watch_status(self, parts):
        if len(parts) >= 4:
            user_id = int(parts[1])
            title_id = int(parts[2])
            episode_id = int(parts[3]) if len(parts) > 3 and parts[3] != 'None' else None
            self.logger.debug(f"Setting user:{user_id} watch status for title_id, episode_id: {title_id}, {episode_id}")
            current_status = self.db_manager.get_history_status(user_id=user_id, title_id=title_id,
                                                                episode_id=episode_id)
            current_watched_status, _ = current_status
            new_watch_status = not current_watched_status
            self.logger.debug(
                f"Setting watch status for user_id: {user_id}, title_id: {title_id}, episode_id: {episode_id}, status: {new_watch_status}")
            self.db_manager.save_watch_status(user_id=user_id, title_id=title_id, episode_id=episode_id,
                                              is_watched=new_watch_status)
            QTimer.singleShot(100, lambda: self.display_info(title_id))
        else:
            self.logger.error(f"Invalid set_watch_status/ link structure: {parts}")

    def _handle_set_watch_all_episodes_status(self, parts):
        if len(parts) >= 4:
            user_id = int(parts[1])
            title_id = int(parts[2])
            episode_ids = ast.literal_eval(parts[3])
            if not isinstance(episode_ids, list):
                raise ValueError("Invalid episode_ids, expected a list.")
            self.logger.debug(f"Setting user:{user_id} watch status for title_id, all_episodes: {title_id}")
            current_watched_status = self.db_manager.get_all_episodes_watched_status(user_id=user_id, title_id=title_id)
            new_watch_status = not current_watched_status
            self.logger.debug(
                f"Setting watch status for user_id: {user_id}, title_id: {title_id} all_episodes status: {new_watch_status}")
            self.db_manager.save_watch_all_episodes(user_id, title_id, is_watched=new_watch_status,
                                                    episode_ids=episode_ids)
            QTimer.singleShot(100, lambda: self.display_info(title_id))
        else:
            self.logger.error(f"Invalid set_watch_all_episodes_status/ link structure: {parts}")

    def _handle_set_rating(self, parts):
        if len(parts) >= 4:
            title_id = int(parts[1])
            rating_name = str(parts[2])
            rating_value = int(parts[3])
            self.logger.debug(f"Setting rating for title_id: {title_id}, rating: {rating_name}:{rating_value}")
            self.db_manager.save_ratings(title_id, rating_name=rating_name, rating_value=rating_value)
            QTimer.singleShot(100, lambda: self.display_info(title_id))
        else:
            self.logger.error(f"Invalid set_rating/ link structure: {parts}")

    def _handle_play_all(self, parts):
        if len(parts) >= 4:
            title_id = int(parts[1])
            filename = parts[2]
            skip_data = parts[3].strip("[]")

            self.logger.debug(f"Play_all: title_id: {title_id}, Skip data base64: {skip_data}, filename: {filename}")
            self.play_playlist_wrapper(filename, title_id, skip_data)
            QTimer.singleShot(100, lambda: self.display_info(title_id))
        else:
            self.logger.error(f"Invalid play_all link structure: {parts}")

    def _handle_play_m3u8(self, parts):
        if len(parts) >= 4:
            try:
                title_id = int(parts[1])
                skip_data = parts[2].strip("[]")
                extracted_link = parts[3].strip("[]")
                decoded_link = base64.urlsafe_b64decode(extracted_link).decode()
                self.logger.debug(
                    f"Skip data base64: {skip_data}, Extracted link: {extracted_link}, Decoded link: {decoded_link}")
                link = decoded_link
                self.logger.info(f"Sending video link: {link} to VLC")
                self.play_link(link, title_id, skip_data)
                QTimer.singleShot(100, lambda: self.display_info(title_id))
            except (ValueError, SyntaxError) as e:
                self.logger.error(f"Error parsing: {e}")
        else:
            self.logger.error(f"Invalid play_m3u8 link structure: {parts}")