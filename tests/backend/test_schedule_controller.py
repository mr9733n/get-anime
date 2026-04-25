"""
Unit tests for ScheduleController.

Covers the three areas flagged in the roadmap:
  1. Day / week API mapping  — day param forwarded to source correctly
  2. Unresolved titles       — items not in TitleProviderMap are counted,
                               forwarded as unresolved_items, reflected in result
  3. Retry after lazy fetch  — fetch_unresolved=True: fetch_title_fn called for
                               every unresolved item, successful ones re-upserted,
                               counters merged correctly

No real DB or network.  All fakes are inline.
"""
from __future__ import annotations

from datetime import datetime

import pytest

from backend.core.controllers.schedule_controller import ScheduleController
from backend.core.dto.schedule import (
    ScheduleEntryDTO,
    ScheduleItemNormalized,
    ScheduleSyncResult,
    ScheduleUpsertResult,
)


# ---------------------------------------------------------------------------
# Helpers — minimal fake data
# ---------------------------------------------------------------------------

def make_item(
    external_title_id: str,
    day_of_week: int = 1,
    provider_code: str = "aniliberty",
) -> ScheduleItemNormalized:
    return ScheduleItemNormalized(
        provider_code=provider_code,
        external_title_id=external_title_id,
        day_of_week=day_of_week,
        air_dt=None,
        episode_label=None,
        poster_url=None,
        title_url=None,
        raw=None,
    )


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------

class FakeReadPort:
    def get_schedule_by_day(self, day: int) -> list[ScheduleEntryDTO]:
        return [ScheduleEntryDTO(title_id=1, day_of_week=day, last_updated=None)]


class FakeSource:
    """Configurable provider schedule source."""

    def __init__(self, items: list[ScheduleItemNormalized] | None = None, raise_exc: Exception | None = None):
        self.items = items or []
        self.raise_exc = raise_exc
        self.calls: list[int | None] = []  # day args received

    def get_schedule(self, *, day: int | None = None) -> list[ScheduleItemNormalized]:
        self.calls.append(day)
        if self.raise_exc:
            raise self.raise_exc
        return list(self.items)


class FakeWritePort:
    """
    Configurable write port.

    resolved_ids: set of external_title_ids that resolve successfully.
    Everything else goes to unresolved_items.
    """

    def __init__(self, resolved_ids: set[str] | None = None):
        self.resolved_ids: set[str] = resolved_ids or set()
        self.calls: list[list[ScheduleItemNormalized]] = []

    def upsert_schedule(self, items: list[ScheduleItemNormalized]) -> ScheduleUpsertResult:
        self.calls.append(list(items))
        upserted = 0
        unresolved_items = []
        for item in items:
            if item.external_title_id in self.resolved_ids:
                upserted += 1
            else:
                unresolved_items.append(item)
        return ScheduleUpsertResult(
            upserted=upserted,
            unresolved=len(unresolved_items),
            unresolved_items=unresolved_items,
        )


class FakeFetchTitleFn:
    """Records calls and returns configurable ok/fail per external_id."""

    def __init__(self, ok_ids: set[str] | None = None):
        self.ok_ids: set[str] = ok_ids or set()
        self.calls: list[tuple[str, str]] = []  # (provider_code, external_id)

    def __call__(self, provider_code: str, external_id: str) -> bool:
        self.calls.append((provider_code, external_id))
        return external_id in self.ok_ids


def make_controller(
    items: list[ScheduleItemNormalized] | None = None,
    resolved_ids: set[str] | None = None,
    fetch_fn: FakeFetchTitleFn | None = None,
    provider_code: str = "aniliberty",
    source_raise: Exception | None = None,
) -> tuple[ScheduleController, FakeSource, FakeWritePort]:
    source = FakeSource(items=items, raise_exc=source_raise)
    write = FakeWritePort(resolved_ids=resolved_ids)
    ctrl = ScheduleController(
        read_port=FakeReadPort(),
        write_port=write,
        sources={provider_code: source},
        fetch_title_fn=fetch_fn,
    )
    return ctrl, source, write


