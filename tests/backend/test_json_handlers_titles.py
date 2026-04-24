def test_titles_search_ok(backend, handlers):
    res = handlers["titles.search"](backend, {"query": "sakamoto"})
    assert res["ok"] is True
    dtos = res["result"]["titles"]
    assert isinstance(dtos, list)
    assert dtos[0]["query"] == "sakamoto"


def test_titles_get_single_ok(backend, handlers):
    res = handlers["titles.get"](backend, {"title_id": 2128})
    assert res["ok"] is True
    dtos = res["result"]["titles"]
    assert dtos[0]["title_id"] == 2128


def test_titles_get_batch_ok(backend, handlers):
    res = handlers["titles.get"](backend, {"title_ids": [2128, 2129]})
    assert res["ok"] is True
    dtos = res["result"]["titles"]
    assert [x["title_id"] for x in dtos] == [2128, 2129]


def test_titles_list_episodes_ok(backend, handlers):
    res = handlers["titles.list_episodes"](backend, {"title_id": 2128})
    assert res["ok"] is True
    eps = res["result"]["episodes"]
    assert eps[0]["title_id"] == 2128

def test_titles_update_ok(backend, handlers):
    res = handlers["titles.update"](backend, {
        "title_ids": [10089, 10322],
        "mode": "title",
        "max_results": 5
    })
    assert res["ok"] is True
    r = res["result"]["result"]
    assert r["ok"] is True
    assert "applied" in r


def test_titles_search_card_view(backend, handlers):
    res = handlers["titles.search"](backend, {"query": "sakamoto", "view": "card"})
    assert res["ok"] is True
    assert res["result"]["view"] == "card"
    dtos = res["result"]["titles"]
    assert dtos[0]["view"] == "card"


def test_titles_get_card_view(backend, handlers):
    res = handlers["titles.get"](backend, {"title_id": 2128, "view": "card"})
    assert res["ok"] is True
    assert res["result"]["view"] == "card"
    dtos = res["result"]["titles"]
    assert dtos[0]["view"] == "card"


def test_titles_get_view_defaults_to_full(backend, handlers):
    """view defaults to 'full' when not specified."""
    res = handlers["titles.get"](backend, {"title_id": 2128})
    assert res["ok"] is True
    assert res["result"]["view"] == "full"
    dtos = res["result"]["titles"]
    assert dtos[0]["view"] == "full"


def test_titles_get_unknown_view_falls_back_to_full(backend, handlers):
    """Unknown view value falls back to FULL gracefully."""
    res = handlers["titles.get"](backend, {"title_id": 2128, "view": "nonexistent"})
    assert res["ok"] is True
    assert res["result"]["view"] == "full"

