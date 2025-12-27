from __future__ import annotations
import re
from typing import Optional, Tuple

schedule_key: str = "am_schedule_cache"
all_titles_key: str = "am_all_titles_cache"

def parse_schedule_line(key: str, s: str) -> Tuple[str, str, str, float, Optional[str], str]:
    # дефолты на все случаи
    title = ""
    time_part = ""
    ep_part = ""
    rating: Optional[float] = 0.0
    poster: Optional[str] = None
    original_id = ""

    m = re.search(r"(https?://\S+\.(?:webp|jpg|jpeg|png))", s, flags=re.IGNORECASE)
    poster = m.group(1) if m else None
    core = s[:m.start()].strip() if m else s
    parts = [p.strip() for p in core.split("\u00B7")]

    if key == schedule_key:
        title = parts[0] if len(parts) > 0 else ""
        time_part = parts[1] if len(parts) > 1 else ""
        ep_part = parts[2] if len(parts) > 2 else ""
        original_id = parts[3] if len(parts) > 3 else ""

    elif key == all_titles_key:
        title = parts[0] if len(parts) > 0 else ""
        rating = _to_float_rating(parts[1]) if len(parts) > 1 else 0.0
        ep_part = parts[2] if len(parts) > 2 else ""
        original_id = parts[3] if len(parts) > 3 else ""

    else:
        raise ValueError(f"Unknown animedia parse key: {key}")

    return title, time_part, ep_part, rating, poster, original_id

def _to_float_rating(v) -> float:
    if v is None:
        return 0.0
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip()
    if not s:
        return 0.0
    # часто рейтинг приходит с запятой
    s = s.replace(",", ".")
    # выкинуть всё кроме цифр и точки
    import re
    s = re.sub(r"[^0-9.]+", "", s)
    try:
        return float(s) if s else 0.0
    except ValueError:
        return 0.0