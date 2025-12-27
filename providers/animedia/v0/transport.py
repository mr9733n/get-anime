# transport.py
import json
import logging
from typing import Any, Mapping, Optional

import httpx

class HttpTransportError(RuntimeError):
    """Базовый тип ошибок транспортного уровня."""

class HttpxTransport:
    """
    Адаптер над вашим кастомным net_client.
    Делает запросы через httpx, но сохраняет возможность
    добавить прокси, таймауты и любые другие настройки,
    которые уже реализованы в net_client.create_async_httpx_client().
    """

    def __init__(self, net_client, *, headers: Mapping[str, str], timeout: float = 30.0,
                 follow_redirects: bool = True, logger: logging.Logger | None = None,) -> None:
        self.logger = logger or logging.getLogger(__name__)
        self._net_client = net_client
        self._headers = dict(headers)
        self._timeout = timeout
        self._follow = follow_redirects

    async def _make_client(self):
        # ваш net_client уже умеет создавать клиент с нужными параметрами
        return self._net_client.create_async_httpx_client(
            headers=self._headers,
            timeout=self._timeout,
            follow_redirects=self._follow,
        )

    @staticmethod
    async def request_json(resp: httpx.Response) -> str:
        """Возвращает html‑строку или поле `html` из JSON‑ответа."""
        try:
            return resp.json().get("html", "")
        except json.JSONDecodeError:
            return resp.text

    async def get(self, url: str) -> str:
        async with await self._make_client() as client:
            resp = await client.get(url)
            resp.raise_for_status()
            return await self.request_json(resp)

    async def post(self, url: str, data: Mapping[str, Any] | None = None) -> str:
        async with await self._make_client() as client:
            resp = await client.post(url, data=data)
            resp.raise_for_status()
            return await self.request_json(resp)
