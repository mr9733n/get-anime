from __future__ import annotations


def norm_str(value: str | None) -> str | None:
    """Convert empty/whitespace strings to None."""
    if value is None:
        return None
    if isinstance(value, str) and not value.strip():
        return None
    return value


def make_base_url(host_for_player: str | None) -> str | None:
    host = norm_str(host_for_player)
    if not host:
        return None
    # host in DB is usually like "cache.libria.fun" (no schema)
    if host.startswith("http://") or host.startswith("https://"):
        return host.rstrip("/")
    return f"https://{host}".rstrip("/")


def abs_url(base_url: str | None, path_or_url: str | None) -> str | None:
    """
    If path_or_url is already absolute -> return it.
    If it's relative -> join with base_url if present.
    If base_url missing -> return raw relative (still useful for callers that add host later).
    """
    s = norm_str(path_or_url)
    if not s:
        return None

    if s.startswith("http://") or s.startswith("https://"):
        return s

    if not base_url:
        return s

    if s.startswith("/"):
        return base_url + s
    return base_url + "/" + s
