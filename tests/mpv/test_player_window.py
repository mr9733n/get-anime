import time
import pytest
import logging
logging.getLogger(__name__).setLevel(logging.CRITICAL)

from app.mpv.player_window import PlayerWindow
from app.mpv.base_engine import PlaybackState


class FakeEngine:
    """Мини-реализация PlayerEngine для тестов PlayerWindow без mpv."""
    def __init__(self):
        self.on_eof = None
        self.on_error = None
        self._shutdown_calls = 0
        self._loaded = []
        self._playing = False
        self._seekable = True
        self._time_ms = 0
        self._length_ms = 10_000
        self._volume = 100
        self.last_end_reason = "eof"

    # ---- methods PlayerWindow expects ----
    def set_video_widget(self, wid: int) -> None:
        pass

    def load(self, url: str) -> None:
        self._loaded.append(url)
        self._playing = True
        self._time_ms = 0

    def play(self) -> None:
        self._playing = True

    def pause(self) -> None:
        self._playing = False

    def toggle_pause(self) -> None:
        self._playing = not self._playing

    def stop(self) -> None:
        self._playing = False

    def seek_ratio(self, ratio: float) -> bool:
        if self._length_ms <= 0:
            return False
        self._time_ms = int(self._length_ms * max(0.0, min(1.0, ratio)))
        return True

    def seek_ms(self, ms: int) -> bool:
        self._time_ms = max(0, ms)
        return True

    def set_volume(self, v: int) -> None:
        self._volume = int(v)

    def screenshot(self, path: str) -> None:
        pass

    def is_seekable(self) -> bool:
        return bool(self._seekable)

    def is_buffering_or_seeking(self) -> bool:
        return False

    def get_video_size(self):
        return (1280, 720)

    def get_state(self) -> PlaybackState:
        return PlaybackState(
            is_playing=self._playing,
            time_ms=self._time_ms,
            length_ms=self._length_ms,
            volume=self._volume,
            mrl=self._loaded[-1] if self._loaded else None,
        )

    def shutdown(self) -> None:
        self._shutdown_calls += 1
        self._playing = False


@pytest.fixture
def engine():
    return FakeEngine()


@pytest.fixture
def w(qtbot, engine):
    win = PlayerWindow(engine, playlist=None, autoplay=False, template="no_background_night")
    qtbot.addWidget(win)
    win.show()
    qtbot.waitExposed(win)
    return win


def test_load_playlist_from_file_ignores_ext_lines(tmp_path, qtbot, engine):
    p = tmp_path / "t.m3u8"
    p.write_text("#EXTM3U\n#EXTINF:-1,a\nhttps://a/b/1\n\n#EXTINF:-1,b\nhttps://a/b/2\n", encoding="utf-8")

    win = PlayerWindow(engine, autoplay=False, template="no_background_night")
    qtbot.addWidget(win)
    win.load_playlist(str(p), title_id=None, skip_data=None)

    assert win.playlist_urls == ["https://a/b/1", "https://a/b/2"]
    assert win.playlist_widget.count() == 2


def test_play_index_sets_current_and_highlight(w, qtbot):
    w.playlist_urls = ["u1", "u2", "u3"]
    w.playlist_widget.clear()
    for u in w.playlist_urls:
        w.playlist_widget.addItem(u)

    w.play_index(1)
    qtbot.wait(20)

    assert w.playlist_index == 1
    assert w.playlist_widget.currentRow() == 1


def test_close_player_closes_video_and_shutdown_once(qtbot, engine):
    win = PlayerWindow(engine, autoplay=False, template="no_background_night")
    qtbot.addWidget(win)
    win.show()
    qtbot.waitExposed(win)

    win.video_window.show()
    qtbot.waitExposed(win.video_window)

    win.close()
    qtbot.wait(50)

    assert engine._shutdown_calls == 1
    assert not win.video_window.isVisible()


def test_close_video_closes_player_and_shutdown_once(qtbot, engine):
    win = PlayerWindow(engine, autoplay=False, template="no_background_night")
    qtbot.addWidget(win)
    win.show()
    qtbot.waitExposed(win)

    win.video_window.show()
    qtbot.waitExposed(win.video_window)

    # пользователь закрывает видео-окно
    win.video_window.close()
    qtbot.wait(100)

    assert engine._shutdown_calls == 1
    assert not win.isVisible()


def test_skip_data_decode_does_not_crash(w):
    # мусорная base64
    w._decode_skip_data("not_base64!!!")
    assert w.skip_data_cache is None

class DummyRR:
    def __init__(self, final_url):
        self.final_url = final_url
        self.chain = []
        self.recommended_host = None

class DummyResolver:
    def __init__(self):
        self.calls = []
    def resolve(self, url: str):
        self.calls.append(url)
        return DummyRR("https://final.example/stream.m3u8")


def test_resolver_not_called_when_proxy_disabled(qtbot, monkeypatch):
    engine = FakeEngine()
    r = DummyResolver()

    win = PlayerWindow(engine, playlist=None, autoplay=False, template="no_background_night",
                       proxy=None, resolver=r)
    qtbot.addWidget(win)

    # форсим "готовность" — иначе _do_load рано выходит
    monkeypatch.setattr(win, "_is_engine_ready", lambda: True, raising=False)
    monkeypatch.setattr(win, "_engine_ready", True, raising=False)

    win._do_load("https://start.example/stream.m3u8")

    assert r.calls == []
    assert engine._loaded[-1] == "https://start.example/stream.m3u8"


def test_resolver_called_when_proxy_enabled(qtbot, monkeypatch):
    engine = FakeEngine()
    r = DummyResolver()

    win = PlayerWindow(engine, playlist=None, autoplay=False, template="no_background_night",
                       proxy="http://127.0.0.1:8866", resolver=r)
    qtbot.addWidget(win)

    monkeypatch.setattr(win, "_is_engine_ready", lambda: True, raising=False)
    monkeypatch.setattr(win, "_engine_ready", True, raising=False)

    win._do_load("https://start.example/stream.m3u8")

    assert r.calls == ["https://start.example/stream.m3u8"]
    assert engine._loaded[-1] == "https://final.example/stream.m3u8"


