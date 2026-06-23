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
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from backend.core.dto.schedule import ScheduleItemNormalized
from backend.core.ports.schedule_port import IProviderScheduleSource

_PROVIDER_CODE = "animedia"
_TIME_RE = re.compile(r"(?P<hour>\d{1,2})[:.](?P<minute>\d{2})")
_DATE_RE = re.compile(r"(?P<day>\d{1,2})[-./](?P<month>\d{1,2})[-./](?P<year>\d{4})")


def _parse_animedia_meta(meta: str, *, now: datetime | None = None) -> datetime | None:
    """
    Parse AniMedia's meta date string into a datetime.

    Handles:
      "Сегодня, 16:00"       → today's date at 16:00 (tz-naive)
      "Вчера, 16:00"         → yesterday at 16:00 (tz-naive)
      "Новая серия в 16:00"  → today's date at 16:00 (tz-naive)
      "7-01-2026, 16:00"     → 2026-01-07 at 16:00 (tz-naive)
      ""                     → None
    Returns tz-naive datetime or None.
    """
    meta = " ".join((meta or "").replace("\xa0", " ").split())
    if not meta:
        return None

    ref = now or datetime.now()
    normalized = meta.lower()

    hour, minute = 0, 0
    time_match = _TIME_RE.search(normalized)
    if time_match:
        try:
            parsed_hour = int(time_match.group("hour"))
            parsed_minute = int(time_match.group("minute"))
            if 0 <= parsed_hour <= 23 and 0 <= parsed_minute <= 59:
                hour, minute = parsed_hour, parsed_minute
            else:
                return None
        except ValueError:
            return None

    if "сегодня" in normalized or "today" in normalized or "новая серия" in normalized:
        base = ref.date()
    elif "вчера" in normalized or "yesterday" in normalized:
        base = (ref - timedelta(days=1)).date()
    else:
        date_match = _DATE_RE.search(normalized)
        if date_match is None:
            return None
        try:
            base = datetime(
                int(date_match.group("year")),
                int(date_match.group("month")),
                int(date_match.group("day")),
            ).date()
        except ValueError:
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

    def invalidate_cache(self) -> None:
        invalidate = getattr(self.api, "invalidate_schedule_cache", None)
        if callable(invalidate):
            invalidate()

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
            page = page_entry.get("page")
            try:
                page_int = int(page)
            except (TypeError, ValueError):
                page_int = None
            section = "announcement" if page_int == 0 else "schedule"
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
                        raw={
                            "encoded": raw,
                            "page": page_int,
                            "section": section,
                            "title": si.title,
                            "meta": si.meta,
                            "episode": si.episode,
                            "poster_url": si.poster_url,
                            "title_url": si.link,
                        },
                    )
                )

        self._log(f"AniMedia schedule: {len(items)} items (day={day})")
        return items

    def get_catalog(
        self,
        *,
        max_titles: int = 120,
        pages: int = 5,
        load_more: bool = False,
    ) -> list[ScheduleItemNormalized]:
        """Fetch AniMedia catalog as lightweight provider-only title cards."""
        if load_more:
            raw_pages = self._run_async(self.api.load_more_titles(pages))
        else:
            raw_pages = self._run_async(self.api.get_all_titles(max_titles, pages))
        return self._normalize_pages(raw_pages or [], section="catalog")

    @staticmethod
    def _run_async(coro):
        try:
            return asyncio.run(coro)
        except RuntimeError:
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                return pool.submit(asyncio.run, coro).result()

    def _normalize_pages(
        self,
        pages: list[dict[str, Any]],
        *,
        section: str,
    ) -> list[ScheduleItemNormalized]:
        from providers.animedia.v0.models import ScheduleItem

        items: list[ScheduleItemNormalized] = []
        for page_entry in pages:
            page = page_entry.get("page")
            try:
                page_int = int(page)
            except (TypeError, ValueError):
                page_int = None

            raw_titles: list[str] = page_entry.get("titles") or []
            for raw in raw_titles:
                if not isinstance(raw, str) or not raw.strip():
                    continue
                try:
                    si = ScheduleItem.from_separator_string(raw)
                except Exception as exc:
                    self._log(f"AniMedia catalog parse error: {exc!r} raw={raw!r}")
                    continue

                ext_id = (si.title_id or "").strip()
                if not ext_id:
                    continue

                items.append(
                    ScheduleItemNormalized(
                        provider_code=_PROVIDER_CODE,
                        external_title_id=ext_id,
                        day_of_week=None,
                        air_dt=None,
                        episode_label=si.episode,
                        poster_url=si.poster_url,
                        title_url=si.link,
                        raw={
                            "encoded": raw,
                            "page": page_int,
                            "section": section,
                            "title": si.title,
                            "meta": si.meta,
                            "episode": si.episode,
                            "poster_url": si.poster_url,
                            "title_url": si.link,
                        },
                    )
                )
        return items
