import pytest


# ---------------------------------------------------------------------------
# history.mark_watched
# ---------------------------------------------------------------------------

def test_mark_watched_episode_ok(backend, handlers):
    res = handlers["history.mark_watched"](backend, {
        "title_id": 10,
        "episode_id": 5,
        "is_watched": True,
    })
    assert res["ok"] is True
    r = res["result"]["result"]
    assert r["ok"] is True
    assert r["title_id"] == 10
    assert r["episode_id"] == 5
    assert r["is_watched"] is True
    assert r["error"] is None


def test_mark_watched_unwatch(backend, handlers):
    res = handlers["history.mark_watched"](backend, {
        "title_id": 7,
        "episode_id": 2,
        "is_watched": False,
    })
    assert res["ok"] is True
    r = res["result"]["result"]
    assert r["is_watched"] is False


def test_mark_watched_no_episode_id(backend, handlers):
    """episode_id is optional — marks the whole title watched."""
    res = handlers["history.mark_watched"](backend, {
        "title_id": 3,
    })
    assert res["ok"] is True
    r = res["result"]["result"]
    assert r["title_id"] == 3
    assert r["episode_id"] is None


def test_mark_watched_missing_title_id_raises(backend, handlers):
    with pytest.raises((ValueError, KeyError, TypeError)):
        handlers["history.mark_watched"](backend, {})


def test_mark_watched_uses_ctx_user_id(backend, handlers):
    """Default user_id comes from backend.ctx.user_id (42)."""
    res = handlers["history.mark_watched"](backend, {"title_id": 1})
    assert res["ok"] is True


def test_mark_watched_explicit_user_id(backend, handlers):
    res = handlers["history.mark_watched"](backend, {
        "user_id": 99,
        "title_id": 1,
        "episode_id": 1,
    })
    assert res["ok"] is True
    # FakeHistoryController echoes params back
    r = res["result"]["result"]
    assert r["ok"] is True


# ---------------------------------------------------------------------------
# history.mark_all_watched
# ---------------------------------------------------------------------------

def test_mark_all_watched_ok(backend, handlers):
    res = handlers["history.mark_all_watched"](backend, {
        "title_id": 20,
        "is_watched": True,
    })
    assert res["ok"] is True
    r = res["result"]["result"]
    assert r["ok"] is True
    assert r["title_id"] == 20
    assert r["is_watched"] is True
    assert r["episodes_affected"] == 0  # no episode_ids passed → 0


def test_mark_all_watched_with_episode_ids(backend, handlers):
    res = handlers["history.mark_all_watched"](backend, {
        "title_id": 20,
        "is_watched": True,
        "episode_ids": [1, 2, 3],
    })
    assert res["ok"] is True
    r = res["result"]["result"]
    assert r["episodes_affected"] == 3


def test_mark_all_watched_unwatch(backend, handlers):
    res = handlers["history.mark_all_watched"](backend, {
        "title_id": 5,
        "is_watched": False,
    })
    assert res["ok"] is True
    r = res["result"]["result"]
    assert r["is_watched"] is False


def test_mark_all_watched_missing_title_id_raises(backend, handlers):
    with pytest.raises((ValueError, KeyError, TypeError)):
        handlers["history.mark_all_watched"](backend, {})


def test_mark_all_watched_bad_episode_ids_raises(backend, handlers):
    """episode_ids must be a list if provided."""
    with pytest.raises((ValueError, TypeError)):
        handlers["history.mark_all_watched"](backend, {
            "title_id": 1,
            "episode_ids": "not-a-list",
        })


# ---------------------------------------------------------------------------
# history.set_need_to_see
# ---------------------------------------------------------------------------

def test_set_need_to_see_true(backend, handlers):
    res = handlers["history.set_need_to_see"](backend, {
        "title_id": 15,
        "need_to_see": True,
    })
    assert res["ok"] is True
    r = res["result"]["result"]
    assert r["ok"] is True
    assert r["title_id"] == 15
    assert r["need_to_see"] is True
    assert r["error"] is None


def test_set_need_to_see_false(backend, handlers):
    res = handlers["history.set_need_to_see"](backend, {
        "title_id": 15,
        "need_to_see": False,
    })
    assert res["ok"] is True
    r = res["result"]["result"]
    assert r["need_to_see"] is False


def test_set_need_to_see_default_true(backend, handlers):
    """need_to_see defaults to True when not provided."""
    res = handlers["history.set_need_to_see"](backend, {"title_id": 8})
    assert res["ok"] is True
    r = res["result"]["result"]
    assert r["need_to_see"] is True


def test_set_need_to_see_missing_title_id_raises(backend, handlers):
    with pytest.raises((ValueError, KeyError, TypeError)):
        handlers["history.set_need_to_see"](backend, {})


def test_set_need_to_see_explicit_user_id(backend, handlers):
    res = handlers["history.set_need_to_see"](backend, {
        "user_id": 77,
        "title_id": 1,
        "need_to_see": True,
    })
    assert res["ok"] is True
