# legacy_mapper.py
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass
class LegacyMapper:
    """
    Pure mapping layer: raw AniLibria v1 -> legacy структура.

    Принципы:
    - НИКАКОЙ сети здесь нет
    - Mapper принимает RAW структуры и превращает в то, что ждёт старый код.
    - normalize_episode_url() сохраняет host (без схемы) в stream_video_host
      и возвращает ТОЛЬКО путь (как в старом API).
    """
    logger: Any
    stream_video_host = "cache.libria.fun"
    api_version = "v1"

    # =========================
    # Base release mapping
    # =========================
    def adapt_structure(self, release: Dict[str, Any]) -> Dict[str, Any]:
        """Адаптирует базовую структуру релиза (максимально близко к твоему текущему адаптеру)."""
        adapted = {
            'external_id': release.get('id'),
            'code': release.get('alias', ''),
            'provider': 'AniLiberty',
            'names': {
                'ru': (release.get('name') or {}).get('main', ''),
                'en': (release.get('name') or {}).get('english', ''),
                'alternative': (release.get('name') or {}).get('alternative', '')
            },

            'posters': {
                'small': {
                    'url': (release.get('poster') or {}).get('thumbnail', '')
                },
                'medium': {
                    'url': (release.get('poster') or {}).get('preview', '')
                },
                'original': {
                    'url': (release.get('poster') or {}).get('src', '')
                }
            },

            'status': self.map_status(release),

            'type': {
                'code': None,
                'string': (release.get('type') or {}).get('value', '')
            },

            'season': {
                'code': None,
                'string': (release.get('season') or {}).get('value', ''),
                'year': release.get('year'),
                'week_day': (release.get('publish_day') or {}).get('value')
            },

            'description': release.get('description', '') or '',
            'announce': '',

            'updated': self.to_timestamp(release.get('updated_at')),
            'last_change': self.to_timestamp(release.get('updated_at')),

            'in_favorites': release.get('added_in_users_favorites', 0),

            'blocked': {
                'copyrights': release.get('is_blocked_by_copyrights', False),
                'geoip': release.get('is_blocked_by_geo', False),
                'geoip_list': []
            },

            'player': {
                'host': None,
                'alternative_player': release.get('external_player', ''),
                'list': {}
            },

            'genres': self.extract_genre_names(release.get('genres', [])),

            'team': {
                'voice': [],
                'translator': [],
                'timing': []
            },

            'franchises': [],

            'torrents': {
                'list': []
            }
        }

        return adapted

    def extract_genre_names(self, genres_list: Any) -> List[str]:
        """Извлекает только имена жанров."""
        if not genres_list:
            return []
        return [g.get('name', '') for g in genres_list if isinstance(g, dict) and g.get('name')]

    def map_status(self, release: Dict[str, Any]) -> Dict[str, Any]:
        """
        Приводим статус к старому формату (как в текущем APIAdapter._map_status):
          code: 1 = В работе, 2 = Завершён, 3 = Анонс
        """
        v = (release.get('status') or {}).get('value')
        if isinstance(v, str):
            vs = v.strip().lower()
            if vs in {'released', 'release', 'complete', 'completed', 'finished', 'done'}:
                return {'code': 2, 'string': 'Завершён'}
            if vs in {'ongoing', 'in_work', 'current'}:
                return {'code': 1, 'string': 'В работе'}
            if vs in {'announcement', 'announced', 'in_production', 'production', 'planned', 'pending'}:
                return {'code': 3, 'string': 'Анонс'}

        if release.get('is_ongoing'):
            return {'code': 1, 'string': 'В работе'}
        if release.get('is_in_production'):
            return {'code': 3, 'string': 'Анонс'}

        return {'code': 2, 'string': 'Завершён'}

    # =========================
    # Team mapping (members)
    # =========================
    def adapt_team(self, members_list: Any) -> Dict[str, List[str]]:
        team = {'voice': [], 'translator': [], 'timing': []}
        if not members_list:
            return team

        if isinstance(members_list, dict):
            members_list = members_list.get('list') or members_list.get('data') or []

        if not isinstance(members_list, list):
            return team

        for member in members_list:
            if not isinstance(member, dict):
                continue
            role_value = ((member.get('role') or {}).get('value') or '').lower()
            nickname = member.get('nickname', '') or ''
            if not nickname:
                continue

            if role_value == 'voicing':
                team['voice'].append(nickname)
            elif role_value == 'translating':
                team['translator'].append(nickname)
            elif role_value == 'timing':
                team['timing'].append(nickname)

        return team

    # =========================
    # Episode mapping
    # =========================
    def adapt_episode(self, episode: Dict[str, Any]) -> Dict[str, Any]:
        episode_number = int(episode.get('ordinal') or 0)
        name = episode.get('name', '') or episode.get('name_english', '')
        if not name:
            name = f"Серия {episode_number}"

        opening = episode.get('opening') or {}
        ending = episode.get('ending') or {}

        skips = {
            'opening': [opening.get('start', 0) if opening else 0, opening.get('stop', 0) if opening else 0],
            'ending': [ending.get('start', 0) if ending else 0, ending.get('stop', 0) if ending else 0],
        }

        hls_fhd = self.normalize_episode_url(episode.get('hls_1080', ''))
        hls_hd = self.normalize_episode_url(episode.get('hls_720', ''))
        hls_sd = self.normalize_episode_url(episode.get('hls_480', ''))

        preview_url = (episode.get('preview') or {}).get('src', '')

        return {
            'episode': episode_number,
            'uuid': episode.get('id', ''),
            'name': name,
            'hls': {'fhd': hls_fhd, 'hd': hls_hd, 'sd': hls_sd},
            'skips': skips,
            'preview': preview_url,
            'created_timestamp': self.to_timestamp(episode.get('updated_at'))
        }

    def normalize_episode_url(self, url: str) -> str:
        if not url:
            return ""

        try:
            url_without_params = url.split("?", 1)[0]

            if url_without_params.startswith("/"):
                return url_without_params

            scheme_split = url_without_params.split("://", 1)
            if len(scheme_split) != 2:
                return url_without_params

            host_and_path = scheme_split[1]

            if "/" in host_and_path:
                host, path = host_and_path.split("/", 1)
                normalized_path = "/" + path
            else:
                host, normalized_path = host_and_path, ""

            if self.stream_video_host is None:
                self.stream_video_host = host
            elif self.stream_video_host != host and self.logger:
                try:
                    self.logger.warning(f"Different host detected: {host} (expected {self.stream_video_host})")
                except Exception:
                    pass

            return normalized_path
        except Exception as exc:
            if self.logger:
                try:
                    self.logger.warning(f"Failed to normalize URL '{url}': {exc}")
                except Exception:
                    pass
            return url

    # =========================
    # Torrent mapping
    # =========================
    def adapt_torrent(self, torrent: Dict[str, Any]) -> Dict[str, Any]:
        self.logger.debug(f"Raw torrent data: {torrent}")

        description = torrent.get('description', '')
        torrent_hash = torrent.get('hash', '')

        return {
            'torrent_id': torrent.get('id'),
            'episodes': {
                'string': description,
                'first': None,
                'last': None
            },
            'quality': {
                'string': torrent.get('quality', {}).get('description', ''),
                'type': torrent.get('type', {}).get('value', ''),
                'resolution': torrent.get('quality', {}).get('value', ''),
                'encoder': torrent.get('codec', {}).get('value', '')
            },
            'leechers': torrent.get('leechers', 0),
            'seeders': torrent.get('seeders', 0),
            'downloads': torrent.get('completed_times', 0),
            'total_size': torrent.get('size', 0),
            'size_string': f"{torrent.get('size', 0) / (1024 ** 3):.2f} GB",
            'url': f"/api/{self.api_version}/anime/torrents/{torrent_hash}/file",
            'magnet': torrent.get('magnet', ''),
            'uploaded_timestamp': self.to_timestamp(torrent.get('created_at')),
            'hash': torrent_hash,
            'metadata': None,
            'raw_base64_file': None,
            'label':  torrent.get('label', ''),
            'filename': torrent.get('filename', ''),
            'episodes_total': torrent.get('release', {}).get('episodes_total', 0),
            'is_in_production': (
                torrent.get('release', {}).get('is_in_production')
                if isinstance(torrent.get('release'), dict)
                else torrent.get('is_in_production', False)
            ),
            'updated_at': self.to_timestamp(torrent.get('updated_at')),
        }
    # =========================
    # Franchise mapping
    # =========================
    def adapt_franchise(self, franchise_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        franchise_data ожидается с franchise_releases.
        Формат как в текущем APIAdapter._adapt_franchise.
        """
        try:
            franchise_releases = franchise_data.get('franchise_releases', []) or []
            franchise_releases_list: list[dict] = []

            for item in franchise_releases:
                rel = (item or {}).get('release', {}) or {}
                release_dict = {
                    'id': rel.get('id'),
                    'code': rel.get('alias'),
                    'names': {
                        'ru': (rel.get('name') or {}).get('main', ''),
                        'en': (rel.get('name') or {}).get('english', ''),
                        'alternative': (rel.get('name') or {}).get('alternative', '')
                    },
                    'posters': {
                        'small': {'url': (rel.get('poster') or {}).get('thumbnail', '')},
                        'medium': {'url': (rel.get('poster') or {}).get('preview', '')},
                        'original': {'url': (rel.get('poster') or {}).get('src', '')}
                    },
                    'season': (rel.get('season') or {}).get('value'),
                    'type': (rel.get('type') or {}).get('value'),
                    'year': rel.get('year'),
                    'updated': self.to_timestamp(rel.get('updated_at'))
                }

                franchise_releases_list.append({
                    'franchise_release_id': item.get('id'),
                    'ordinal': item.get('sort_order'),
                    'release_id': item.get('release_id'),
                    'franchise_id': item.get('franchise_id'),
                    'release': release_dict
                })
            adapted = {
                'franchise': {
                    'id': franchise_data.get('id'),
                    'name': franchise_data.get('name', '')
                },
                'franchise_releases': franchise_releases_list
            }

            return adapted
        except Exception:
            return None

    # =========================
    # Utils
    # =========================
    def to_timestamp(self, date_str: Optional[str]) -> int:
        if not date_str:
            return 0

        try:
            s = date_str
            if s.endswith('Z'):
                s = s[:-1] + '+00:00'
            if 'T' in s and not re.search(r"[+-]\d{2}:\d{2}$", s):
                # если нет явной TZ, добавим UTC
                if not s.endswith('+00:00'):
                    s = s + '+00:00'
            dt = datetime.fromisoformat(s)
            return int(dt.timestamp())
        except Exception:
            try:
                core = date_str.split('.')[0]
                if core.endswith('Z'):
                    core = core[:-1]
                dt = datetime.fromisoformat(core)
                return int(dt.replace(tzinfo=timezone.utc).timestamp())
            except Exception:
                return 0
