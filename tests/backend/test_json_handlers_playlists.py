def test_playlist_compose_ok(backend, handlers):
    res = handlers["playlist.compose"](backend, {"title_id": 1, "quality": "best"})
    assert res["ok"] is True
    assert "path" in res["result"]


def test_playlist_compose_multi_ok(backend, handlers):
    res = handlers["playlist.compose_multi"](backend, {
        "title_ids": [1, 2, 3],
        "quality": "best",
        "mode": "title",
        "name": "test",
        "preview_count": 3,
        "user_id": 42,
    })
    assert res["ok"] is True
    assert "path" in res["result"]
