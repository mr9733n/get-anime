def test_sync_search_external_ids_ok(backend, handlers):
    res = handlers["sync.search_external_ids"](backend, {
        "provider_code": "aniliberty",
        "query": "One Punch Man",
        "max_results": 10
    })
    assert res["ok"] is True
    assert res["result"]["external_ids"] == [1, 2, 3]


def test_sync_fetch_payload_ok(backend, handlers):
    res = handlers["sync.fetch_payload"](backend, {
        "provider_code": "animedia",
        "query": "One Punch Man",
        "max_results": 10
    })
    assert res["ok"] is True
    p = res["result"]["payload"]
    assert p["provider_code"] == "animedia"
    assert p["query"] == "One Punch Man"


def test_sync_fetch_and_process_ok(backend, handlers):
    res = handlers["sync.fetch_and_process"](backend, {
        "provider_code": "animedia",
        "query": "One Punch Man",
        "mode": "title",
        "max_results": 1
    })
    assert res["ok"] is True
    r = res["result"]["result"]
    assert r["provider_code"] == "animedia"
    assert r["mode"] == "title"


def test_sync_search_and_process_ok(backend, handlers):
    res = handlers["sync.search_and_process"](backend, {
        "provider_code": "aniliberty",
        "query": "One Punch Man",
        "mode": "title",
        "max_results": 10,
        "limit": 5
    })
    assert res["ok"] is True

    r = res["result"]["result"]
    assert r["ok"] is True
    assert r["provider_code"] == "aniliberty"
    assert r["query"] == "One Punch Man"
    assert isinstance(r["applied"], list)
    assert len(r["applied"]) == 5
