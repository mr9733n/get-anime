# api_client.py - ТУПЫЙ HTTP клиент для API v1
import os
import time
import requests
import logging


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

    def _send_request(self, endpoint, params=None, method='GET'):
        """
        Универсальный метод для отправки запросов.

        Args:
            endpoint: путь эндпоинта (например: 'anime/releases/random')
            params: параметры запроса
            method: HTTP метод (GET/POST)

        Returns:
            dict: JSON ответ или {'error': 'описание ошибки'}
        """
        url = f"{self.pre}{self.base_url}/api/{self.api_version}/{endpoint}"

        try:
            start_time = time.time()

            if method == 'POST':
                response = requests.post(url, json=params, timeout=30)
            else:
                response = requests.get(url, params=params, timeout=30)

            response.raise_for_status()
            end_time = time.time()

            data = response.json()

            # Сохраняем для отладки
            utils_json = os.path.join(self.utils_folder, 'response.json')
            with open(utils_json, 'w', encoding='utf-8') as file:
                file.write(response.text)

            num_items = len(response.text) if response.text else 0
            self.logger.info(
                f"API call to {endpoint}: "
                f"{end_time - start_time:.2f}s, "
                f"{num_items} bytes"
            )

            return data

        except requests.exceptions.HTTPError as http_err:
            error_message = f"HTTP error: {http_err} - URL: {url}"
            self.logger.error(error_message)
            return {'error': error_message}

        except requests.exceptions.RequestException as req_err:
            error_message = f"Request error: {req_err} - URL: {url}"
            self.logger.error(error_message)
            return {'error': error_message}

        except Exception as e:
            error_message = f"Unexpected error: {e} - URL: {url}"
            self.logger.error(error_message)
            return {'error': error_message}

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