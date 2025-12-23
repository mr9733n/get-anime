import time
import json
import httpx
import pytest

from providers.aniliberty.v1.transport import HttpTransport


class FakeResponse:
    def __init__(self, status_code=200, json_data=None, content=b"", headers=None):
        self.status_code = status_code
        self._json_data = json_data
        self.content = content
        self.headers = headers or {"Content-Type": "application/json"}
        self.text = content.decode("utf-8", errors="replace") if content else ""

    def raise_for_status(self):
        if self.status_code >= 400:
            # эмулируем поведение httpx
            req = httpx.Request("GET", "http://test")
            resp = httpx.Response(self.status_code, request=req)
            raise httpx.HTTPStatusError("error", request=req, response=resp)

    def json(self):
        if self._json_data is None:
            raise json.JSONDecodeError("no", "", 0)
        return self._json_data


class FakeHTTP:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def request(self, method, endpoint, **kwargs):
        self.calls.append((method, endpoint, kwargs))
        r = self.responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r

    def close(self):
        pass


class FakeNetClient:
    def __init__(self, fake_http):
        self.fake_http = fake_http

    def create_httpx_client(self, **kwargs):
        return self.fake_http


def test_transport_cache_hit():
    fake_http = FakeHTTP([
        FakeResponse(json_data={"ok": 1}),
    ])
    t = HttpTransport(
        net_client=FakeNetClient(fake_http),
        base_url="http://x",
        cache_policy=None,
        enable_dumps=False,
        max_cache_items=10,
    )

    # вручную задаём ttl через cache_ttl
    r1 = t.request_json("anime/releases/1", params={"a": 1}, cache_ttl=60)
    r2 = t.request_json("anime/releases/1", params={"a": 1}, cache_ttl=60)

    assert r1 == {"ok": 1}
    assert r2 == {"ok": 1}
    assert len(fake_http.calls) == 1  # второй раз взяли из кеша


def test_transport_retry_calls_sleep():
    calls = {"sleep": 0}

    def fake_sleep(_):
        calls["sleep"] += 1

    fake_http = FakeHTTP([
        httpx.RequestError("boom", request=httpx.Request("GET", "http://x")),
        httpx.RequestError("boom2", request=httpx.Request("GET", "http://x")),
        FakeResponse(json_data={"ok": 1}),
    ])

    t = HttpTransport(
        net_client=FakeNetClient(fake_http),
        base_url="http://x",
        sleep_fn=fake_sleep,
        enable_dumps=False,
    )

    r = t.request_json("anime/releases/1", attempts=3, backoff=0.01, cache_ttl=0)
    assert r == {"ok": 1}
    assert calls["sleep"] == 2  # между 1->2 и 2->3


def test_request_raw_returns_bytes():
    fake_http = FakeHTTP([
        FakeResponse(status_code=200, content=b"<rss></rss>", headers={"Content-Type": "application/xml"}),
    ])
    t = HttpTransport(net_client=FakeNetClient(fake_http), base_url="http://x")
    b = t.request_raw("anime/torrents/rss", params={"limit": 5})
    assert b == b"<rss></rss>"

def test_cache_disabled_when_ttl_zero():
    fake_http = FakeHTTP([
        FakeResponse(json_data={"ok": 1}),
        FakeResponse(json_data={"ok": 2}),
    ])
    t = HttpTransport(net_client=FakeNetClient(fake_http), base_url="http://x", enable_dumps=False)

    r1 = t.request_json("anime/releases/1", params={"a": 1}, cache_ttl=0)
    r2 = t.request_json("anime/releases/1", params={"a": 1}, cache_ttl=0)

    assert r1["ok"] == 1
    assert r2["ok"] == 2
    assert len(fake_http.calls) == 2

def test_request_json_http_status_error():
    fake_http = FakeHTTP([
        FakeResponse(status_code=503, json_data={"msg": "down"}),
    ])
    t = HttpTransport(net_client=FakeNetClient(fake_http), base_url="http://x", enable_dumps=False)

    out = t.request_json("anime/releases/1", params=None, method="GET", cache_ttl=0)
    assert isinstance(out, dict)
    assert out.get("error")  # зависит от твоего формата

def test_request_json_invalid_json_returns_error():
    fake_http = FakeHTTP([
        FakeResponse(status_code=200, json_data=None, content=b"not-json", headers={"Content-Type": "text/plain"}),
    ])
    t = HttpTransport(net_client=FakeNetClient(fake_http), base_url="http://x", enable_dumps=False)

    out = t.request_json("app/status", params=None, method="GET", cache_ttl=0)
    assert isinstance(out, dict)
    assert out.get("error")  # или проверяй "raw"/"text" — как у тебя сделано
