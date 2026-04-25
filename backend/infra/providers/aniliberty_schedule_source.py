from __future__ import annotations

"""AniLiberty → ScheduleItemNormalized adapter.

AniLiberty get_schedule(day) returns (sync):
    [{"day": int, "list": [adapted_legacy_release]}, ...]

Each adapted_legacy_release (from APIAdapter._enrich_and_adapt) has:
    "external_id": int
    "names": {"ru": ..., "en": ...}
    "posters": {"small": {...}, "medium": {"url": ...}, "original": {...}}
    "season": {"week_day": int, ...}

AniLiberty does NOT provide a precise air time — only day_of_week is known.
"""

import logging
from dataclasses import dataclass
from typing import Any

from backend.core.dto.schedule import ScheduleItemNormalized
from backend.core.ports.schedule_port import IProviderScheduleSource

_PROVIDER_CODE = "aniliberty"


def _extract_poster_url(release: dict[str, Any]) -> str | None:
    posters = release.get("posters") or {}
    for key in ("medium", "original", "small"):
        entry = posters.get(key)
        if isinstance(entry, dict):
            url = entry.get("url")
            if url:
                return str(url)
    return None


@dataclass(frozen=True)
class AniLibertyScheduleSource(IProviderScheduleSource):
    """
    Wraps AniLiberty APIAdapter and produces ScheduleItemNormalized list.

    api: APIAdapter (or compatible) with a synchronous get_schedule(day) method.
    """

    api: Any
    logger: Any = None

    def _log(self, msg: str) -> None:
        lg = self.logger or logging.getLogger(__name__)
        lg.debug(msg)

    def get_schedule(self, *, day: int | None = None) -> list[ScheduleItemNormalized]:
        """
        Fetch schedule from AniLiberty.

        day: 1-7 (Mon-Sun). If None, fetches all 7 days sequentially.
        """
        if day is not None:
            return self._fetch_day(day)

        items: list[ScheduleItemNormalized] = []
        for d in range(1, 8):
            try:
                items.extend(self._fetch_day(d))
            except Exception as exc:
                self._log(f"AniLiberty schedule day={d} error: {exc!r}")
        return items

    def _fetch_day(self, day: int) -> list[ScheduleItemNormalized]:
        try:
            # Prefer the lightweight variant — it makes only 1 network call per day
            # instead of 1 per release (no episodes/torrents fetched for schedule).
            if hasattr(self.api, "get_schedule_light"):
                raw = self.api.get_schedule_light(day)
            else:
                raw = self.api.get_schedule(day)
        except Exception as exc:
            self._log(f"AniLiberty get_schedule({day}) failed: {exc!r}")
            return []

        if isinstance(raw, dict) and "error" in raw:
            self._log(f"AniLiberty get_schedule({day}) returned error: {raw['error']}")
            return []

        if not isinstance(raw, list):
            return []

        items: list[ScheduleItemNormalized] = []
        for entry in raw:
            if not isinstance(entry, dict):
                continue
            entry_day = int(entry.get("day") or day)
            releases = entry.get("list") or []
            for release in releases:
                if not isinstance(release, dict):
                    continue
                item = self._release_to_item(release, day=entry_day)
                if item is not None:
                    items.append(item)

        self._log(f"AniLiberty schedule day={day}: {len(items)} items")
        return items

    def _release_to_item(
        self, release: dict[str, Any], *, day: int
    ) -> ScheduleItemNormalized | None:
        ext_id = release.get("external_id")
        if ext_id is None:
            return None
        try:
            ext_id_str = str(int(ext_id))
        except (TypeError, ValueError):
            return None

        # day_of_week: prefer release's own week_day, fall back to container day
        season = release.get("season") or {}
        week_day_raw = season.get("week_day")
        try:
            item_day = int(week_day_raw) if week_day_raw is not None else day
        except (TypeError, ValueError):
            item_day = day

        poster_url = _extract_poster_url(release)

        return ScheduleItemNormalized(
            provider_code=_PROVIDER_CODE,
            external_title_id=ext_id_str,
            day_of_week=item_day,
            air_dt=None,        # AniLiberty has no precise air time
            episode_label=None,
            poster_url=poster_url,
            title_url=None,
            raw=release,
        )
