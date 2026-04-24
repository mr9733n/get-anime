from __future__ import annotations

import logging
from typing import Callable

from backend.core.dto.schedule import (
    ScheduleEntryDTO,
    ScheduleSyncResult,
    ScheduleItemNormalized,
)
from backend.core.ports.schedule_port import (
    IScheduleReadPort,
    IScheduleWritePort,
    IProviderScheduleSource,
)

# Sync callable: (provider_code, external_title_id) → True if title was saved
FetchTitleFn = Callable[[str, str], bool]


class ScheduleController:
    """
    Orchestrates schedule read and sync operations.

    schedule_get  → DB-only, no network
    schedule_sync → provider → normalize → upsert into DB
                    (optionally: fetch missing titles before upserting)
    """

    def __init__(
        self,
        read_port: IScheduleReadPort,
        write_port: IScheduleWritePort,
        sources: dict[str, IProviderScheduleSource] | None = None,
        fetch_title_fn: FetchTitleFn | None = None,
    ) -> None:
        self._read = read_port
        self._write = write_port
        self._sources: dict[str, IProviderScheduleSource] = sources or {}
        self._fetch_title_fn = fetch_title_fn
        self._logger = logging.getLogger(__name__)

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def schedule_get(self, *, day: int) -> list[ScheduleEntryDTO]:
        """Return schedule entries for the given day from the DB."""
        return self._read.get_schedule_by_day(day)

    # ------------------------------------------------------------------
    # Sync
    # ------------------------------------------------------------------

    def schedule_sync(
        self,
        *,
        provider_code: str,
        day: int | None = None,
        fetch_unresolved: bool = False,
    ) -> ScheduleSyncResult:
        """
        Fetch schedule from *provider_code*, normalise, upsert into DB.

        provider_code:     registered source key ("aniliberty", "animedia")
        day:               1-7 or None (fetch all available days)
        fetch_unresolved:  if True and fetch_title_fn is wired, attempt to
                           fetch+save missing titles from the provider, then
                           retry the schedule upsert for those items.
        """
        source = self._sources.get(provider_code)
        if source is None:
            return ScheduleSyncResult(
                ok=False,
                provider_code=provider_code,
                fetched=0,
                upserted=0,
                unresolved=0,
                fetched_missing=0,
                error=f"No schedule source registered for provider '{provider_code}'",
            )

        try:
            items = source.get_schedule(day=day)
        except Exception as exc:
            return ScheduleSyncResult(
                ok=False,
                provider_code=provider_code,
                fetched=0,
                upserted=0,
                unresolved=0,
                fetched_missing=0,
                error=str(exc),
            )

        if not items:
            return ScheduleSyncResult(
                ok=True,
                provider_code=provider_code,
                fetched=0,
                upserted=0,
                unresolved=0,
                fetched_missing=0,
                error=None,
            )

        try:
            upsert_result = self._write.upsert_schedule(items)
        except Exception as exc:
            return ScheduleSyncResult(
                ok=False,
                provider_code=provider_code,
                fetched=len(items),
                upserted=0,
                unresolved=len(items),
                fetched_missing=0,
                error=str(exc),
            )

        fetched_missing = 0
        final_unresolved = upsert_result.unresolved

        # ── Lazy enrich: fetch missing titles then retry upsert ───────────
        if (
            fetch_unresolved
            and upsert_result.unresolved_items
            and self._fetch_title_fn is not None
        ):
            fetched_missing, retry_items = self._fetch_missing(
                provider_code, upsert_result.unresolved_items
            )

            if retry_items:
                try:
                    retry_result = self._write.upsert_schedule(retry_items)
                    upsert_result = type(upsert_result)(
                        upserted=upsert_result.upserted + retry_result.upserted,
                        unresolved=retry_result.unresolved,
                        unresolved_items=retry_result.unresolved_items,
                    )
                    final_unresolved = retry_result.unresolved
                except Exception as exc:
                    self._logger.warning(
                        "schedule retry upsert failed after fetch_missing: %s", exc
                    )

        return ScheduleSyncResult(
            ok=True,
            provider_code=provider_code,
            fetched=len(items),
            upserted=upsert_result.upserted,
            unresolved=final_unresolved,
            fetched_missing=fetched_missing,
            error=None,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _fetch_missing(
        self,
        provider_code: str,
        unresolved: list[ScheduleItemNormalized],
    ) -> tuple[int, list[ScheduleItemNormalized]]:
        """
        Call fetch_title_fn for each unresolved item.

        Returns:
            (fetched_count, items_that_were_successfully_fetched)
        """
        assert self._fetch_title_fn is not None

        fetched_count = 0
        retry_items: list[ScheduleItemNormalized] = []

        for item in unresolved:
            try:
                ok = self._fetch_title_fn(provider_code, item.external_title_id)
            except Exception as exc:
                self._logger.debug(
                    "fetch_title_fn failed for %s/%s: %s",
                    provider_code, item.external_title_id, exc,
                )
                ok = False

            if ok:
                fetched_count += 1
                retry_items.append(item)
            else:
                self._logger.debug(
                    "Could not fetch missing title %s/%s — leaving unresolved",
                    provider_code, item.external_title_id,
                )

        return fetched_count, retry_items
