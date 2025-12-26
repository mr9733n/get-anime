from __future__ import annotations
from dataclasses import dataclass, field
from datetime import timedelta

@dataclass(frozen=True)
class ResolverConfig:
    enabled: bool = True

    max_hops: int = 5

    # auto: для .m3u8/.ts HEAD не используем
    use_head: bool | None = None
    head_timeout_s: float = 1.5
    get_timeout_s: float = 8.0

    default_cache_ttl: timedelta = timedelta(minutes=7)
    min_cache_ttl: timedelta = timedelta(minutes=1)
    max_cache_ttl: timedelta = timedelta(minutes=30)

    skip_hosts: set[str] = field(default_factory=lambda: {"cache.libria.fun"})
