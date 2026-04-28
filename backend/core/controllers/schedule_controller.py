from __future__ import annotations

from dataclasses import replace
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
        force_refresh: bool = False,
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

        if force_refresh:
            invalidate_cache = getattr(source, "invalidate_cache", None)
            if callable(invalidate_cache):
                try:
                    invalidate_cache()
                except Exception as exc:
                    self._logger.warning(
                        "schedule source cache invalidation failed for %s: %s",
                        provider_code,
                        exc,
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

        provider_only_items = [
            item for item in items
            if self._is_provider_only_item(provider_code, item)
        ]
        write_items = [
            item for item in items
            if not self._is_provider_only_item(provider_code, item)
        ]

        try:
            upsert_result = self._replace_or_upsert(
                provider_code=provider_code,
                items=write_items,
                day=day,
            )
        except Exception as exc:
            return ScheduleSyncResult(
                ok=False,
                provider_code=provider_code,
                fetched=len(items),
                upserted=0,
                unresolved=len(items),
                fetched_missing=0,
                error=str(exc),
                provider_items=list(items),
                unresolved_items=list(items),
            )

        fetched_missing = 0
        final_unresolved = upsert_result.unresolved
        final_unresolved_items = upsert_result.unresolved_items

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
                    final_unresolved_items = retry_result.unresolved_items
                except Exception as exc:
                    self._logger.warning(
                        "schedule retry upsert failed after fetch_missing: %s", exc
                    )

        provider_items = self._dedupe_provider_items(provider_only_items + final_unresolved_items)
        provider_items = self._with_resolved_title_ids(provider_code, provider_items)
        unresolved_items = self._with_resolved_title_ids(provider_code, final_unresolved_items)

        return ScheduleSyncResult(
            ok=True,
            provider_code=provider_code,
            fetched=len(items),
            upserted=upsert_result.upserted,
            unresolved=final_unresolved,
            fetched_missing=fetched_missing,
            error=None,
            provider_items=provider_items,
            unresolved_items=unresolved_items,
        )

    def provider_catalog(
        self,
        *,
        provider_code: str,
        max_titles: int = 120,
        pages: int = 5,
        load_more: bool = False,
    ) -> dict:
        source = self._sources.get(provider_code)
        if source is None:
            return {
                "ok": False,
                "provider_code": provider_code,
                "fetched": 0,
                "items": [],
                "error": f"No provider source registered for provider '{provider_code}'",
            }

        get_catalog = getattr(source, "get_catalog", None)
        if not callable(get_catalog):
            return {
                "ok": False,
                "provider_code": provider_code,
                "fetched": 0,
                "items": [],
                "error": f"Provider '{provider_code}' does not expose a catalog",
            }

        try:
            items = get_catalog(max_titles=max_titles, pages=pages, load_more=load_more)
            items = self._dedupe_provider_items(items)
            items = self._with_resolved_title_ids(provider_code, items)
            return {
                "ok": True,
                "provider_code": provider_code,
                "fetched": len(items),
                "items": items,
                "error": None,
            }
        except Exception as exc:
            return {
                "ok": False,
                "provider_code": provider_code,
                "fetched": 0,
                "items": [],
                "error": str(exc),
            }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _replace_or_upsert(
        self,
        *,
        provider_code: str,
        items: list[ScheduleItemNormalized],
        day: int | None,
    ):
        replace_schedule = getattr(self._write, "replace_schedule", None)
        if callable(replace_schedule):
            days = {int(day)} if day is not None else set(range(1, 8))
            return replace_schedule(
                provider_code=provider_code,
                items=items,
                days=days,
            )
        return self._write.upsert_schedule(items)

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
            fetch_external_id = self._fetch_external_id_for_item(provider_code, item)
            try:
                ok = self._fetch_title_fn(provider_code, fetch_external_id)
            except Exception as exc:
                self._logger.debug(
                    "fetch_title_fn failed for %s/%s: %s",
                    provider_code, fetch_external_id, exc,
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

    @staticmethod
    def _fetch_external_id_for_item(provider_code: str, item: ScheduleItemNormalized) -> str:
        external_id = str(item.external_title_id).strip()
        if provider_code != "animedia" or "@@" in external_id:
            return external_id

        raw = item.raw
        title = None
        if isinstance(raw, dict):
            title = raw.get("title") or raw.get("name") or raw.get("name_ru") or raw.get("name_en")

        if isinstance(title, str) and title.strip():
            return f"{external_id}@@{title.strip()}"

        return external_id

    @staticmethod
    def _is_provider_only_item(provider_code: str, item: ScheduleItemNormalized) -> bool:
        if provider_code != "animedia":
            return False

        raw = item.raw
        if not isinstance(raw, dict):
            return False

        section = raw.get("section")
        meta = raw.get("meta")
        section_text = str(section).strip().lower() if section is not None else ""
        meta_text = str(meta).strip().lower() if meta is not None else ""
        return section_text == "announcement" or "новая серия" in meta_text

    @staticmethod
    def _dedupe_provider_items(items: list[ScheduleItemNormalized]) -> list[ScheduleItemNormalized]:
        result: list[ScheduleItemNormalized] = []
        seen: set[tuple[str, str]] = set()
        for item in items:
            key = (str(item.provider_code), str(item.external_title_id))
            if key in seen:
                continue
            seen.add(key)
            result.append(item)
        return result

    def _with_resolved_title_ids(
        self,
        provider_code: str,
        items: list[ScheduleItemNormalized],
    ) -> list[ScheduleItemNormalized]:
        if not items:
            return items

        resolver = getattr(self._write, "resolve_provider_title_ids", None)
        if not callable(resolver):
            return items

        external_ids = [str(item.external_title_id) for item in items if item.external_title_id]
        try:
            resolved = resolver(provider_code, external_ids)
        except Exception as exc:
            self._logger.debug("provider title id resolution failed for %s: %s", provider_code, exc)
            return items

        return [
            replace(item, title_id=title_id) if (title_id := resolved.get(str(item.external_title_id))) is not None else item
            for item in items
        ]