# ---------------------------------------------------------------------------
# 1. Day / week API mapping
# ---------------------------------------------------------------------------

class TestDayWeekMapping:
    """The day parameter (or None) must be forwarded verbatim to the source."""

    def test_day_forwarded_to_source(self):
        ctrl, source, _ = make_controller()
        ctrl.schedule_sync(provider_code="aniliberty", day=3)
        assert source.calls == [3]

    def test_day_1_forwarded(self):
        ctrl, source, _ = make_controller()
        ctrl.schedule_sync(provider_code="aniliberty", day=1)
        assert source.calls == [1]

    def test_day_7_forwarded(self):
        ctrl, source, _ = make_controller()
        ctrl.schedule_sync(provider_code="aniliberty", day=7)
        assert source.calls == [7]

    def test_none_day_means_all_week(self):
        """No day param → full week fetch (day=None passed to source)."""
        ctrl, source, _ = make_controller()
        ctrl.schedule_sync(provider_code="aniliberty", day=None)
        assert source.calls == [None]

    def test_default_day_is_none(self):
        """schedule_sync(provider_code=...) without day → all-week."""
        ctrl, source, _ = make_controller()
        ctrl.schedule_sync(provider_code="aniliberty")
        assert source.calls == [None]

    def test_result_fetched_count_matches_items(self):
        items = [make_item("ext-1"), make_item("ext-2"), make_item("ext-3")]
        ctrl, _, _ = make_controller(items=items, resolved_ids={"ext-1", "ext-2", "ext-3"})
        result = ctrl.schedule_sync(provider_code="aniliberty")
        assert result.fetched == 3

    def test_empty_source_returns_zero_counts(self):
        ctrl, _, _ = make_controller(items=[])
        result = ctrl.schedule_sync(provider_code="aniliberty")
        assert result.ok is True
        assert result.fetched == 0
        assert result.upserted == 0
        assert result.unresolved == 0


# ---------------------------------------------------------------------------
# 2. Unresolved titles
# ---------------------------------------------------------------------------

class TestUnresolvedTitles:
    """Items whose external_title_id has no DB mapping are tracked."""

    def test_all_resolved(self):
        items = [make_item("a"), make_item("b")]
        ctrl, _, _ = make_controller(items=items, resolved_ids={"a", "b"})
        result = ctrl.schedule_sync(provider_code="aniliberty")
        assert result.upserted == 2
        assert result.unresolved == 0

    def test_none_resolved(self):
        items = [make_item("a"), make_item("b")]
        ctrl, _, _ = make_controller(items=items, resolved_ids=set())
        result = ctrl.schedule_sync(provider_code="aniliberty")
        assert result.upserted == 0
        assert result.unresolved == 2

    def test_partial_resolve(self):
        items = [make_item("a"), make_item("b"), make_item("c")]
        ctrl, _, _ = make_controller(items=items, resolved_ids={"a", "c"})
        result = ctrl.schedule_sync(provider_code="aniliberty")
        assert result.upserted == 2
        assert result.unresolved == 1

    def test_unresolved_does_not_affect_ok_flag(self):
        """Unresolved items are not an error — ok=True as long as sync succeeded."""
        items = [make_item("unknown-1"), make_item("unknown-2")]
        ctrl, _, _ = make_controller(items=items, resolved_ids=set())
        result = ctrl.schedule_sync(provider_code="aniliberty")
        assert result.ok is True
        assert result.error is None

    def test_unknown_provider_returns_ok_false(self):
        ctrl, _, _ = make_controller()
        result = ctrl.schedule_sync(provider_code="unknown_provider")
        assert result.ok is False
        assert "unknown_provider" in (result.error or "")

    def test_source_exception_returns_ok_false(self):
        ctrl, _, _ = make_controller(source_raise=RuntimeError("network down"))
        result = ctrl.schedule_sync(provider_code="aniliberty")
        assert result.ok is False
        assert "network down" in (result.error or "")

    def test_fetched_missing_is_zero_without_fetch_unresolved(self):
        """fetch_unresolved defaults to False; fetched_missing must be 0."""
        items = [make_item("no-such-title")]
        ctrl, _, _ = make_controller(items=items, resolved_ids=set())
        result = ctrl.schedule_sync(provider_code="aniliberty")
        assert result.fetched_missing == 0

    def test_write_port_receives_all_items(self):
        items = [make_item("a"), make_item("b")]
        ctrl, _, write = make_controller(items=items, resolved_ids={"a"})
        ctrl.schedule_sync(provider_code="aniliberty")
        assert len(write.calls) == 1
        sent = write.calls[0]
        assert {i.external_title_id for i in sent} == {"a", "b"}


