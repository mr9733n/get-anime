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

# =========================
# NEW: assets helpers
# =========================

def normalize_provider_code(value: str | None) -> str | None:
    """
    В проекте provider иногда хранится как name (AniLibria), иногда как code (aniliberty).
    Приводим к code, который понимает конфиг.
    """
    s = norm_str(value)
    if not s:
        return None
    p = s.strip().lower()
    mapping = {
        "aniliberty": "aniliberty",
        "anilibria": "aniliberty",
        "ani libria": "aniliberty",
        "libria": "aniliberty",
        "animedia": "animedia",
    }
    return mapping.get(p, p)


def make_assets_base(provider_code: str | None, cfg) -> str | None:
    """
    base URL для ассетов (preview/posters/torrents) из config.ini:
      [Settings]
      base_al_url = aniliberty.top
      base_am_url = amd.online
    cfg — utils.config.config_manager.ConfigManager
    """
    if not cfg:
        return None

    p = normalize_provider_code(provider_code)
    if not p:
        return None

    if p == "aniliberty":
        host = cfg.get_setting("Settings", "base_al_url", None)
    elif p == "animedia":
        host = cfg.get_setting("Settings", "base_am_url", None)
    else:
        host = None

    return make_base_url(host)


def abs_asset_url(
    provider_code: str | None,
    cfg,
    path_or_url: str | None,
    *,
    fallback_base: str | None = None,
) -> str | None:
    """
    Строит абсолютный URL ассета:
    - если path_or_url уже absolute → вернёт как есть
    - иначе попробует assets host из конфига
    - если его нет → fallback_base (обычно stream base)
    """
    s = norm_str(path_or_url)
    if not s:
        return None

    if s.startswith("http://") or s.startswith("https://"):
        return s

    base = make_assets_base(provider_code, cfg) or fallback_base
    return abs_url(base, s)