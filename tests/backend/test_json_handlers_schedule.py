import pytest


def test_schedule_get_ok(backend, handlers):
    res = handlers["schedule.get"](backend, {"day": 1})
    assert res["ok"] is True
    assert res["result"]["day"] == 1
    entries = res["result"]["entries"]
    assert isinstance(entries, list)
    assert len(entries) == 1
    assert entries[0]["day_of_week"] == 1
    assert entries[0]["title_id"] == 1


def test_schedule_get_day_5(backend, handlers):
    res = handlers["schedule.get"](backend, {"day": 5})
    assert res["ok"] is True
    assert res["result"]["day"] == 5
    assert res["result"]["entries"][0]["day_of_week"] == 5


def test_schedule_get_missing_day_raises(backend, handlers):
    with pytest.raises((ValueError, KeyError, TypeError)):
        handlers["schedule.get"](backend, {})


def test_schedule_sync_ok(backend, handlers):
    res = handlers["schedule.sync"](backend, {"provider_code": "aniliberty"})
    assert res["ok"] is True
    r = res["result"]["result"]
    assert r["ok"] is True
    assert r["provider_code"] == "aniliberty"
    assert r["fetched"] == 3
    assert r["upserted"] == 2
    assert r["unresolved"] == 1
    assert r["fetched_missing"] == 0
    assert r["error"] is None


def test_schedule_sync_with_day(backend, handlers):
    res = handlers["schedule.sync"](backend, {"provider_code": "animedia", "day": 3})
    assert res["ok"] is True
    r = res["result"]["result"]
    assert r["ok"] is True
    assert r["provider_code"] == "animedia"


def test_schedule_sync_fetch_unresolved(backend, handlers):
    """fetch_unresolved=true triggers lazy enrich for missing titles."""
    res = handlers["schedule.sync"](backend, {
        "provider_code": "aniliberty",
        "fetch_unresolved": True,
    })
    assert res["ok"] is True
    r = res["result"]["result"]
    assert r["ok"] is True
    assert r["fetched_missing"] == 1  # FakeScheduleController returns 1 when fetch_unresolved


def test_schedule_sync_missing_provider_raises(backend, handlers):
    with pytest.raises(ValueError):
        handlers["schedule.sync"](backend, {})
