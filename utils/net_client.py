# net_client.py
import requests
import httpx
from utils.config_manager import NetworkConfig

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
        return self.requests_session.get(url, **kwargs)

    def post(self, url: str, **kwargs):
        return self.requests_session.post(url, **kwargs)

    def get_httpx_client(self) -> httpx.Client:
        return self.httpx_client
