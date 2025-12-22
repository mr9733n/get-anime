# transport.py
from __future__ import annotations

import json
import os
import time
import httpx
import logging
from typing import Any, Dict, Optional, Tuple

from providers.aniliberty.v1.cache_policy import CachePolicy


class HttpTransport:
    """
    Low-level HTTP transport with retries + small TTL cache + optional response dumps.

    Тут НЕ должно быть бизнес-логики. Только:
    - отправка запросов
    - декод JSON
    - кэширование
    - логи/дампы
    """

    def __init__(
        self,
        *,
        net_client: Any,
        base_url: str,
        utils_folder: str = "temp",
        logger: logging.Logger | None = None,
        sleep_fn: Any | None = None,
        timeout: httpx.Timeout | None = None,
        headers: Dict[str, str] | None = None,
        limits: httpx.Limits | None = None,
        cache_policy: CachePolicy | None = None,
        max_cache_items: int = 256,
        enable_dumps: bool = False,
    ) -> None:
        self.logger = logger or logging.getLogger(__name__)
        self.utils_folder = utils_folder
        self._sleep = sleep_fn or time.sleep
        self.max_cache_items = max(0, int(max_cache_items))
        self._cache_policy = cache_policy
        self.enable_dumps = enable_dumps
        if self.enable_dumps:
            os.makedirs(self.utils_folder, exist_ok=True)

        self._http = net_client.create_httpx_client(
            base_url=base_url,
            http2=False,
            timeout=timeout or httpx.Timeout(15.0, read=30.0, connect=10.0),
            headers=headers
            or {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36 Edg/140.0.0.0",
                "Accept": "application/json",
                "Accept-Encoding": "gzip, deflate",
                "Connection": "keep-alive",
            },
            limits=limits or httpx.Limits(max_keepalive_connections=6, max_connections=6),
        )

        # key: (endpoint, frozenset(params.items()) or None) -> (expires_ts, data)
        self._cache: Dict[Tuple[str, Optional[frozenset]], Tuple[float, Any]] = {}

    def close(self) -> None:
        try:
            self._http.close()
        except Exception:
            pass

    def _cache_key(
            self,
            endpoint: str,
            params: Optional[Dict[str, Any]]
    ) -> Optional[Tuple[str, Optional[frozenset]]]:
        if not params:
            return (endpoint, None)
        try:
            return (endpoint, frozenset(sorted(params.items())))
        except Exception:
            return None

    def _cache_get(self, endpoint: str, params: Optional[Dict[str, Any]], ttl: int) -> tuple[
        Optional[Any], Optional[tuple[str, Optional[frozenset]]]]:
        if ttl <= 0:
            return None, None

        cache_key = self._cache_key(endpoint, params)
        if cache_key is None:
            return None, None

        cached = self._cache.get(cache_key)
        if cached is None:
            return None, cache_key

        exp, data = cached
        if exp < time.time():
            self._cache.pop(cache_key, None)
            return None, cache_key

        return data, cache_key

    def _cache_ttl_for(self, endpoint: str) -> int:
        if not self._cache_policy:
            return 0
        return self._cache_policy.ttl_for(endpoint)

    def request_json(
        self,
        endpoint: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        method: str = "GET",
        attempts: int = 3,
        backoff: float = 0.6,
        cache_ttl: Optional[int] = None,
    ) -> Any:
        method = (method or "GET").upper()

        request_kwargs = {}
        if method in ("POST", "PUT", "PATCH"):
            request_kwargs["json"] = params or None
        else:
            request_kwargs["params"] = params or None

        ttl = int(cache_ttl) if cache_ttl is not None else self._cache_ttl_for(endpoint)

        cached_data, cache_key = (None, None)
        if method == "GET":
            cached_data, cache_key = self._cache_get(endpoint, params, ttl)
            if cached_data is not None:
                return cached_data

        last_err: Exception | None = None

        for attempt in range(1, max(1, attempts) + 1):
            t0 = time.time()
            try:
                resp = self._http.request(method, endpoint, **request_kwargs)

                ct = resp.headers.get("Content-Type", "")
                ce = resp.headers.get("Content-Encoding", "")
                bytes_len = len(resp.content or b"")

                try:
                    resp.raise_for_status()
                except httpx.HTTPStatusError as e:
                    status_code = e.response.status_code
                    self.logger.debug(f"HTTP {status_code} {endpoint} | CT:{ct} | CE:{ce}")
                    return {"error": "HTTP error", "status_code": status_code, "endpoint": endpoint}

                try:
                    data = resp.json()
                except (UnicodeDecodeError, json.JSONDecodeError) as e:
                    if self.enable_dumps:
                        ts = int(time.time())
                        safe = endpoint.replace("/", "_")
                        try:
                            with open(os.path.join(self.utils_folder, f"{safe}_{ts}.bin"), "wb") as fb:
                                fb.write(resp.content)
                        except Exception:
                            pass
                        try:
                            with open(os.path.join(self.utils_folder, f"{safe}_{ts}.txt"), "w", encoding="utf-8", errors="replace") as ft:
                                ft.write(resp.text)
                        except Exception:
                            pass

                    self.logger.error(f"JSON decode error on {endpoint}: {e} | CT:{ct} CE:{ce}")
                    return {"error": "JSON decode error", "content_type": ct, "content_encoding": ce}

                elapsed = time.time() - t0
                self.logger.info(f"API {endpoint}: {elapsed:.2f}s; {bytes_len} bytes")

                if self.enable_dumps:
                    try:
                        ts = int(time.time())
                        safe = endpoint.replace("/", "_")
                        with open(os.path.join(self.utils_folder, f"{safe}_{ts}.json"), "w", encoding="utf-8") as f:
                            json.dump(data, f, ensure_ascii=False, indent=2)
                    except Exception:
                        pass

                if cache_key is not None:
                    self._cache[cache_key] = (time.time() + ttl, data)
                    if self.max_cache_items and len(self._cache) > self.max_cache_items:
                        self._cache.pop(next(iter(self._cache)))

                return data

            except httpx.RequestError as e:
                last_err = e
                self.logger.warning(f"Request error {endpoint} (attempt {attempt}/{attempts}): {e}")
                if attempt < attempts:
                    self._sleep(backoff * attempt)
                continue
            except Exception as e:
                last_err = e
                self.logger.error(f"Unexpected error in transport for {endpoint}: {e}")
                break

        return {"error": str(last_err) if last_err else "Unknown transport error", "endpoint": endpoint}

    def request_raw(
        self,
        endpoint: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        method: str = "GET",
        attempts: int = 3,
        backoff: float = 0.6,
    ) -> bytes:
        method = (method or "GET").upper()

        request_kwargs = {}
        if method in ("POST", "PUT", "PATCH"):
            request_kwargs["json"] = params or None
        else:
            request_kwargs["params"] = params or None

        last_err: Exception | None = None
        for attempt in range(1, max(1, attempts) + 1):
            try:
                resp = self._http.request(method, endpoint, **request_kwargs)
                resp.raise_for_status()
                return resp.content or b""
            except httpx.RequestError as e:
                last_err = e
                self.logger.warning(f"Request error {endpoint} (attempt {attempt}/{attempts}): {e}")
                if attempt < attempts:
                    self._sleep(backoff * attempt)
                continue
            except httpx.HTTPStatusError as e:
                last_err = e
                self.logger.warning(f"HTTP {e.response.status_code} {endpoint}")
                break
            except Exception as e:
                last_err = e
                self.logger.error(f"Unexpected error in transport for {endpoint}: {e}")
                break

        return b""