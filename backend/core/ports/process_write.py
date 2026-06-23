from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class ApplyProviderPayloadResult:
    ok: bool
    provider_code: str
    mode: str
    title_id: int | None = None
    details: dict[str, Any] | None = None
    error: str | None = None


class IProcessWritePort(Protocol):
    def apply_provider_payload(
        self,
        *,
        provider_code: str,
        payload: dict[str, Any],
        mode: str = "auto",
    ) -> ApplyProviderPayloadResult:
        ...