# ---------------------------------------------------------------------------
# 3. Retry after lazy fetch (fetch_unresolved=True)
# ---------------------------------------------------------------------------

class TestFetchUnresolvedAndRetry:
    """
    When fetch_unresolved=True and fetch_title_fn is set:
    - fetch_title_fn called for every unresolved item
    - Successful items re-upserted (second upsert_schedule call)
    - Counters from both upserts are merged
    - fetched_missing == number of titles successfully fetched
    """

    def test_all_missing_fetched_and_retried(self):
        items = [make_item("x"), make_item("y")]
        # First upsert: x and y are unresolved
        # After fetch: both are now resolvable (second upsert resolves them)
        write = FakeWritePort(resolved_ids=set())
        fetch_fn = FakeFetchTitleFn(ok_ids={"x", "y"})

        # Simulate: after fetch_title_fn, write port now knows x and y
        # We need write to resolve on second call → update resolved_ids
        call_count = [0]
        original_upsert = write.upsert_schedule

        def smart_upsert(items_arg):
            call_count[0] += 1
            if call_count[0] == 1:
                # first call: all unresolved
                return ScheduleUpsertResult(
                    upserted=0,
                    unresolved=2,
                    unresolved_items=list(items_arg),
                )
            else:
                # second call: retry, now resolved
                return ScheduleUpsertResult(
                    upserted=len(items_arg),
                    unresolved=0,
                    unresolved_items=[],
                )

        write.upsert_schedule = smart_upsert

        source = FakeSource(items=items)
        ctrl = ScheduleController(
            read_port=FakeReadPort(),
            write_port=write,
            sources={"aniliberty": source},
            fetch_title_fn=fetch_fn,
        )

        result = ctrl.schedule_sync(
            provider_code="aniliberty",
            fetch_unresolved=True,
        )

        assert result.fetched_missing == 2
        assert result.upserted == 2
        assert result.unresolved == 0
        assert result.ok is True

    def test_partial_fetch_success(self):
        """fetch_title_fn succeeds for some, fails for others."""
        item_a = make_item("a")
        item_b = make_item("b")
        items = [item_a, item_b]

        call_count = [0]

        class SmartWrite:
            calls = []

            def upsert_schedule(self, items_arg):
                self.calls.append(list(items_arg))
                call_count[0] += 1
                if call_count[0] == 1:
                    # first call: both unresolved
                    return ScheduleUpsertResult(
                        upserted=0,
                        unresolved=2,
                        unresolved_items=list(items_arg),
                    )
                else:
                    # retry call: only "a" was fetched → only "a" in retry
                    # "a" resolves; no "b" here
                    return ScheduleUpsertResult(
                        upserted=len(items_arg),
                        unresolved=0,
                        unresolved_items=[],
                    )

        write = SmartWrite()
        fetch_fn = FakeFetchTitleFn(ok_ids={"a"})  # only "a" succeeds
        source = FakeSource(items=items)
        ctrl = ScheduleController(
            read_port=FakeReadPort(),
            write_port=write,
            sources={"aniliberty": source},
            fetch_title_fn=fetch_fn,
        )

        result = ctrl.schedule_sync(
            provider_code="aniliberty",
            fetch_unresolved=True,
        )

        # fetched_missing = 1 (only "a")
        assert result.fetched_missing == 1
        # fetch_title_fn was called for both "a" and "b"
        assert set(eid for _, eid in fetch_fn.calls) == {"a", "b"}
        # retry only submitted "a" — write received 2 calls
        assert len(write.calls) == 2
        retry_ids = {i.external_title_id for i in write.calls[1]}
        assert retry_ids == {"a"}

    def test_no_fetch_when_fetch_unresolved_false(self):
        """fetch_title_fn must NOT be called when fetch_unresolved=False."""
        items = [make_item("missing")]
        fetch_fn = FakeFetchTitleFn(ok_ids={"missing"})
        ctrl, _, _ = make_controller(
            items=items,
            resolved_ids=set(),
            fetch_fn=fetch_fn,
        )

        ctrl.schedule_sync(provider_code="aniliberty", fetch_unresolved=False)
        assert fetch_fn.calls == []

    def test_fetch_unresolved_without_fetch_fn_does_not_crash(self):
        """fetch_unresolved=True without fetch_title_fn → graceful no-op."""
        items = [make_item("missing")]
        source = FakeSource(items=items)
        write = FakeWritePort(resolved_ids=set())
        ctrl = ScheduleController(
            read_port=FakeReadPort(),
            write_port=write,
            sources={"aniliberty": source},
            fetch_title_fn=None,  # intentionally no fn
        )

        result = ctrl.schedule_sync(provider_code="aniliberty", fetch_unresolved=True)
        assert result.ok is True
        assert result.fetched_missing == 0

    def test_fetch_fn_exception_does_not_abort_other_items(self):
        """If fetch_title_fn raises for one item, remaining items are still processed."""
        items = [make_item("bad"), make_item("good")]

        call_count = [0]

        def flaky_fetch(provider_code: str, ext_id: str) -> bool:
            if ext_id == "bad":
                raise RuntimeError("network timeout")
            return True

        write_calls = []

        class TrackingWrite:
            def upsert_schedule(self, items_arg):
                write_calls.append(list(items_arg))
                call_count[0] += 1
                if call_count[0] == 1:
                    return ScheduleUpsertResult(
                        upserted=0,
                        unresolved=2,
                        unresolved_items=list(items_arg),
                    )
                return ScheduleUpsertResult(
                    upserted=len(items_arg),
                    unresolved=0,
                    unresolved_items=[],
                )

        source = FakeSource(items=items)
        ctrl = ScheduleController(
            read_port=FakeReadPort(),
            write_port=TrackingWrite(),
            sources={"aniliberty": source},
            fetch_title_fn=flaky_fetch,
        )

        result = ctrl.schedule_sync(provider_code="aniliberty", fetch_unresolved=True)

        # "good" was fetched successfully despite "bad" raising
        assert result.fetched_missing == 1
        assert result.ok is True

    def test_write_port_not_called_twice_when_nothing_fetched(self):
        """If fetch_title_fn fails for all items, the retry upsert is skipped."""
        items = [make_item("none-will-resolve")]
        write = FakeWritePort(resolved_ids=set())
        fetch_fn = FakeFetchTitleFn(ok_ids=set())  # always fails

        source = FakeSource(items=items)
        ctrl = ScheduleController(
            read_port=FakeReadPort(),
            write_port=write,
            sources={"aniliberty": source},
            fetch_title_fn=fetch_fn,
        )

        ctrl.schedule_sync(provider_code="aniliberty", fetch_unresolved=True)
        # Only one upsert call (no retry when retry_items is empty)
        assert len(write.calls) == 1


# ---------------------------------------------------------------------------
# 4. schedule_get pass-through
# ---------------------------------------------------------------------------

class TestScheduleGet:
    def test_returns_entries_for_day(self):
        source = FakeSource()
        write = FakeWritePort()
        ctrl = ScheduleController(
            read_port=FakeReadPort(),
            write_port=write,
            sources={},
        )
        entries = ctrl.schedule_get(day=2)
        assert len(entries) == 1
        assert entries[0].day_of_week == 2
        assert entries[0].title_id == 1
