from __future__ import annotations

from dataclasses import is_dataclass, asdict
from datetime import date, datetime
from typing import Any


def to_jsonable(obj: Any) -> Any:
    """
    Convert dataclasses (including nested), datetime, Path-like and other common objects
    into JSON-serializable structures.
    """
    if obj is None:
        return None

    if is_dataclass(obj):
        # asdict already recursively converts nested dataclasses to dicts/lists,
        # but we still run to_jsonable on values for datetime etc.
        raw = asdict(obj)
        return to_jsonable(raw)

    if isinstance(obj, dict):
        return {str(k): to_jsonable(v) for k, v in obj.items()}

    if isinstance(obj, (list, tuple, set)):
        return [to_jsonable(v) for v in obj]

    if isinstance(obj, (datetime, date)):
        return obj.isoformat()

    # Path / os.PathLike
    try:
        import os
        if isinstance(obj, os.PathLike):
            return str(obj)
    except Exception:
        pass

    # primitives
    if isinstance(obj, (str, int, float, bool)):
        return obj

    # fallback: best-effort string
    return str(obj)
