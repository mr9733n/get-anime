from tests.conftest import call_op


def test_aniliberty_search_external_ids_not_empty(backend):
    res = call_op(backend, "sync.search_external_ids", {
        "provider_code": "aniliberty",
        "query": "One Punch Man",
        "max_results": 10,
    })
    assert res["ok"] is True
    ids = res["result"]["external_ids"]
    assert len(ids) > 0


def test_aniliberty_search_and_process_not_no_candidates(backend):
    res = call_op(backend, "sync.search_and_process", {
        "provider_code": "aniliberty",
        "query": "One Punch Man",
        "mode": "title",
        "max_results": 10,
        "limit": 3,
    })
    assert res["ok"] is True
    inner = res["result"]["result"]
    assert inner["ok"] is True
    assert inner["error"] is None
    assert len(inner["applied"]) == 3
