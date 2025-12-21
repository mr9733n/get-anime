# net_client.py
import requests
import httpx
from utils.config_manager import NetworkConfig


class NetworkError(requests.exceptions.RequestException):
    """Базовое исключение для всех сетевых ошибок"""
    def __init__(self, message: str, url: str | None = None, original_error: Exception | None = None):
        super().__init__(message)
        self.url = url
        self.original_error = original_error


class NetworkTimeoutError(NetworkError):
    """Превышен таймаут запроса"""
    pass


class NetworkConnectionError(NetworkError):
    """Ошибка соединения (нет сети, DNS, etc)"""
    pass


class NetworkHTTPError(NetworkError):
    """HTTP ошибка (4xx, 5xx)"""
    def __init__(self, message: str, url: str, status_code: int, original_error: Exception | None = None):
        super().__init__(message, url, original_error)
        self.status_code = status_code


class NetClient:
    def __init__(self, cfg: NetworkConfig):
        if cfg.proxy_enabled and cfg.proxy_url:
            self._proxy_url = cfg.proxy_url
            self._requests_proxies = {
                "http": cfg.proxy_url,
                "https": cfg.proxy_url,
            }
        else:
            self._proxy_url = None
            self._requests_proxies = None

        # requests.Session
        self.requests_session = requests.Session()
        if self._requests_proxies:
            self.requests_session.proxies.update(self._requests_proxies)

        # httpx.Client — HTTP/1, один прокси
        self.httpx_client = httpx.Client(
            proxy=self._proxy_url,  # тут просто строка или None
            http1=True,
            http2=False,
        )


    def get(self, url: str, **kwargs):
        try:
            return self.requests_session.get(url, **kwargs)
        except requests.Timeout as e:
            raise NetworkTimeoutError(f"Request timeout for {url}", url=url, original_error=e) from e
        except requests.ConnectionError as e:
            raise NetworkConnectionError(f"Connection failed for {url}", url=url, original_error=e) from e
        except requests.HTTPError as e:
            status_code = e.response.status_code if e.response else None
            raise NetworkHTTPError(
                f"HTTP error {status_code} for {url}",
                url=url,
                status_code=status_code,
                original_error=e
            ) from e
        except requests.RequestException as e:
            raise NetworkError(f"Request failed for {url}", url=url, original_error=e) from e


    def post(self, url: str, **kwargs):
        try:
            return self.requests_session.post(url, **kwargs)
        except requests.Timeout as e:
            raise NetworkTimeoutError(f"Request timeout for {url}", url=url, original_error=e) from e
        except requests.ConnectionError as e:
            raise NetworkConnectionError(f"Connection failed for {url}", url=url, original_error=e) from e
        except requests.HTTPError as e:
            status_code = e.response.status_code if e.response else None
            raise NetworkHTTPError(
                f"HTTP error {status_code} for {url}",
                url=url,
                status_code=status_code,
                original_error=e
            ) from e
        except requests.RequestException as e:
            raise NetworkError(f"Request failed for {url}", url=url, original_error=e) from e


    def get_httpx_client(self) -> httpx.Client:
        return self.httpx_client

    def create_httpx_client(self, *, base_url: str = "", headers: dict | None = None,
                            timeout: httpx.Timeout | float | None = None,
                            limits: httpx.Limits | None = None,
                            http2: bool = False) -> httpx.Client:
        """
        Создать НОВЫЙ httpx.Client с тем же proxy и базовыми настройками,
        но с дополнительными параметрами (base_url, timeout, headers, limits, ...).
        """
        if timeout is None:
            timeout = httpx.Timeout(15.0, read=30.0, connect=10.0)
        if limits is None:
            limits = httpx.Limits(max_keepalive_connections=6, max_connections=6)

        return httpx.Client(
            proxy=self._proxy_url,
            http1=True,
            http2=http2,
            base_url=base_url,
            headers=headers,
            timeout=timeout,
            limits=limits,
        )

    def create_async_httpx_client(self, **kwargs) -> httpx.AsyncClient:
        """
        Создаёт НОВЫЙ асинхронный httpx.AsyncClient
        с автоматически подставленным прокси + любыми доп. параметрами.
        """
        return httpx.AsyncClient(
            proxy=self._proxy_url,
            http1=True,
            http2=False,
            **kwargs,
        )
