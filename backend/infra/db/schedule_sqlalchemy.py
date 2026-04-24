from __future__ import annotations

from datetime import datetime, timezone

from backend.core.dto.schedule import (
    ScheduleEntryDTO,
    ScheduleItemNormalized,
    ScheduleUpsertResult,
)
from backend.core.ports.schedule_port import IScheduleReadPort, IScheduleWritePort


class SqlAlchemyScheduleReadPort(IScheduleReadPort):
    """Reads schedule entries from the DB via DatabaseManager."""

    def __init__(self, db) -> None:
        self._db = db

    def get_schedule_by_day(self, day: int) -> list[ScheduleEntryDTO]:
        titles = self._db.get_titles_for_day(day) or []
        result: list[ScheduleEntryDTO] = []
        for title in titles:
            # Title ORM has schedules relationship; grab the matching row
            sched = next(
                (s for s in (title.schedules or []) if s.day_of_week == day),
                None,
            )
            last_updated = None
            if sched and sched.last_updated:
                lu = sched.last_updated
                if isinstance(lu, datetime):
                    last_updated = lu.isoformat()
                else:
                    last_updated = str(lu)

            result.append(
                ScheduleEntryDTO(
                    title_id=title.title_id,
                    day_of_week=day,
                    last_updated=last_updated,
                )
            )
        return result


class SqlAlchemyScheduleWritePort(IScheduleWritePort):
    """Resolves external IDs and upserts schedule rows via DatabaseManager."""

    def __init__(self, db) -> None:
        self._db = db

    def upsert_schedule(
        self, items: list[ScheduleItemNormalized]
    ) -> ScheduleUpsertResult:
        if not items:
            return ScheduleUpsertResult(upserted=0, unresolved=0)

        # Group by provider_code for batched resolution
        by_provider: dict[str, list[ScheduleItemNormalized]] = {}
        for item in items:
            by_provider.setdefault(item.provider_code, []).append(item)

        total_upserted = 0
        unresolved_items: list[ScheduleItemNormalized] = []

        for provider_code, group in by_provider.items():
            external_ids = [it.external_title_id for it in group]

            # Batch resolve: external_id (str) → internal title_id (int)
            resolved: dict[str, int] = self._db.get_title_ids_by_external_ids(
                provider_code, external_ids
            )

            for item in group:
                title_id = resolved.get(str(item.external_title_id))
                if title_id is None:
                    unresolved_items.append(item)
                    continue

                day = item.day_of_week
                if day is None:
                    # Infer day from air_dt if available
                    if item.air_dt is not None:
                        day = item.air_dt.isoweekday()  # 1=Mon … 7=Sun
                    else:
                        unresolved_items.append(item)
                        continue  # cannot store without a day

                try:
                    self._db.save_schedule(
                        day_of_week=day,
                        title_id=title_id,
                        last_updated=datetime.now(timezone.utc),
                    )
                    total_upserted += 1
                except Exception:
                    unresolved_items.append(item)

        return ScheduleUpsertResult(
            upserted=total_upserted,
            unresolved=len(unresolved_items),
            unresolved_items=unresolved_items,
        )
