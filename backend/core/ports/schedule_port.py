from __future__ import annotations

from typing import Protocol, runtime_checkable

from backend.core.dto.schedule import (
    ScheduleItemNormalized,
    ScheduleEntryDTO,
    ScheduleUpsertResult,
)


@runtime_checkable
class IScheduleReadPort(Protocol):
    """Read schedule entries from persistent storage (DB-only)."""

    def get_schedule_by_day(self, day: int) -> list[ScheduleEntryDTO]:
        """Return all titles scheduled on the given day (1=Mon … 7=Sun)."""
        ...


@runtime_checkable
class IScheduleWritePort(Protocol):
    """Resolve external IDs and upsert schedule rows."""

    def upsert_schedule(
        self, items: list[ScheduleItemNormalized]
    ) -> ScheduleUpsertResult:
        """
        For each item:
        1. Resolve external_title_id → internal title_id via TitleProviderMap.
        2. Upsert a Schedule row (day_of_week, title_id).
        3. Count unresolved items (external_id not in TitleProviderMap).
        """
        ...

    def replace_schedule(
        self,
        *,
        provider_code: str,
        items: list[ScheduleItemNormalized],
        days: set[int],
    ) -> ScheduleUpsertResult:
        """
        Replace provider-owned schedule rows for affected days.

        Rows for the same provider/day that are absent from `items` are removed.
        Rows for other providers are preserved.
        """
        ...


@runtime_checkable
class IProviderScheduleSource(Protocol):
    """Fetch and normalise schedule from a specific provider."""

    def get_schedule(
        self, *, day: int | None = None
    ) -> list[ScheduleItemNormalized]:
        """
        Fetch schedule from the provider.

        day: 1-7 (Mon-Sun); None = fetch all available days.
        Returns a list of normalised schedule items.
        """
        ...
