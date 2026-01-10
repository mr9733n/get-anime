from __future__ import annotations

from typing import Any

from backend.core.ports.process_write import ApplyProviderPayloadResult
from backend.core.use_cases.apply_provider_payload import (
    ApplyProviderPayloadUseCase,
    ApplyProviderPayloadInput,
)


class ProcessController:
    def __init__(self, use_case: ApplyProviderPayloadUseCase):
        self._uc = use_case

    def process_provider_payload(
        self,
        *,
        provider_code: str,
        payload: dict[str, Any],
        mode: str = "auto",
    ) -> ApplyProviderPayloadResult:
        return self._uc.execute(
            ApplyProviderPayloadInput(provider_code=provider_code, payload=payload, mode=mode)
        )

    def apply_provider_payload(
        self,
        *,
        provider_code: str,
        payload: dict[str, Any],
        mode: str = "auto",
    ) -> ApplyProviderPayloadResult:
        return self.process_provider_payload(provider_code=provider_code, payload=payload, mode=mode)
