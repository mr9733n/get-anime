def test_streams_get_ok(backend, handlers):
    res = handlers["streams.get"](backend, {"title_id": 2128, "episode_number": 1})
    assert res["ok"] is True

    stream = res["result"]["stream"]
    assert stream["title_id"] == 2128
    assert stream["episode_number"] == 1
