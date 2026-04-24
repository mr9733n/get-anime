from __future__ import annotations

"""AniMedia → ScheduleItemNormalized adapter.

AniMedia get_schedule() is async and returns:
    [{"page": int, "titles": [separator_encoded_str]}, ...]

Each separator_encoded_str parses via ScheduleItem.from_separator_string():
    ScheduleItem(title_id, title, meta, episode, poster_url, link)

The meta field contains one of:
    "Сегодня, 16:00"       – today
    "Вчера, 16:00"         – yesterday
    "7-01-2026, 16:00"     – explicit date DD-MM-YYYY
    ""                     – unknown

We derive day_of_week (1=Mon…7=Sun) from the parsed date/relative word.
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from backend.core.dto.schedule import ScheduleItemNormalized
from backend.core.ports.schedule_port import IProviderScheduleSource

_PROVIDER_CODE = "animedia"


def _parse_animedia_meta(meta: str, *, now: datetime | None = None) -> datetime | None:
    """
    Parse AniMedia's meta date string into a datetime.

    Handles:
      "Сегодня, 16:00"       → today's date at 16:00 (tz-naive)
      "Вчера, 16:00"         → yesterday at 16:00 (tz-naive)
      "7-01-2026, 16:00"     → 2026-01-07 at 16:00 (tz-naive)
      ""                     → None
    Returns tz-naive datetime or None.
    """
    meta = (meta or "").strip()
    if not meta:
        return None

    ref = now or datetime.now()

    # Split on comma: ["Сегодня", " 16:00"] or ["7-01-2026", " 16:00"]
    parts = meta.split(",", 1)
    date_part = parts[0].strip().lower()
    time_str = parts[1].strip() if len(parts) > 1 else ""

    # Parse time
    hour, minute = 0, 0
    if time_str:
        try:
            t = datetime.strptime(time_str.strip(), "%H:%M")
            hour, minute = t.hour, t.minute
        except ValueError:
            pass

    # Determine base date
    if date_part in ("сегодня", "today"):
        base = ref.date()
    elif date_part in ("вчера", "yesterday"):
        base = (ref - timedelta(days=1)).date()
    else:
        # Try "DD-MM-YYYY"
        for fmt in ("%d-%m-%Y", "%d.%m.%Y", "%d/%m/%Y"):
            try:
                base = datetime.strptime(date_part, fmt).date()
                break
            except ValueError:
                continue
        else:
            return None

    return datetime(base.year, base.month, base.day, hour, minute)


@dataclass(frozen=True)
class AniMediaScheduleSource(IProviderScheduleSource):
    """
    Wraps AniMediaAdapter and produces ScheduleItemNormalized list.

    api: AniMediaAdapter instance (has async get_new_titles(max_titles))
    max_titles: max schedule entries to fetch
    """

    api: Any
    max_titles: int = 60
    logger: Any = None

    def _log(self, msg: str) -> None:
        lg = self.logger or logging.getLogger(__name__)
        lg.debug(msg)

    def get_schedule(self, *, day: int | None = None) -> list[ScheduleItemNormalized]:
        """
        Fetch AniMedia schedule synchronously (runs async internally).

        day: if provided, filter results to only that day_of_week.
        """
        from providers.animedia.v0.models import ScheduleItem

        try:
            pages: list[dict[str, Any]] = asyncio.run(
                self.api.get_new_titles(self.max_titles)
            )
        except RuntimeError:
            # Already in an event loop — use a thread
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(
                    asyncio.run, self.api.get_new_titles(self.max_titles)
                )
                pages = future.result()

        if not pages:
            return []

        now = datetime.now()
        items: list[ScheduleItemNormalized] = []

        for page_entry in pages:
            raw_titles: list[str] = page_entry.get("titles") or []
            for raw in raw_titles:
                if not isinstance(raw, str) or not raw.strip():
                    continue

                try:
                    si = ScheduleItem.from_separator_string(raw)
                except Exception as exc:
                    self._log(f"AniMedia schedule parse error: {exc!r} raw={raw!r}")
                    continue

                ext_id = (si.title_id or "").strip()
                if not ext_id:
                    continue

                air_dt = _parse_animedia_meta(si.meta or "", now=now)
                item_day = air_dt.isoweekday() if air_dt is not None else None

                if day is not None and item_day != day:
                    continue

                items.append(
                    ScheduleItemNormalized(
                        provider_code=_PROVIDER_CODE,
                        external_title_id=ext_id,
                        day_of_week=item_day,
                        air_dt=air_dt,
                        episode_label=si.episode,
                        poster_url=si.poster_url,
                        title_url=si.link,
                        raw=raw,
                    )
                )

        self._log(f"AniMedia schedule: {len(items)} items (day={day})")
        return items
