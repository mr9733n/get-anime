import logging
from providers.aniliberty.v1.adapter import APIAdapter


class FakeClient:
    def get_status(self):
        return {"ok": True}

    def get_release(self, rid):
        return {"id": rid, "title": "Test", "episodes": []}

    def get_latest_releases(self, limit=14):
        return [{"id": 1}, {"id": 2}]

    def search_releases(self, query):
        return [{"id": 3}]

    def get_random_releases(self):
        return [{"id": 4}]

    def get_release_by_id(self, rid):
        return self.get_release(rid)

    def get_release_by_alias(self, alias):
        return self.get_release(alias)

    def get_catalog_releases(self, **kwargs):
        return {"data": [{"id": 5}]}

    def get_torrents_rss(self, **kwargs):
        return b"<rss></rss>"

    def get_torrents_rss_for_release(self, rid, **kwargs):
        return b"<rss></rss>"


class FakeMapper:
    def __init__(self):
        self.stream_video_host = None

    def adapt_structure(self, raw):
        return {"id": raw.get("id"), "player": {"list": []}, "torrents": {"list": []}}

    def adapt_episode(self, ep):
        return ep

    def adapt_torrent(self, t):
        return t

    def adapt_team(self, m):
        return []

    def adapt_franchise(self, f):
        return f

    def adapt_rss_feed(self, xml):
        return {"items": [{"title": "torrent"}]}


def make_adapter():
    logger = logging.getLogger("test")
    adapter = APIAdapter(FakeClient(), logger)
    adapter.mapper = FakeMapper()  # подменяем реальный mapper
    adapter.service = None         # сервис тут не нужен
    return adapter


def test_get_app_status():
    ad = make_adapter()
    out = ad.get_app_status()
    assert out["ok"] is True


def test_get_search_by_alias():
    ad = make_adapter()
    out = ad.get_search_by_alias("naruto")
    assert "list" in out
    assert isinstance(out["list"], list)
    assert len(out["list"]) == 1
    assert out["list"][0]["id"] is not None

def test_get_latest_releases():
    ad = make_adapter()
    out = ad.get_latest_releases(limit=2)
    assert "list" in out
    assert len(out["list"]) == 2


def test_get_torrents_rss():
    ad = make_adapter()
    out = ad.get_torrents_rss()
    assert "items" in out
    assert out["items"][0]["title"] == "torrent"


def test_get_torrents_rss_for_release():
    ad = make_adapter()
    out = ad.get_torrents_rss_for_release(123)
    assert "items" in out

def test_adapter_propagates_error_dict():
    class Client:
        def get_status(self):
            return {"error": "boom"}

    ad = APIAdapter(Client(), logger=logging.getLogger("test"))
    out = ad.get_app_status()
    assert out == {"error": "boom"}

