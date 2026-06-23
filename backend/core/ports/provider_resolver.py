from __future__ import annotations
from typing import Protocol
from backend.core.ports.provider_payload_source import IProviderPayloadSource

class IProviderResolver(Protocol):
    def resolve(self, provider_code: str) -> IProviderPayloadSource:
        ...
