# api_client.py - ТУПЫЙ HTTP клиент для API v1
import json
import os
import time
import httpx
import random
import logging

from concurrent.futures import ThreadPoolExecutor, as_completed

class APIClient:
    """
    Простой HTTP клиент для AniLibria API v1.
    Только делает запросы - никакой бизнес-логики!
    """

    def __init__(self, base_url, api_version):
        self.logger = logging.getLogger(__name__)
        self.base_url = base_url
        self.api_version = api_version
        self.pre = "https://"
        self.utils_folder = "temp"
        os.makedirs(self.utils_folder, exist_ok=True)
        self._http = httpx.Client(
            base_url=f"{self.pre}{self.base_url}/api/{self.api_version}/",
            http2=False,
            timeout=httpx.Timeout(15.0, read=30.0, connect=10.0),
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36 Edg/140.0.0.0",
                "Accept": "application/json",
                "Accept-Encoding": "gzip, deflate",
                "Connection": "keep-alive",
            },
            limits=httpx.Limits(max_keepalive_connections=6, max_connections=6),
        )
        self._cache = {}  # key: (endpoint, frozenset(params.items()) or None) -> (expires_ts, data)
        self._cache_ttls = {
            "anime/schedule/week": 60,
            "anime/schedule/now": 30,
            "anime/releases/": 60,
            "anime/torrents/release/": 60,
            "anime/releases_members/": 60,  # псевдо-метка, см. ниже
            "anime/franchises/release/": 120,
            "anime/releases_episodes/": 60,  # псевдо-метка
        }

    def _cache_key(self, endpoint, params):
        p = None
        if params:
            try:
                p = frozenset(sorted(params.items()))
            except Exception:
                p = None
        return (endpoint, p)

    def _cache_ttl_for(self, endpoint):
        # Простое сопоставление по префиксам
        for prefix, ttl in self._cache_ttls.items():
            if endpoint.startswith(prefix):
                return ttl
        # Спец-случаи:
        if endpoint.startswith("anime/releases/") and endpoint.endswith("/members"):
            return self._cache_ttls["anime/releases_members/"]
        if endpoint.startswith("anime/releases/") and endpoint.endswith("/episodes"):
            return self._cache_ttls["anime/releases_episodes/"]
        return 0

    def _send_request(self, endpoint, params=None, method='GET', attempts=3, backoff=0.6):
        """
        Универсальный метод для отправки запросов.

        Args:
            endpoint: путь эндпоинта (например: 'anime/releases/random')
            params: параметры запроса
            method: HTTP метод (GET/POST)

        Returns:
            dict: JSON ответ или {'error': 'описание ошибки'}
        """
        url = endpoint  # base_url уже в self._http
        last_err = None
        utils_json = os.path.join(self.utils_folder, 'response.json')
        utils_bin = os.path.join(self.utils_folder, 'response.bin')

        cache_ttl = self._cache_ttl_for(endpoint) if method == 'GET' else 0
        if cache_ttl:
            key = self._cache_key(endpoint, params)
            rec = self._cache.get(key)
            now = time.time()
            if rec and rec[0] > now:
                return rec[1]

        for i in range(attempts):
            response = None
            try:
                t0 = time.time()
                if method == 'POST':
                    response = self._http.post(url, json=params)
                else:
                    response = self._http.get(url, params=params)

                ct = response.headers.get("Content-Type", "")
                ce = response.headers.get("Content-Encoding", "")
                self.logger.debug(f"HTTP {response.status_code} {endpoint} | CT:{ct} | CE:{ce}")

                response.raise_for_status()

                # пытаемся сразу распарсить JSON
                try:
                    data = response.json()
                    if cache_ttl:
                        self._cache[key] = (time.time() + cache_ttl, data)
                    # красивый дамп распакованного JSON
                    with open(utils_json, 'w', encoding='utf-8') as f:
                        json.dump(data, f, ensure_ascii=False, indent=2)
                    self.logger.info(f"API {endpoint}: {time.time() - t0:.2f}s; {len(response.content)} bytes")
                    return data
                except (UnicodeDecodeError, json.JSONDecodeError) as e:
                    # сохраняем и бинарь, и «безопасный» текст (если распаковка была)
                    try:
                        with open(utils_bin, 'wb') as fb:
                            fb.write(response.content)
                    except Exception as dump_err:
                        self.logger.warning(f"Dump(bin) write error: {dump_err}")
                    try:
                        text_safe = response.text  # httpx сам попытается декодировать по r.encoding
                        with open(utils_json, 'w', encoding='utf-8', errors='replace') as f:
                            f.write(text_safe)
                    except Exception as dump_err:
                        self.logger.warning(f"Dump(text) write error: {dump_err}")
                    self.logger.error(f"JSON decode error: {e} | CT:{ct} CE:{ce}")
                    return {"error": "JSON decode error", "content_type": ct, "content_encoding": ce}

            except httpx.HTTPStatusError as e:
                last_err = e
                body_snip = ""
                try:
                    body_snip = (response.text[:300] + "…") if response is not None else ""
                except Exception:
                    pass
                self.logger.error(f"HTTP {e.response.status_code} on {url} | body: {body_snip}")
                # нет смысла ретраить 4xx; 5xx можно, но уже попали сюда после raise_for_status
                if 400 <= e.response.status_code < 500:
                    return {"error": f"HTTP {e.response.status_code}", "body": body_snip}

            except httpx.RequestError as e:
                last_err = e
                # сетевые ошибки — ретраим с backoff
                sleep_s = backoff * (2 ** i) + random.random() * 0.1
                time.sleep(sleep_s)

            except Exception as e:
                last_err = e
                self.logger.error(f"Unexpected error: {e} - URL: {url}")
                return {"error": f"Unexpected error: {e}", "url": url}

        self.logger.error(f"HTTP error after retries: {last_err} - URL: {url}")
        return {"error": str(last_err) if last_err else "Unknown error", "url": url}

    def close(self):
        try:
            self._http.close()
        except Exception:
            pass

    # ============================================
    # ЭНДПОИНТЫ API v1
    # ============================================

    def get_schedule_week(self):
        """Получить расписание на неделю"""
        return self._send_request('anime/schedule/week')

    def get_schedule_now(self):
        """Получить расписание на сегодня"""
        return self._send_request('anime/schedule/now')

    def search_releases(self, query):
        """Поиск релизов по названию"""
        return self._send_request('app/search/releases', params={'query': query})

    def get_release_by_id(self, release_id):
        """Получить релиз по ID"""
        return self._send_request(f'anime/releases/{release_id}')

    def get_release_by_alias(self, alias):
        """Получить релиз по alias (код)"""
        return self._send_request(f'anime/releases/{alias}')

    def get_releases_list(self, ids=None, aliases=None, page=1, limit=10):
        """
        Получить список релизов по ID или alias.

        Args:
            ids: список ID (например [9951, 9433])
            aliases: список alias (например ['darling-in-the-franxx'])
            page: номер страницы
            limit: количество на странице
        """
        params = {'page': page, 'limit': limit}

        if ids:
            params['ids'] = ','.join(map(str, ids))
        if aliases:
            params['aliases'] = ','.join(aliases)

        return self._send_request('anime/releases/list', params=params)

    def get_random_releases(self, limit=1):
        """Получить случайные релизы"""
        return self._send_request('anime/releases/random', params={'limit': limit})

    def get_release_torrents(self, release_id):
        """Получить торренты для релиза"""
        return self._send_request(f'anime/torrents/release/{release_id}')

    def get_release_members(self, release_id):
        """Получить команду (участников) для релиза"""
        return self._send_request(f'anime/releases/{release_id}/members')

    def get_catalog_releases(self, filters=None, page=1, limit=15):
        """
        Получить релизы из каталога с фильтрами.

        Args:
            filters: словарь с фильтрами (genres, types, years, search и т.д.)
            page: номер страницы
            limit: количество на странице
        """
        params = {'page': page, 'limit': limit}

        if filters:
            # API v1 принимает фильтры как f[genres], f[types] и т.д.
            for key, value in filters.items():
                if value is not None:
                    params[f'f[{key}]'] = value

        return self._send_request('anime/catalog/releases', params=params)

    def get_release_episodes(self, release_id):
        """
        Получить эпизоды для релиза.

        ВНИМАНИЕ: Этот эндпоинт возвращает список эпизодов.
        Обычно эпизоды уже есть в основном ответе релиза,
        но этот метод может быть полезен для обновления.
        """
        return self._send_request(f'anime/releases/{release_id}/episodes')

    def get_franchise_by_id(self, franchise_id):
        """
        Получить информацию о франшизе по ID.

        Args:
            franchise_id: UUID франшизы

        Returns:
            dict: Информация о франшизе с массивом franchise_releases
        """
        return self._send_request(f'anime/franchises/{franchise_id}')

    def get_franchise_by_release(self, release_id):
        """
        Получить франшизу(ы) для конкретного релиза.

        ВАЖНО: Это основной метод для получения франшиз!

        Args:
            release_id: ID релиза (int)

        Returns:
            list или dict: Франшизы, связанные с релизом
        """
        return self._send_request(f'anime/franchises/release/{release_id}')

    def fetch_release_bundle(self, release_id, need=('torrents', 'members', 'franchises', 'episodes'), max_workers=4):
        """
        Забирает полную информацию по релизу ПАРАЛЛЕЛЬНО:
        - базовый релиз (обязательно)
        - торренты
        - команда (members)
        - франшизы
        - эпизоды (если не пришли внутри базового релиза)
        Возвращает единый dict "как из get_release_by_id", но дополненный полями.
        """
        # 1) базовый релиз (синхронно — чтобы знать, что уже есть)
        base = self.get_release_by_id(release_id)
        if not base or 'error' in base:
            return base

        tasks = {}
        # 2) параллельно дёргаем всё остальное
        with ThreadPoolExecutor(max_workers=max_workers) as ex:
            if 'torrents' in need:
                tasks['torrents'] = ex.submit(self.get_release_torrents, release_id)
            if 'members' in need:
                tasks['members'] = ex.submit(self.get_release_members, release_id)
            if 'franchises' in need:
                tasks['franchises'] = ex.submit(self.get_franchise_by_release, release_id)
            if 'episodes' in need and not base.get('episodes'):
                tasks['episodes'] = ex.submit(self.get_release_episodes, release_id)

            # 3) собираем результаты
            results = {k: f.result() for k, f in tasks.items()}

        # 4) аккуратно мержим в базовый ответ
        torrents = results.get('torrents')
        if torrents and 'error' not in torrents:
            # API может вернуть list или {"data": [...]}
            base['torrents'] = torrents['data'] if isinstance(torrents, dict) and 'data' in torrents else torrents

        members = results.get('members')
        if members and 'error' not in members:
            base['members'] = members

        franchises = results.get('franchises')
        if franchises and 'error' not in franchises:
            base['franchises'] = franchises

        episodes = results.get('episodes')
        if episodes and 'error' not in episodes and not base.get('episodes'):
            base['episodes'] = episodes

        return base

    def fetch_release_bundles(self, release_ids, need=('torrents', 'members', 'franchises', 'episodes'), max_workers=8):
        """
        Параллельно собирает полные бандлы по списку релизов.
        Возвращает dict: { release_id: bundle_or_error }
        """
        out = {}

        def job(rid):
            return rid, self.fetch_release_bundle(rid, need=need)

        with ThreadPoolExecutor(max_workers=max_workers) as ex:
            futures = [ex.submit(job, rid) for rid in release_ids]
            for fut in as_completed(futures):
                rid, bundle = fut.result()
                out[rid] = bundle

        return out
