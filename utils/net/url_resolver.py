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


def _is_hls_like(url: str) -> bool:
    p = urlparse(url)
    path = (p.path or "").lower()
    return path.endswith(".m3u8") or path.endswith(".ts")


def _recommended_host(url: str) -> Optional[str]:
    try:
        return urlparse(url).hostname
    except Exception:
        return None


def _parse_expires_from_headers(headers: httpx.Headers) -> Optional[datetime]:
    """
    Пытаемся вытащить TTL из Cache-Control: max-age или Expires.
    """
    now = datetime.now(timezone.utc)

    cc = headers.get("Cache-Control") or headers.get("cache-control")
    if cc:
        parts = [p.strip().lower() for p in cc.split(",")]
        for p in parts:
            if p.startswith("max-age="):
                try:
                    sec = int(p.split("=", 1)[1])
                    if sec > 0:
                        return now + timedelta(seconds=sec)
                except Exception:
                    pass

    exp = headers.get("Expires") or headers.get("expires")
    if exp:
        try:
            # httpx использует email.utils.parsedate_to_datetime через Response,
            # но тут проще: попросим httpx распарсить через response внизу.
            # Поэтому здесь оставим None — а воспользуемся resp.headers + resp напрямую, если захочешь.
            return None
        except Exception:
            return None

    return None


def resolve_redirects(
    url: str,
    *,
    client: httpx.Client,
    max_hops: int = 5,
    cache: Optional[TTLCache] = None,
    default_cache_ttl: timedelta = timedelta(minutes=7),
    min_cache_ttl: timedelta = timedelta(minutes=1),
    max_cache_ttl: timedelta = timedelta(minutes=30),
    # NEW:
    use_head: Optional[bool] = None,     # None = auto
    head_timeout_s: float = 1.5,
    get_timeout_s: float = 8.0,
    skip_hosts: Optional[set[str]] = None,
) -> ResolveResult:
    cache_key = url
    if cache is not None:
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

    host0 = _recommended_host(url) or ""

    # fast-skip по trusted host
    if skip_hosts and host0 in skip_hosts:
        now = datetime.now(timezone.utc)
        expires_at = now + default_cache_ttl
        result = ResolveResult(
            original_url=url,
            final_url=url,
            chain=[],
            recommended_host=host0 or None,
            cache_until=expires_at,
        )
        if cache is not None:
            cache.set(cache_key, result, expires_at)
        return result

    # авто: для .m3u8/.ts сразу GET (HEAD часто висит через proxy/CDN)
    if use_head is None:
        use_head = not _is_hls_like(url)

    chain: List[Hop] = []
    current = url
    now = datetime.now(timezone.utc)

    for _ in range(max_hops + 1):
        resp = None

        if use_head:
            try:
                resp = client.request("HEAD", current, timeout=head_timeout_s, follow_redirects=False)
            except Exception:
                resp = None

        # если HEAD выключен или не удался/неинформативен — GET(stream) и закрываем
        if (
            resp is None
            or resp.status_code in (405, 400, 403)
            or (resp.status_code < 200 and resp.status_code not in (301, 302, 303, 307, 308))
        ):
            try:
                with client.stream("GET", current, timeout=get_timeout_s) as r:
                    resp = r
                    _ = r.status_code
            except Exception:
                return ResolveResult(
                    original_url=url,
                    final_url=current,
                    chain=chain,
                    recommended_host=_recommended_host(current),
                    cache_until=None,
                )

        status = resp.status_code
        location = resp.headers.get("Location")

        chain.append(Hop(url=current, status_code=status, location=location))

        if status in (301, 302, 303, 307, 308) and location:
            current = urljoin(current, location)
            continue

        # не редирект — финал
        final_url = current

        # TTL: сначала query expires=..., потом Cache-Control max-age, потом дефолт
        expires_at = _parse_expires_from_query(final_url)
        if expires_at is None:
            expires_at = _parse_expires_from_headers(resp.headers)
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
    return ResolveResult(
        original_url=url,
        final_url=current,
        chain=chain,
        recommended_host=_recommended_host(current),
        cache_until=None,
    )