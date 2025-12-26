from __future__ import annotations
from dataclasses import dataclass, field

from utils.net.url_resolver import resolve_redirects, TTLCache, ResolveResult
from utils.net.net_client import NetClient
from utils.net.url_resolver_config import ResolverConfig

@dataclass
class UrlResolveService:
    net: NetClient
    cache: TTLCache
    cfg: ResolverConfig

    def resolve(self, url: str):
        if not self.cfg.enabled:
            # “выключено” — возвращаем как есть
            return ResolveResult(
                original_url=url,
                final_url=url,
                chain=[],
                recommended_host=None,
                cache_until=None,
            )

        client = self.net.get_httpx_client()
        return resolve_redirects(
            url,
            client=client,
            max_hops=self.cfg.max_hops,
            cache=self.cache,
            default_cache_ttl=self.cfg.default_cache_ttl,
            min_cache_ttl=self.cfg.min_cache_ttl,
            max_cache_ttl=self.cfg.max_cache_ttl,
            use_head=self.cfg.use_head,
            head_timeout_s=self.cfg.head_timeout_s,
            get_timeout_s=self.cfg.get_timeout_s,
            skip_hosts=self.cfg.skip_hosts,
        )
