from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class ScheduleItemNormalized:
    """Normalized schedule item from any provider.

    Produced by provider-specific schedule sources and consumed by
    the write port that resolves external_title_id → title_id and saves.
    """
    provider_code: str
    external_title_id: str      # provider's own ID (str, may be int-like)
    day_of_week: int | None     # 1=Monday … 7=Sunday; None = unknown/to be inferred
    air_dt: datetime | None     # UTC or tz-naive; None = unknown
    episode_label: str | None   # "7 серия", "1", etc.
    poster_url: str | None
    title_url: str | None
    raw: str | dict[str, Any] | None  # original payload from provider
    title_id: int | None = None  # internal DB title_id when the provider item is already mapped


@dataclass(frozen=True)
class ScheduleEntryDTO:
    """Single row returned by schedule.get (DB-only read)."""
    title_id: int
    day_of_week: int
    last_updated: str | None    # ISO-format string or None


@dataclass(frozen=True)
class ScheduleUpsertResult:
    """Result of writing schedule items to the DB."""
    upserted: int    # successfully saved/updated
    unresolved: int  # external_ids not found in TitleProviderMap
    # The actual items that could not be resolved — used by schedule_sync
    # to optionally fetch missing titles from the provider.
    unresolved_items: list[ScheduleItemNormalized] = field(default_factory=list)


@dataclass(frozen=True)
class ScheduleSyncResult:
    """Result returned by schedule.sync op."""
    ok: bool
    provider_code: str
    fetched: int
    upserted: int
    unresolved: int
    fetched_missing: int    # titles fetched from provider for previously unresolved items
    error: str | None
    # Items that should be shown outside the DB-backed day schedule:
    # provider announcements/future releases plus unresolved provider items.
    provider_items: list[ScheduleItemNormalized] = field(default_factory=list)
    unresolved_items: list[ScheduleItemNormalized] = field(default_factory=list)
