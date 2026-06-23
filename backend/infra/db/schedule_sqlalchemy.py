from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select

from backend.core.dto.schedule import (
    ScheduleEntryDTO,
    ScheduleItemNormalized,
    ScheduleUpsertResult,
)
from backend.core.ports.schedule_port import IScheduleReadPort, IScheduleWritePort
from storage.tables import Provider, Schedule, Title, TitleProviderMap


class SqlAlchemyScheduleReadPort(IScheduleReadPort):
    """Reads schedule entries from the DB via DatabaseManager."""

    def __init__(self, db) -> None:
        self._db = db

    def get_schedule_by_day(self, day: int) -> list[ScheduleEntryDTO]:
        with self._db.Session() as session:
            schedules = (
                session.query(Schedule)
                .join(Title, Title.title_id == Schedule.title_id)
                .filter(Schedule.day_of_week == int(day))
                .filter(Title.is_deleted == False)
                .order_by(Schedule.title_id.asc())
                .all()
            )

        result: list[ScheduleEntryDTO] = []
        for sched in schedules:
            last_updated = None
            if sched.last_updated:
                lu = sched.last_updated
                if isinstance(lu, datetime):
                    last_updated = lu.isoformat()
                else:
                    last_updated = str(lu)

            result.append(
                ScheduleEntryDTO(
                    title_id=int(sched.title_id),
                    day_of_week=int(sched.day_of_week),
                    last_updated=last_updated,
                )
            )
        return result


class SqlAlchemyScheduleWritePort(IScheduleWritePort):
    """Resolves external IDs and upserts schedule rows via DatabaseManager."""

    def __init__(self, db) -> None:
        self._db = db

    def resolve_provider_title_ids(
        self,
        provider_code: str,
        external_ids: list[str],
    ) -> dict[str, int]:
        external_ids = [str(x) for x in (external_ids or []) if x]
        if not external_ids:
            return {}

        with self._db.Session() as session:
            rows = (
                session.query(TitleProviderMap.external_title_id, TitleProviderMap.title_id)
                .join(Provider, Provider.provider_id == TitleProviderMap.provider_id)
                .filter(Provider.code == provider_code)
                .filter(TitleProviderMap.external_title_id.in_(external_ids))
                .all()
            )
            return {str(ext): int(title_id) for ext, title_id in rows}

    def replace_schedule(
        self,
        *,
        provider_code: str,
        items: list[ScheduleItemNormalized],
        days: set[int],
    ) -> ScheduleUpsertResult:
        """Replace provider-owned schedule rows for the affected days."""
        days = {int(day) for day in days if 1 <= int(day) <= 7}
        if not days:
            return ScheduleUpsertResult(upserted=0, unresolved=len(items), unresolved_items=list(items))

        external_ids = [str(item.external_title_id) for item in items if item.external_title_id]
        now = datetime.now(timezone.utc)

        resolved = self.resolve_provider_title_ids(provider_code, external_ids)

        with self._db.Session() as session:
            current_keys: set[tuple[int, int]] = set()
            unresolved_items: list[ScheduleItemNormalized] = []

            for item in items:
                title_id = resolved.get(str(item.external_title_id))
                if title_id is None:
                    unresolved_items.append(item)
                    continue

                day = item.day_of_week
                if day is None and item.air_dt is not None:
                    day = item.air_dt.isoweekday()
                if day is None or int(day) not in days:
                    unresolved_items.append(item)
                    continue

                current_keys.add((int(day), int(title_id)))

            provider_title_ids = (
                select(TitleProviderMap.title_id)
                .join(Provider, Provider.provider_id == TitleProviderMap.provider_id)
                .where(Provider.code == provider_code)
            )
            existing = (
                session.query(Schedule)
                .filter(Schedule.day_of_week.in_(days))
                .filter(Schedule.title_id.in_(provider_title_ids))
                .all()
            )
            for schedule in existing:
                key = (int(schedule.day_of_week), int(schedule.title_id))
                if key not in current_keys:
                    session.delete(schedule)

            for day, title_id in current_keys:
                session.merge(
                    Schedule(
                        day_of_week=day,
                        title_id=title_id,
                        last_updated=now,
                    )
                )

            session.commit()

        return ScheduleUpsertResult(
            upserted=len(current_keys),
            unresolved=len(unresolved_items),
            unresolved_items=unresolved_items,
        )

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
