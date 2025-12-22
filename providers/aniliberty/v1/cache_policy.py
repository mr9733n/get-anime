# cache_policy.py
from dataclasses import dataclass
from typing import Iterable
from .endpoints import MEMBERS


@dataclass(frozen=True)
class EndpointTTL:
    prefix: str
    ttl: int
    description: str = ""


@dataclass(frozen=True)
class CachePolicy:
    endpoints: Iterable[EndpointTTL]

    def ttl_for(self, endpoint: str) -> int:
        if endpoint.endswith(MEMBERS):
            for rule in self.endpoints:
                if rule.prefix == MEMBERS:
                    return rule.ttl
            return 0

        for rule in self.endpoints:
            if endpoint.startswith(rule.prefix):
                return rule.ttl
        return 0
