# process.py
from __future__ import annotations

import re
import ast
import json
import logging
from datetime import datetime, timezone
from dataclasses import dataclass
from typing import Any, Optional


@dataclass(frozen=True)
class SeasonNorm:
    key: str                 # winter/spring/summer/autumn/unknown
    code: Optional[int]      # 1..4 or None
    string: str              # canonical display (e.g. "Spring" or "Весна")
    raw_string: str = ""
    raw_code: Optional[int] = None

    @property
    def is_known(self) -> bool:
        return self.code is not None and self.key != "unknown"


@dataclass(frozen=True)
class SeasonCatalog:
    key_to_code: dict[str, int]
    key_to_en: dict[str, str]
    key_to_ru: dict[str, str]
    aliases: dict[str, str]

    @classmethod
    def default(cls) -> "SeasonCatalog":
        key_to_code = {"winter": 1, "spring": 2, "summer": 3, "autumn": 4}
        key_to_en = {"winter": "Winter", "spring": "Spring", "summer": "Summer", "autumn": "Autumn"}
        key_to_ru = {"winter": "Зима", "spring": "Весна", "summer": "Лето", "autumn": "Осень"}

        aliases = {
            # EN
            "winter": "winter", "win": "winter",
            "spring": "spring", "spr": "spring",
            "summer": "summer", "sum": "summer",
            "autumn": "autumn", "aut": "autumn",
            "fall": "autumn",

            # RU
            "зима": "winter", "зимний": "winter",
            "весна": "spring", "весенний": "spring",
            "лето": "summer", "летний": "summer",
            "осень": "autumn", "осенний": "autumn",
        }
        return cls(key_to_code=key_to_code, key_to_en=key_to_en, key_to_ru=key_to_ru, aliases=aliases)


