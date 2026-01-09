from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Request:
    op: str
    params: dict[str, Any]


@dataclass(frozen=True)
class Response:
    ok: bool
    result: Any = None
    error: str | None = None


def parse_request(payload: dict[str, Any]) -> Request:
    op = (payload.get("op") or "").strip()
    params = payload.get("params") or {}
    if not isinstance(params, dict):
        raise ValueError("params must be an object")
    if not op:
        raise ValueError("op is required")
    return Request(op=op, params=params)


def ok(result: Any) -> dict[str, Any]:
    return {"ok": True, "result": result, "error": None}


def fail(message: str) -> dict[str, Any]:
    return {"ok": False, "result": None, "error": message}
