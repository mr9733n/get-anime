from tests.conftest import call_op


def test_animedia_search_external_ids_returns_many(backend):
    res = call_op(backend, "sync.search_external_ids", {
        "provider_code": "animedia",
        "query": "One Punch Man",
        "max_results": 10,
    })
    assert res["ok"] is True
    ids = res["result"]["external_ids"]
    assert isinstance(ids, list)
    assert len(ids) >= 3


def test_animedia_search_and_process_applies_limit(backend):
    res = call_op(backend, "sync.search_and_process", {
        "provider_code": "animedia",
        "query": "One Punch Man",
        "mode": "title",
        "max_results": 10,
        "limit": 3,
    })
    assert res["ok"] is True
    inner = res["result"]["result"]
    assert inner["ok"] is True
    assert len(inner["applied"]) == 3
    # важно: не должно быть storage_result false
    for a in inner["applied"]:
        ok, title_id = a["details"]["storage_result"]
        assert ok is True
        assert title_id is not None
