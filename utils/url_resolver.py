# url_resolver.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Tuple
from urllib.parse import urljoin, urlparse, parse_qs

import httpx


@dataclass(frozen=True)
class Hop:
    url: str
    status_code: int
    location: Optional[str] = None


@dataclass(frozen=True)
class ResolveResult:
    original_url: str
    final_url: str
    chain: List[Hop]
    recommended_host: Optional[str]
    cache_until: Optional[datetime]


class TTLCache:
    """Простой TTL-кэш в памяти. Достаточно для MVP."""
    def __init__(self, max_items: int = 2048):
        self._max_items = max_items
        self._store: Dict[str, Tuple[ResolveResult, datetime]] = {}

    def get(self, key: str) -> Optional[ResolveResult]:
        item = self._store.get(key)
        if not item:
            return None
        value, expires_at = item
        now = datetime.now(timezone.utc)
        if now >= expires_at:
            self._store.pop(key, None)
            return None
        return value

    def set(self, key: str, value: ResolveResult, expires_at: datetime) -> None:
        if len(self._store) >= self._max_items:
            # простейшая стратегия: выкинуть что-то одно (первое попавшееся)
            self._store.pop(next(iter(self._store)), None)
        self._store[key] = (value, expires_at)


def _parse_expires_from_query(url: str) -> Optional[datetime]:
    """
    Ищем expires=... в query:
    - если число большое (>= 1e10) — считаем epoch seconds
    - иначе — считаем TTL в секундах от текущего момента
    """
    qs = parse_qs(urlparse(url).query)
    v = qs.get("expires")
    if not v:
        return None
    try:
        n = int(v[0])
    except Exception:
        return None

    now = datetime.now(timezone.utc)
    if n >= 10_000_000_000:  # ~2286 год, но для epoch норм
        try:
            return datetime.fromtimestamp(n, tz=timezone.utc)
        except Exception:
            return None
    # иначе трактуем как TTL секунд
    if n <= 0:
        return None
    return now + timedelta(seconds=n)


def _recommended_host(url: str) -> Optional[str]:
    try:
        return urlparse(url).hostname
    except Exception:
        return None


def resolve_redirects(
    url: str,
    *,
    client: httpx.Client,
    timeout_s: float = 10.0,
    max_hops: int = 5,
    user_agent: str = "MiniResolver/1.0",
    cache: Optional[TTLCache] = None,
    default_cache_ttl: timedelta = timedelta(minutes=7),
    min_cache_ttl: timedelta = timedelta(minutes=1),
    max_cache_ttl: timedelta = timedelta(minutes=30),
) -> ResolveResult:
    """
    MVP redirect-resolve:
    - HEAD (fallback GET stream=True) без auto-redirect
    - вручную идем по Location
    - max_hops ограничивает цепочку
    """
    cache_key = f"{url}||proxy={client or ''}"
    if cache is not None:
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

    headers = {
        "User-Agent": user_agent,
        "Accept": "*/*",
        "Connection": "close",
    }

    proxies = None
    if client:
        # httpx принимает либо строку, либо dict.
        # Для простоты: одна строка на все схемы.
        proxies = client

    chain: List[Hop] = []
    current = url
    now = datetime.now(timezone.utc)

    # Важно: verify оставляем дефолтным (True).
    # Если твой прокси — MITM и ломает TLS, решай это отдельно (или поставь verify=False только для resolver-а, если осознанно).

    for _ in range(max_hops + 1):
        # 1) пробуем HEAD
        resp = None
        try:
            resp = client.request("HEAD", current, timeout=timeout_s, follow_redirects=False)
        except Exception:
            resp = None

        # 2) если HEAD не работает/не информативен — fallback на GET stream и закрываем сразу
        if resp is None or resp.status_code in (405, 400, 403) or (resp.status_code < 200 and resp.status_code not in (301, 302, 303, 307, 308)):
            try:
                with client.stream("GET", current, timeout=timeout_s) as r:
                    # нам важны только заголовки/код
                    resp = r
                    _ = r.status_code
            except Exception as e:
                # если совсем не получилось — считаем текущий финальным (лучше вернуть что есть, чем падать)
                result = ResolveResult(
                    original_url=url,
                    final_url=current,
                    chain=chain,
                    recommended_host=_recommended_host(current),
                    cache_until=None,
                )
                return result

        status = resp.status_code
        location = resp.headers.get("Location")

        chain.append(Hop(url=current, status_code=status, location=location))

        if status in (301, 302, 303, 307, 308) and location:
            # Location может быть относительным
            nxt = urljoin(current, location)
            current = nxt
            continue

        # не редирект — финал
        final_url = current
        # кэш TTL: expires=... или дефолт
        expires_at = _parse_expires_from_query(final_url)
        if expires_at is None:
            expires_at = now + default_cache_ttl

        # clamp TTL
        ttl = expires_at - now
        if ttl < min_cache_ttl:
            expires_at = now + min_cache_ttl
        elif ttl > max_cache_ttl:
            expires_at = now + max_cache_ttl

        result = ResolveResult(
            original_url=url,
            final_url=final_url,
            chain=chain,
            recommended_host=_recommended_host(final_url),
            cache_until=expires_at,
        )

        if cache is not None:
            cache.set(cache_key, result, expires_at)

        return result

    # если упёрлись в max_hops — возвращаем то, что есть сейчас
    result = ResolveResult(
        original_url=url,
        final_url=current,
        chain=chain,
        recommended_host=_recommended_host(current),
        cache_until=None,
    )
    return result