class ProcessManager:
    def __init__(self, save_manager):
        self.logger = logging.getLogger(__name__)
        self.save_manager = save_manager

    @staticmethod
    def _norm_token(s: str) -> str:
        s = s.strip().lower()
        s = re.sub(r"[\s_\-]+", " ", s)
        return s

    @staticmethod
    def normalize_season(season: Any, *, locale: str = "en", catalog: SeasonCatalog | None = None) -> SeasonNorm:
        """
        season может быть: dict / str / None.
        Понимает numeric code 1..4, рус/англ, регистр, и строки типа "Весна 2024".
        """
        catalog = catalog or SeasonCatalog.default()

        raw_code: Optional[int] = None
        raw_string: str = ""

        if season is None:
            return SeasonNorm(key="unknown", code=None, string="", raw_string="", raw_code=None)

        if isinstance(season, str):
            raw_string = season
        elif isinstance(season, dict):
            raw_code = season.get("code")
            raw_string = season.get("string") or season.get("value") or season.get("description") or ""
        else:
            raw_string = str(season)

        if isinstance(raw_code, int) and raw_code in (1, 2, 3, 4):
            key = {1: "winter", 2: "spring", 3: "summer", 4: "autumn"}[raw_code]
            canon_code = raw_code
        else:
            def _norm_token(s: str) -> str:
                s = s.strip().lower()
                s = re.sub(r"[\s_\-]+", " ", s)
                return s
            t = _norm_token(raw_string)
            key = catalog.aliases.get(t, "unknown")

            if key == "unknown" and t:
                for tok in t.split():
                    key = catalog.aliases.get(tok, "unknown")
                    if key != "unknown":
                        break

            canon_code = catalog.key_to_code.get(key)

        if key == "unknown":
            canon_string = ""
            canon_code = None
        else:
            canon_string = (catalog.key_to_en if locale == "en" else catalog.key_to_ru)[key]

        return SeasonNorm(
            key=key,
            code=canon_code,
            string=canon_string,
            raw_string=raw_string,
            raw_code=raw_code,
        )

    def process_external_data(self, title_id: int, title_data: dict):
        try:
            studio_name = title_data.get('studio_name')
            rating_name = title_data.get('rating_name')
            rating_score = title_data.get('rating_score')

            rating_ok = False
            if rating_name and rating_score:
                self.save_manager.save_ratings(title_id, name_external=rating_name, score_external=rating_score)
                rating_ok = True

            studio_ok = False
            if studio_name:
                self.save_manager.save_studio_to_db([title_id], studio_name=studio_name)
                studio_ok = True

            return rating_ok or studio_ok
        except Exception as e:
            self.logger.error(f"Failed to save external Rating or Studio to database: {e}")
            return False

    def process_titles(self, raw_title_data: dict):
        try:
            season_norm = self.normalize_season(raw_title_data.get("season"), locale="en")
            provider_code = raw_title_data.get('provider')
            external_id = raw_title_data.get('external_id')

            if not provider_code or external_id is None:
                self.logger.error(f"Missing provider or external_id in title data: {raw_title_data.get('id')}")
                return False

            title_fields = {
                'code': raw_title_data.get('code', ''),
                'name_ru': raw_title_data.get('names', {}).get('ru', ''),
                'name_en': raw_title_data.get('names', {}).get('en', ''),
                'alternative_name': raw_title_data.get('names', {}).get('alternative', ''),
                'title_franchises': json.dumps(raw_title_data.get('franchises', [])),
                'announce': raw_title_data.get('announce', ''),
                'status_string': raw_title_data.get('status', {}).get('string', ''),
                'status_code': raw_title_data.get('status', {}).get('code', None),
                'poster_path_small': raw_title_data.get('posters', {}).get('small', {}).get('url', ''),
                'poster_path_medium': raw_title_data.get('posters', {}).get('medium', {}).get('url', ''),
                'poster_path_original': raw_title_data.get('posters', {}).get('original', {}).get('url', ''),
                'updated': raw_title_data.get('updated', 0) or 0,
                'last_change': raw_title_data.get('last_change', 0) or 0,
                'type_full_string': raw_title_data.get('type', {}).get('full_string', ''),
                'type_code': raw_title_data.get('type', {}).get('code', None),
                'type_string': raw_title_data.get('type', {}).get('string', ''),
                'type_episodes': raw_title_data.get('type', {}).get('episodes', None),
                'type_length': raw_title_data.get('type', {}).get('length', ''),
                'title_genres': json.dumps(raw_title_data.get('genres', [])),
                'team_voice': json.dumps(raw_title_data.get('team', {}).get('voice', [])),
                'team_translator': json.dumps(raw_title_data.get('team', {}).get('translator', [])),
                'team_timing': json.dumps(raw_title_data.get('team', {}).get('timing', [])),
                "season_key": season_norm.key,
                "season_code": season_norm.code,
                "season_string": season_norm.string,
                'season_year': raw_title_data.get('season', {}).get('year', None),
                'season_week_day': raw_title_data.get('season', {}).get('week_day', None),
                'description': raw_title_data.get('description', ''),
                'in_favorites': raw_title_data.get('in_favorites', 0),
                'blocked_copyrights': raw_title_data.get('blocked', {}).get('copyrights', False),
                'blocked_geoip': raw_title_data.get('blocked', {}).get('geoip', False),
                'blocked_geoip_list': json.dumps(raw_title_data.get('blocked', {}).get('geoip_list', [])),
                'host_for_player': raw_title_data.get('player', {}).get('host', ''),
                'alternative_player': raw_title_data.get('player', {}).get('alternative_player', ''),
                'last_updated': datetime.now(timezone.utc),
            }

            self.logger.debug(
                f"STATUS INCOMING: code={raw_title_data.get('status', {}).get('code')} "
                f"str='{raw_title_data.get('status', {}).get('string')}' | external_id={external_id}"
            )

            title_id = self.save_manager.save_title(
                provider_code=provider_code,
                external_id=external_id,
                title_fields=title_fields,
            )

            external_data = {
                'studio_name': raw_title_data.get('studio', ''),
                'rating_name': raw_title_data.get('rating', {}).get('name', ''),
                'rating_score': raw_title_data.get("rating", {}).get('score', 0.0),
            }

            if not self.process_external_data(title_id, external_data):
                self.logger.info(
                    f"Skipping further processing for external_id={external_id}, provider={provider_code}"
                )

            self.process_franchises({'external_id': external_id, 'title_id': title_id, **title_fields})

            genres_json = title_fields['title_genres']
            decoded_genres = json.loads(genres_json)
            self.logger.debug(f"GENRES: {title_id}:{decoded_genres}")
            self.save_manager.save_genre(title_id, decoded_genres)

            team_data = {
                'voice': title_fields['team_voice'],
                'translator': title_fields['team_translator'],
                'timing': title_fields['team_timing'],
            }
            self.logger.debug(f"TEAM DATA: {title_id}:{team_data}")
            if team_data:
                self.save_manager.save_team_members(title_id, team_data)

            return True, title_id

        except Exception as e:
            self.logger.error(f"Failed to save title to database: {e}")
            return False, None

    def process_episodes(self, title_data):
        try:
            list_data = title_data.get("player", {}).get("list")

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
                            'title_id': title_data.get('title_id', None), # internal id
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
                    'external_id': title_data['external_id'],
                    'title_id': title_data['title_id'],
                    'franchise_id': franchise.get('franchise', {}).get('id'),
                    'franchise_name': franchise.get('franchise', {}).get('name'),
                    'franchise_releases': franchise.get('franchise_releases', [])
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
                            'title_id': title_data.get('title_id'), # Internal id
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
