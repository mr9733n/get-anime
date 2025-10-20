# api_adapter.py - УМНЫЙ адаптер для API v1 (OPTIMIZED)
import logging
import threading
from datetime import datetime, timezone


class APIAdapter:
    """
    Адаптер между API v1 (anilibria.top) и старым форматом процессора.

    КРИТИЧЕСКИЕ ИСПРАВЛЕНИЯ:
    1. Используем ВЛОЖЕННЫЕ данные (episodes, members, torrents) из базового ответа
    2. Делаем отдельные запросы ТОЛЬКО если данных нет
    3. Правильная структура для process.py
    """

    def __init__(self, api_client, stream_video_host="cache.libria.fun", api_version="v1"):
        self.api_version = api_version
        self.logger = logging.getLogger(__name__)
        self.client = api_client
        self.stream_video_host = stream_video_host
        self._title_locks = {}
        self._title_locks_guard = threading.Lock()

    # ============================================
    # ПУБЛИЧНЫЕ МЕТОДЫ
    # ============================================

    def get_schedule(self, day):
        """Получает расписание для конкретного дня."""
        try:
            today = datetime.now().isoweekday()
            day = int(day)
            if day == today:
                self.logger.info(f"Requesting TODAY's schedule (day={day}) via /schedule/now")
                return self._get_schedule_now(day)
            else:
                self.logger.info(f"Requesting schedule for day={day} (today={today}) via /schedule/week")
                return self._get_schedule_week(day)

        except Exception as e:
            self.logger.error(f"Error in get_schedule: {e}")
            return {'error': str(e)}

    def _get_schedule_now(self, day: int):
        """Загружает расписание на СЕГОДНЯ."""
        try:
            now_data = self.client.get_schedule_now()

            if 'error' in now_data:
                return now_data

            if not isinstance(now_data, dict) or 'today' not in now_data:
                self.logger.error(f"Unexpected schedule/now format: {type(now_data)}")
                return {'error': 'Invalid schedule/now format'}

            today_items = now_data.get('today', [])

            adapted_releases = []
            for item in today_items:
                release_data = item.get('release', {})
                adapted = self._enrich_and_adapt(release_data, fetch_episodes=False)

                ep = item.get('published_release_episode') or {}
                if ep:
                    adapted.setdefault('meta', {})['last_episode'] = {
                        'id': ep.get('id'),
                        'num': ep.get('ordinal'),
                        'name': ep.get('name'),
                        'updated_at': ep.get('updated_at'),
                        'hls_480': ep.get('hls_480'),
                        'hls_720': ep.get('hls_720'),
                        'hls_1080': ep.get('hls_1080'),
                        'duration': ep.get('duration'),
                    }

                adapted_releases.append(adapted)


            self.logger.info(f"Loaded today's schedule: {len(adapted_releases)} releases")

            return [{
                'day': day,
                'list': adapted_releases
            }]

        except Exception as e:
            self.logger.error(f"Error in _get_schedule_now: {e}")
            return {'error': str(e)}

    def _get_schedule_week(self, day_index: int, *, max_workers=2):
        """Загружает расписание на ВСЮ НЕДЕЛЮ, но обогащает только выбранный день."""
        try:
            day_index = int(day_index)
            raw = int(day_index)
            api_day = raw if 1 <= raw <= 7 else (raw + 1 if 0 <= raw <= 6 else ((raw - 1) % 7) + 1)

            week_data = self.client.get_schedule_week()
            if isinstance(week_data, dict) and 'error' in week_data: return week_data
            if not isinstance(week_data, list):
                self.logger.error(f"Unexpected week schedule format: {type(week_data)}")
                return {'error': 'Invalid schedule format'}

            # раскладываем по publish_day (внутри release)
            buckets = {i: [] for i in range(1, 8)}
            miss = 0
            for r in week_data:
                rel = r.get('release') or {}
                pd = (rel.get('publish_day') or {}).get('value')
                try:
                    pd = int(pd) if pd is not None else None
                except:
                    pd = None
                if isinstance(pd, int) and 1 <= pd <= 7:
                    buckets[pd].append(r)
                else:
                    miss += 1

            day_list = buckets.get(api_day, []) or []

            # адаптируем без сетевых догрузок
            adapted_list = []
            for r in day_list:
                release = (r.get('release') or r)
                adapted_list.append(
                    self._enrich_and_adapt(
                        release,
                        fetch_episodes=True,  # возьмём встроенные, но...
                        fetch_torrents=False,  # ...не трогаем сеть
                        fetch_team=False,
                        fetch_franchises=False,
                        allow_network=False  # ← критично
                    )
                )

            return [{'day': api_day, 'list': adapted_list}]
        except Exception as e:
            self.logger.error(f"Error in _get_schedule_week: {type(e).__name__}: {e}")
            return {'error': str(e)}

    def get_search_by_title(self, search_text):
        """Поиск релизов по названию."""
        try:
            results = self.client.search_releases(search_text)

            if 'error' in results:
                return results

            if isinstance(results, list):
                enriched = [self._enrich_and_adapt(r) for r in results]
                return {'list': enriched}
            elif isinstance(results, dict) and 'data' in results:
                enriched = [self._enrich_and_adapt(r) for r in results['data']]
                return {
                    'list': enriched,
                    'pagination': results.get('pagination', {})
                }

            return results

        except Exception as e:
            self.logger.error(f"Error in get_search_by_title: {e}")
            return {'error': str(e)}

    def get_search_by_title_id(self, title_id):
        """Получить релиз по ID."""
        try:
            release = self.client.get_release_by_id(title_id)

            if 'error' in release:
                return release

            adapted = self._enrich_and_adapt(release)

            return {
                'list': [adapted],
                'pagination': self._single_item_pagination()
            }

        except Exception as e:
            self.logger.error(f"Error in get_search_by_title_id({title_id}): {e}")
            return {'error': str(e)}

    def get_search_by_title_ids(self, title_ids):
        """Получить релизы по списку ID."""
        try:
            data = self.client.get_releases_list(
                ids=title_ids,
                limit=len(title_ids)
            )

            if 'error' in data:
                return data

            releases = self._extract_releases(data)
            enriched = [self._enrich_and_adapt(r) for r in releases]

            return {
                'list': enriched,
                'pagination': data.get('pagination', {})
            }

        except Exception as e:
            self.logger.error(f"Error in get_search_by_title_ids: {e}")
            return {'error': str(e)}

    def get_random_title(self):
        """Получить случайный релиз."""
        try:
            data = self.client.get_random_releases(limit=1)

            if 'error' in data:
                return data

            if isinstance(data, list) and len(data) > 0:
                release = data[0]
            elif isinstance(data, dict):
                release = data
            else:
                return {'error': 'No random title found'}

            adapted = self._enrich_and_adapt(release)

            return {
                'list': [adapted],
                'pagination': self._single_item_pagination()
            }

        except Exception as e:
            self.logger.error(f"Error in get_random_title: {e}")
            return {'error': str(e)}

    # ============================================
    # АДАПТАЦИЯ ДАННЫХ
    # ============================================

    def _enrich_and_adapt(self, release, *, fetch_episodes=True, fetch_torrents=True,
                          fetch_team=True, fetch_franchises=True, single_episode=None,
                          allow_network=True):
        """
        Главный метод адаптации.

        ОПТИМИЗАЦИЯ: Сначала проверяем ВЛОЖЕННЫЕ данные,
        только потом делаем отдельные запросы.
        """
        try:
            release_id = release.get('id')

            # 1. Базовая адаптация
            adapted = self._adapt_structure(release)

            # 2. Эпизоды - ПРИОРИТЕТ вложенным данным
            if fetch_episodes:
                episodes = self._fetch_episodes(release, release_id, allow_network=allow_network)
                if episodes:
                    adapted['player']['list'] = episodes

            # 3. Торренты - ПРИОРИТЕТ вложенным данным
            if fetch_torrents:
                torrents = self._fetch_torrents(release, release_id)
                if torrents:
                    adapted['torrents'] = {'list': torrents}

            # 4. Команда - ПРИОРИТЕТ вложенным данным
            if fetch_team:
                team = self._fetch_team(release, release_id)
                if team:
                    adapted['team'] = team

            # 5. Франшизы - требуют отдельного запроса
            if fetch_franchises:
                try:
                    franchises = self._fetch_franchises(release_id)
                    if franchises:
                        adapted['franchises'] = franchises
                except Exception as e:
                    self.logger.debug(f"Franchises not available for {release_id}: {e}")

            return adapted

        except Exception as e:
            self.logger.error(f"Error enriching release {release.get('id')}: {e}", exc_info=True)
            return self._adapt_structure(release)

    def _adapt_structure(self, release):
        """Адаптирует базовую структуру релиза."""
        adapted = {
            'id': release.get('id'),
            'code': release.get('alias', ''),

            'names': {
                'ru': release.get('name', {}).get('main', ''),
                'en': release.get('name', {}).get('english', ''),
                'alternative': release.get('name', {}).get('alternative', '')
            },

            'posters': {
                'small': {
                    'url': release.get('poster', {}).get('thumbnail', '')
                },
                'medium': {
                    'url': release.get('poster', {}).get('preview', '')
                },
                'original': {
                    'url': release.get('poster', {}).get('src', '')
                }
            },

            'status': self._map_status(release),

            'type': {
                'code': None,
                'string': release.get('type', {}).get('value', ''),
                'full_string': release.get('type', {}).get('description', ''),
                'episodes': release.get('episodes_total'),
                'length': str(release.get('average_duration_of_episode', 0))
            },

            'season': {
                'code': None,
                'string': release.get('season', {}).get('value', ''),
                'year': release.get('year'),
                'week_day': release.get('publish_day', {}).get('value')
            },

            'description': release.get('description', ''),
            'announce': '',

            'updated': self._to_timestamp(release.get('updated_at')),
            'last_change': self._to_timestamp(release.get('updated_at')),

            'in_favorites': release.get('added_in_users_favorites', 0),

            'blocked': {
                'copyrights': release.get('is_blocked_by_copyrights', False),
                'geoip': release.get('is_blocked_by_geo', False),
                'geoip_list': []
            },

            'player': {
                'host': self.stream_video_host,  # ИСПРАВЛЕНО: заполняем из конфига
                'alternative_player': release.get('external_player', ''),
                'list': {}
            },

            'genres': self._extract_genre_names(release.get('genres', [])),

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

    def _extract_genre_names(self, genres_list):
        """Извлекает только имена жанров."""
        if not genres_list:
            return []

        return [g.get('name', '') for g in genres_list if g.get('name')]

    def _map_status(self, release):
        """Маппинг статуса."""
        if release.get('is_ongoing'):
            return {'code': 2, 'string': 'В работе'}
        elif release.get('is_in_production'):
            return {'code': 3, 'string': 'Анонс'}
        else:
            return {'code': 1, 'string': 'Завершён'}

    def _to_timestamp(self, iso_date):
        """Конвертирует ISO дату → unix timestamp, терпимо относится к 'Z' и отсутствующей TZ."""
        if not iso_date:
            return 0
        try:
            s = str(iso_date)
            # '2025-10-20T21:36:25Z' → '+00:00'
            if s.endswith('Z'):
                s = s[:-1] + '+00:00'
            # если вообще нет смещения и 'T', добавим UTC
            if 'T' in s and ('+' not in s and '-' in s.split('T')[-1] and s[-6:-5] == ':') is False and (
                    '+' not in s and 'Z' not in s):
                # грубо: если нет явной TZ, добавим UTC
                s = s + '+00:00'
            dt = datetime.fromisoformat(s)
            return int(dt.timestamp())
        except Exception:
            try:
                # обрежем миллисекунды, если кривые
                core = s.split('.')[0]
                if core.endswith('Z'):
                    core = core[:-1]
                dt = datetime.fromisoformat(core)
                return int(dt.replace(tzinfo=timezone.utc).timestamp())
            except Exception:
                return 0

    # ============================================
    # ЭПИЗОДЫ
    # ============================================

    def _fetch_episodes(self, release, release_id, allow_network=True):
        """
        Правильный порядок:
          1) Пробуем встроенные episodes из release
          2) Если их нет и allow_network=True — дергаем /anime/releases/{id}/episodes
          3) Если и там пусто — финальный fallback: полный релиз /anime/releases/{id}
        """
        try:
            # 1) Встроенные из того, что уже есть
            episodes_list = release.get('episodes') or []
            if isinstance(episodes_list, dict) and 'data' in episodes_list:
                episodes_list = episodes_list.get('data') or []

            # 2) Полный релиз: часто содержит episodes и экономит лишний запрос к /episodes
            if not episodes_list and allow_network:
                try:
                    full_release = self.client.get_release_by_id(release_id)
                    if full_release and 'error' not in full_release:
                        eps2 = full_release.get('episodes') or []
                        if isinstance(eps2, dict) and 'data' in eps2:
                            eps2 = eps2.get('data') or []
                        episodes_list = eps2
                        # Чтобы дальше обогащение шло из «полного» ответа
                        if episodes_list:
                            release = full_release
                except Exception as e:
                    self.logger.debug(f"Failed to fetch full release for episodes {release_id}: {e}")

            # 3) Отдельный /episodes — НО только если он «разрешён» для этого id
            can_try_eps = getattr(self.client, "episodes_supported", lambda _id: True)(release_id)
            if not episodes_list and allow_network and can_try_eps:
                try:
                    eps = self.client.get_release_episodes(release_id)
                    # Если клиент сам вернул None после 404 — просто пропускаем
                    if eps and 'error' not in eps:
                        if isinstance(eps, dict) and 'data' in eps:
                            episodes_list = eps['data'] or []
                        elif isinstance(eps, list):
                            episodes_list = eps
                except Exception as e:
                    self.logger.debug(f"Failed to fetch episodes via /episodes for {release_id}: {e}")

            if not episodes_list:
                return None

            adapted_episodes = {}
            for episode in episodes_list:
                adapted_ep = self._adapt_episode(episode)
                num = str(adapted_ep.get('episode', 0))
                if num != '0':
                    adapted_episodes[num] = adapted_ep

            self.logger.debug(f"Adapted {len(adapted_episodes)} episodes for {release_id}")
            return adapted_episodes or None

        except Exception as e:
            self.logger.error(f"Error fetching episodes for {release_id}: {e}")
            return None

    def _adapt_episode(self, episode):
        """Адаптирует эпизод v1 → старый формат."""
        ordinal = episode.get('ordinal', 0)
        episode_number = int(ordinal) if ordinal else 0

        name = episode.get('name', '') or episode.get('name_english', '')
        if not name:
            name = f"Серия {episode_number}"

        opening = episode.get('opening') or {}
        ending = episode.get('ending') or {}

        skips = {
            'opening': [
                opening.get('start', 0) if opening else 0,
                opening.get('stop', 0) if opening else 0
            ],
            'ending': [
                ending.get('start', 0) if ending else 0,
                ending.get('stop', 0) if ending else 0
            ]
        }

        preview_data = episode.get('preview', {})
        preview_url = preview_data.get('preview', '') if isinstance(preview_data, dict) else ''

        # Нормализуем URL эпизодов (убираем протокол и параметры)
        hls_fhd = self._normalize_episode_url(episode.get('hls_1080', ''))
        hls_hd = self._normalize_episode_url(episode.get('hls_720', ''))
        hls_sd = self._normalize_episode_url(episode.get('hls_480', ''))

        adapted = {
            'episode': episode_number,
            'uuid': episode.get('id', ''),
            'name': name,
            'hls': {
                'fhd': hls_fhd,
                'hd': hls_hd,
                'sd': hls_sd
            },
            'skips': skips,
            'preview': preview_url,
            'created_timestamp': self._to_timestamp(episode.get('updated_at'))
        }

        return adapted

    def _normalize_episode_url(self, url):
        """
        Нормализует URL эпизода для совместимости со старым форматом.

        API v1 возвращает:
        https://cache.libria.fun/videos/media/ts/10037/1/1080/hash.m3u8?params

        Старый формат хранил:
        /videos/media/ts/10037/1/1080/hash.m3u8

        Args:
            url: полный URL от API v1

        Returns:
            str: нормализованный путь без протокола, домена и параметров
        """
        if not url:
            return ''

        try:
            # Убираем query параметры (?countryIso=...)
            url_without_params = url.split('?')[0]

            # Убираем протокол и домен (https://cache.libria.fun)
            # Оставляем только путь (/videos/media/ts/...)
            if '://' in url_without_params:
                path = url_without_params.split('://', 1)[1]  # убираем https://
                if '/' in path:
                    path = '/' + path.split('/', 1)[1]  # убираем домен, оставляем /videos/...
                    return path

            # Если это уже нормализованный путь - возвращаем как есть
            return url_without_params

        except Exception as e:
            self.logger.warning(f"Failed to normalize URL '{url}': {e}")
            # В случае ошибки возвращаем оригинал
            return url

    # ============================================
    # ТОРРЕНТЫ
    # ============================================

    def _fetch_torrents(self, release, release_id):
        """
        КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ:
        1. Сначала проверяем ВЛОЖЕННЫЕ торренты
        2. Если их нет - запрашиваем через отдельный эндпоинт (он существует!)
        """
        try:
            # 1. ПРИОРИТЕТ: Вложенные торренты
            torrents_list = release.get('torrents', [])

            if not torrents_list:
                # 2. Для торрентов эндпоинт существует
                self.logger.debug(f"No embedded torrents, fetching separately for {release_id}")

                try:
                    torrents_data = self.client.get_release_torrents(release_id)

                    if 'error' in torrents_data or not torrents_data:
                        self.logger.debug(f"No torrents found for {release_id}")
                        return None

                    if isinstance(torrents_data, dict) and 'data' in torrents_data:
                        torrents_list = torrents_data['data']
                    elif isinstance(torrents_data, list):
                        torrents_list = torrents_data
                    else:
                        return None

                except Exception as e:
                    self.logger.debug(f"Failed to fetch torrents for {release_id}: {e}")
                    return None

            if not torrents_list:
                return None

            adapted_torrents = [self._adapt_torrent(t) for t in torrents_list]

            self.logger.debug(f"Adapted {len(adapted_torrents)} torrents for {release_id}")

            return adapted_torrents

        except Exception as e:
            self.logger.error(f"Error fetching torrents for {release_id}: {e}")
            return None

    def _adapt_torrent(self, torrent):
        """Адаптирует торрент v1 → старый формат."""
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
            'uploaded_timestamp': self._to_timestamp(torrent.get('created_at')),
            'hash': torrent_hash,
            'metadata': None,
            'raw_base64_file': None
        }

    # ============================================
    # КОМАНДА
    # ============================================

    def _fetch_team(self, release, release_id):
        """
        КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ:
        1. Сначала проверяем ВЛОЖЕННЫХ members
        2. Если их нет - запрашиваем через отдельный эндпоинт
        """
        try:
            # 1. ПРИОРИТЕТ: Вложенные members
            members_list = release.get('members', [])

            if not members_list:
                # 2. Запрашиваем отдельно
                self.logger.debug(f"No embedded members, fetching separately for {release_id}")

                try:
                    members_data = self.client.get_release_members(release_id)

                    if 'error' in members_data or not members_data:
                        self.logger.debug(f"No members found for {release_id}")
                        return None

                    members_list = members_data

                except Exception as e:
                    self.logger.debug(f"Failed to fetch members for {release_id}: {e}")
                    return None

            if not members_list:
                return None

            # 3. Группируем по ролям
            team = {
                'voice': [],
                'translator': [],
                'timing': []
            }

            for member in members_list:
                role_value = member.get('role', {}).get('value', '').lower()
                nickname = member.get('nickname', '')

                if not nickname:
                    continue

                # Маппинг ролей API v1
                if role_value == 'voicing':
                    team['voice'].append(nickname)
                elif role_value == 'translating':
                    team['translator'].append(nickname)
                elif role_value == 'timing':
                    team['timing'].append(nickname)

            self.logger.debug(f"Adapted team for {release_id}: {len(members_list)} members")

            return team

        except Exception as e:
            self.logger.error(f"Error fetching team for {release_id}: {e}")
            return None

    # ============================================
    # ФРАНШИЗЫ
    # ============================================

    def _fetch_franchises(self, release_id):
        """Получает франшизы (требует отдельного запроса)."""
        try:
            franchises_data = self.client.get_franchise_by_release(release_id)

            if 'error' in franchises_data or not franchises_data:
                return None

            if isinstance(franchises_data, dict):
                franchises_list = [franchises_data]
            elif isinstance(franchises_data, list):
                franchises_list = franchises_data
            else:
                return None

            adapted_franchises = []

            for franchise_data in franchises_list:
                adapted = self._adapt_franchise(franchise_data)
                if adapted:
                    adapted_franchises.append(adapted)

            return adapted_franchises if adapted_franchises else None

        except Exception as e:
            self.logger.debug(f"No franchises for {release_id}: {e}")
            return None

    def _adapt_franchise(self, franchise_data):
        """Адаптирует франшизу v1 → старый формат."""
        try:
            franchise_releases = franchise_data.get('franchise_releases', [])

            releases_list = []
            for item in franchise_releases:
                release = item.get('release', {})

                releases_list.append({
                    'id': release.get('id'),
                    'code': release.get('alias'),
                    'names': {
                        'ru': release.get('name', {}).get('main', ''),
                        'en': release.get('name', {}).get('english', ''),
                        'alternative': release.get('name', {}).get('alternative', '')
                    }
                })

            adapted = {
                'franchise': {
                    'id': franchise_data.get('id'),
                    'name': franchise_data.get('name', '')
                },
                'releases': releases_list
            }

            return adapted

        except Exception as e:
            self.logger.error(f"Error adapting franchise: {e}")
            return None

    # ============================================
    # УТИЛИТЫ
    # ============================================

    def _extract_releases(self, data):
        """Извлекает массив релизов из ответа API."""
        if isinstance(data, list):
            return data
        elif isinstance(data, dict):
            if 'data' in data:
                return data['data']
            elif 'releases' in data:
                return data['releases']

        return []

    def _single_item_pagination(self):
        """Пагинация для одного элемента."""
        return {
            'pages': 1,
            'current_page': 1,
            'items_per_page': 1,
            'total_items': 1
        }

    def _lock_for(self, release_id: int):
        with self._title_locks_guard:
            lock = self._title_locks.get(release_id)
            if not lock:
                lock = threading.Lock()
                self._title_locks[release_id] = lock
            return lock

    # ============================================
    # Асинхронная загрузка пакетами
    # ============================================

    def get_release_full(self, release_id, *, need=('torrents','members','franchises','episodes'), max_workers=4):
        """
        Полные данные по релизу за один вызов адаптера.
        Внутри: параллельно тянем части (через APIClient.fetch_release_bundle),
        затем адаптируем в старый формат.
        """
        lock = self._lock_for(int(release_id))
        with lock:
            bundle = self.client.fetch_release_bundle(release_id, need=need, max_workers=max_workers)
            if not bundle or ('error' in bundle):
                return bundle
            return self._enrich_and_adapt(bundle)

    def get_releases_full(self, release_ids, *, need=('torrents','members','franchises','episodes'), max_workers=8):
        """
        Полные данные по нескольким релизам (параллельно), результат — список уже адаптированных элементов.
        """
        bundles = self.client.fetch_release_bundles(release_ids, need=need, max_workers=max_workers)
        out = []
        for rid in release_ids:
            b = bundles.get(rid)
            if b and ('error' not in b):
                out.append(self._enrich_and_adapt(b))
        return out