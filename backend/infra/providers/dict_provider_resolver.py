from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from backend.core.ports.provider_resolver import IProviderResolver
from backend.core.ports.provider_payload_source import IProviderPayloadSource


@dataclass(frozen=True)
class DictProviderResolver(IProviderResolver):
    providers: Mapping[str, IProviderPayloadSource]

    def resolve(self, provider_code: str) -> IProviderPayloadSource:
        code = (provider_code or "").strip().lower()
        if not code:
            raise ValueError("provider_code is empty")
        if code not in self.providers:
            raise KeyError(f"Provider not registered: {code}")
        return self.providers[code]
