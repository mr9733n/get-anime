from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from backend.core.ports.process_write import IProcessWritePort, ApplyProviderPayloadResult


@dataclass(frozen=True)
class ApplyProviderPayloadInput:
    provider_code: str
    payload: dict[str, Any]
    mode: str = "auto"


class ApplyProviderPayloadUseCase:
    def __init__(self, write_port: IProcessWritePort):
        self._write_port = write_port

    def execute(self, inp: ApplyProviderPayloadInput) -> ApplyProviderPayloadResult:
        provider_code = (inp.provider_code or "").strip()
        if not provider_code:
            raise ValueError("provider_code is required")

        if not isinstance(inp.payload, dict):
            raise ValueError("payload must be an object (dict)")

        mode = (inp.mode or "auto").strip().lower()

        return self._write_port.apply_provider_payload(
            provider_code=provider_code,
            payload=inp.payload,
            mode=mode,
        )
