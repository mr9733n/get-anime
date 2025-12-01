# process.py
import ast
import json
import logging
from datetime import datetime, timezone


class ProcessManager:
    def __init__(self, save_manager):
        self.logger = logging.getLogger(__name__)
        self.save_manager = save_manager

    def process_titles(self, title_data):
        try:
            title_id = title_data.get('id', None)
            studio_name = title_data.get('studio', '')
            rating_name = title_data.get('rating', {}).get('name', '')
            rating_score = title_data.get("rating", {}).get('score', 0.0)

            if rating_name and rating_score:
                self.save_manager.save_ratings(title_id, rating_name=rating_name, external_value=rating_score)

            if studio_name:
                self.save_manager.save_studio_to_db([title_id], studio_name=studio_name)

            title_data = {
                'title_id': title_data.get('id', None),
                'animedia_id': title_data.get('animedia_id', None),
                'provider': title_data.get('provider'),
                'code': title_data.get('code', ''),
                'name_ru': title_data.get('names', {}).get('ru', ''),
                'name_en': title_data.get('names', {}).get('en', ''),
                'alternative_name': title_data.get('names', {}).get('alternative', ''),
                'title_franchises': json.dumps(title_data.get('franchises', [])),
                'announce': title_data.get('announce', ''),
                'status_string': title_data.get('status', {}).get('string', ''),
                'status_code': title_data.get('status', {}).get('code', None),
                'poster_path_small': title_data.get('posters', {}).get('small', {}).get('url', ''),
                'poster_path_medium': title_data.get('posters', {}).get('medium', {}).get('url', ''),
                'poster_path_original': title_data.get('posters', {}).get('original', {}).get('url', ''),
                'updated': title_data.get('updated', 0) if title_data.get('updated') is not None else 0,
                'last_change': title_data.get('last_change', 0) if title_data.get('last_change') is not None else 0,
                'type_full_string': title_data.get('type', {}).get('full_string', ''),
                'type_code': title_data.get('type', {}).get('code', None),
                'type_string': title_data.get('type', {}).get('string', ''),
                'type_episodes': title_data.get('type', {}).get('episodes', None),
                'type_length': title_data.get('type', {}).get('length', ''),
                'title_genres': json.dumps(title_data.get('genres', [])),
                'team_voice': json.dumps(title_data.get('team', {}).get('voice', [])),
                'team_translator': json.dumps(title_data.get('team', {}).get('translator', [])),
                'team_timing': json.dumps(title_data.get('team', {}).get('timing', [])),
                'season_string': title_data.get('season', {}).get('string', ''),
                'season_code': title_data.get('season', {}).get('code', None),
                'season_year': title_data.get('season', {}).get('year', None),
                'season_week_day': title_data.get('season', {}).get('week_day', None),
                'description': title_data.get('description', ''),
                'in_favorites': title_data.get('in_favorites', 0),
                'blocked_copyrights': title_data.get('blocked', {}).get('copyrights', False),
                'blocked_geoip': title_data.get('blocked', {}).get('geoip', False),
                'blocked_geoip_list': json.dumps(title_data.get('blocked', {}).get('geoip_list', [])),
                'host_for_player': title_data.get('player', {}).get('host', ''),
                'alternative_player': title_data.get('player', {}).get('alternative_player', ''),
                'last_updated': datetime.now(timezone.utc),
            }
            self.logger.debug(f"STATUS INCOMING: code={title_data.get('status', {}).get('code')} "
                              f"str='{title_data.get('status', {}).get('string')}' | id={title_data.get('id')}")
            self.save_manager.save_title(title_data)

            title_id = title_data['title_id']

            # Сохранение данных в связанные таблицы
            self.process_franchises(title_data)

            genres = title_data['title_genres']
            decoded_genres = ast.literal_eval(genres)  # Decode each genre
            self.logger.debug(f"GENRES: {title_id}:{decoded_genres}")
            self.save_manager.save_genre(title_id, decoded_genres)

            # Извлечение данных команды напрямую
            team_data = {
                'voice': title_data['team_voice'],
                'translator': title_data['team_translator'],
                'timing': title_data['team_timing'],
            }
            self.logger.debug(f"TEAM DATA: {title_id}:{team_data}")

            # Проверяем, что данные команды существуют и сохраняем их
            if team_data:
                self.save_manager.save_team_members(title_id, team_data)

            return True
        except Exception as e:
            self.logger.error(f"Failed to save title to database: {e}")
            return False

    def process_episodes(self, title_data):
        try:
            list_data = title_data.get("player", {}).get("list")

            # Проверяем, является ли `list_data` словарем или списком
            if isinstance(list_data, dict):
                episodes = list_data.values()
            elif isinstance(list_data, list):
                episodes = list_data
            else:
                self.logger.error("Unexpected type for list_data in player. Expected dict or list.")
                return False

            for episode in episodes:
                if not isinstance(episode, dict):
                    self.logger.error(f"Invalid type for episode. Expected dict, got {type(episode)}")
                    continue

                if "hls" in episode:
                    try:
                        # self.logger.debug(f"Processing episode: {episode.get('episode')}")

                        created_timestamp = episode.get('created_timestamp')
                        if created_timestamp is not None and isinstance(created_timestamp, (int, float)):
                            created_timestamp = datetime.fromtimestamp(created_timestamp, tz=timezone.utc)
                        else:
                            created_timestamp = datetime.fromtimestamp(0, tz=timezone.utc)

                        episode_data = {
                            'title_id': title_data.get('id', None),
                            'episode_number': episode.get('episode'),
                            'name': episode.get('name', f'Серия {episode.get("episode")}'),
                            'uuid': episode.get('uuid'),
                            'created_timestamp': created_timestamp,
                            'hls_fhd': episode.get('hls', {}).get('fhd'),
                            'hls_hd': episode.get('hls', {}).get('hd'),
                            'hls_sd': episode.get('hls', {}).get('sd'),
                            'preview_path': episode.get('preview'),
                            'skips_opening': json.dumps(episode.get('skips', {}).get('opening', [])),
                            'skips_ending': json.dumps(episode.get('skips', {}).get('ending', []))
                        }

                        self.save_manager.save_episode(episode_data)

                    except Exception as e:
                        self.logger.error(f"Failed to save episode to database: {e}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to save episode to database: {e}")

    def process_franchises(self, title_data):
        franchises_str = title_data['title_franchises']

        try:
            self.logger.debug(f"franchises_str: {len(franchises_str)}")

            # Use json.loads to parse the JSON string
            franchises = json.loads(franchises_str)
        except json.JSONDecodeError as e:
            self.logger.error(
                f"Failed to parse franchises data for title_id: {title_data.get('title_id', 'unknown')}: {e}"
            )
            return

        if franchises:
            for franchise in franchises:
                franchise_data = {
                    'title_id': title_data['title_id'],
                    'franchise_id': franchise.get('franchise', {}).get('id'),
                    'franchise_name': franchise.get('franchise', {}).get('name'),
                    'releases': franchise.get('releases', [])
                }
                self.logger.debug(f"Franchises found for title_id: {title_data['title_id']} : {len(franchise_data)}")
                self.save_manager.save_franchise(franchise_data)

    def process_torrents(self, title_data):
        if "torrents" in title_data and "list" in title_data["torrents"]:
            for torrent in title_data["torrents"]["list"]:
                url = torrent.get("url")
                if url:
                    try:
                        uploaded_timestamp = torrent.get('uploaded_timestamp')
                        if uploaded_timestamp is not None and isinstance(uploaded_timestamp, (int, float)):
                            uploaded_timestamp = datetime.fromtimestamp(uploaded_timestamp, tz=timezone.utc)
                        else:
                            uploaded_timestamp = datetime.fromtimestamp(0, tz=timezone.utc)

                        api_updated_at = torrent.get('updated_at')
                        if api_updated_at is not None and isinstance(api_updated_at, (int, float)):
                            api_updated_at = datetime.fromtimestamp(api_updated_at, tz=timezone.utc)
                        else:
                            api_updated_at = datetime.fromtimestamp(0, tz=timezone.utc)

                        torrent_data = {
                            'torrent_id': torrent.get('torrent_id'),
                            'title_id': title_data.get('id'),
                            'episodes_range': torrent.get('episodes', {}).get('string', 'Неизвестный диапазон'),

                            'quality': torrent.get('quality', {}).get('string', 'Качество не указано'),
                            'quality_type': torrent.get('quality', {}).get('type'),
                            'resolution': torrent.get('quality', {}).get('resolution'),
                            'encoder': torrent.get('quality', {}).get('encoder'),
                            'leechers': torrent.get('leechers'),
                            'seeders': torrent.get('seeders'),
                            'downloads': torrent.get('downloads'),
                            'total_size': torrent.get('total_size'),
                            'size_string': torrent.get('size_string'),
                            'url': torrent.get('url'),
                            'magnet_link': torrent.get('magnet'),
                            'uploaded_timestamp': uploaded_timestamp,
                            'api_updated_at': api_updated_at,
                            'is_in_production': torrent.get('is_in_production'),
                            'label': torrent.get('label'),
                            'filename': torrent.get('filename'),
                            'episodes_total': torrent.get('episodes_total'),
                            'hash': torrent.get('hash'),
                            'torrent_metadata': torrent.get('metadata'),
                            'raw_base64_file': torrent.get('raw_base64_file')
                        }

                        self.save_manager.save_torrent(torrent_data)
                    except Exception as e:
                        self.logger.error(f"Ошибка при сохранении торрента в базе данных: {e}")
        return True
