# tests/app/test_player_controller.py
import types
from pathlib import Path
import pytest
import logging

from app.qt.controllers.players import PlayerController, PlayerControllerDeps

logging.getLogger(__name__).setLevel(logging.CRITICAL)


# === Dummy Dependencies ===

class DummyLogger:
    def info(self, *a, **k): pass
    def debug(self, *a, **k): pass
    def warning(self, *a, **k): pass
    def error(self, *a, **k): pass
    def exception(self, *a, **k): pass


class DummyResolver:
    def resolve(self, url):
        return None


class DummyDB:
    def __init__(self, host="example.com"):
        self._host = host

    def get_player_host_by_title_id(self, title_id):
        return self._host


class DummyPlaylistManager:
    playlist_path = "playlists"

    def make_full_url(self, link, host):
        if not host:
            return None
        return f"https://{host}{link}"


class DummyContext:
    """Минимальный контекст для тестов."""
    def __init__(self):
        self.current_title_id = 123
        self.current_template = "default"
        self.stream_video_url = "fallback-host.com"
        self.playlist_filename = None
        self.playlists = {}


class DummyRouter:
    def __init__(self):
        self.opened_urls = []
        self.opened_files = []

    def open_web_urls(self, urls):
        self.opened_urls.extend(urls)

    def open_web_file(self, path):
        self.opened_files.append(path)


# === Fixtures ===

@pytest.fixture
def dummy_router():
    return DummyRouter()


@pytest.fixture
def make_controller(dummy_router):
    """Фабрика для создания PlayerController с нужными параметрами."""

    def _make(
        *,
        host="db-host.com",
        use_mpv_player=False,
        use_libvlc=True,
        proxy_enabled=False,
        proxy_url="http://proxy:8080",
    ):
        deps = PlayerControllerDeps(
            logger=DummyLogger(),
            db=DummyDB(host=host),
            context=DummyContext(),
            playlist_manager=DummyPlaylistManager(),
            url_resolver=DummyResolver(),
            use_libvlc=use_libvlc,
            use_mpv_player=use_mpv_player,
            proxy_enabled=proxy_enabled,
            proxy_url=proxy_url,
            video_player_path="C:/player.exe",
            get_router=lambda: dummy_router,
        )
        return PlayerController(deps)

    return _make


# === Tests ===

def test_play_link_full_url_uses_as_is(make_controller, mocker):
    """Полный URL используется как есть."""
    pc = make_controller(use_mpv_player=True)

    # Мокаем внутренний метод MPV
    spy = mocker.patch.object(pc, "_play_via_mpv", return_value=True)

    pc.play_link("https://cdn.site/video.m3u8", title_id=55)

    spy.assert_called_once()
    called_url = spy.call_args.args[0]
    assert called_url == "https://cdn.site/video.m3u8"


def test_play_link_relative_uses_db_host(make_controller, mocker):
    """Относительный URL дополняется хостом из БД."""
    pc = make_controller(use_mpv_player=True, host="db-host.com")

    spy = mocker.patch.object(pc, "_play_via_mpv", return_value=True)

    pc.play_link("/videos/ep1.m3u8", title_id=777)

    called_url = spy.call_args.args[0]
    assert called_url == "https://db-host.com/videos/ep1.m3u8"


def test_play_link_relative_without_leading_slash_is_fixed(make_controller, mocker):
    """Относительный URL без / в начале — добавляется автоматически."""
    pc = make_controller(use_mpv_player=True, host="db-host.com")

    spy = mocker.patch.object(pc, "_play_via_mpv", return_value=True)

    pc.play_link("videos/ep1.m3u8", title_id=777)

    called_url = spy.call_args.args[0]
    assert called_url == "https://db-host.com/videos/ep1.m3u8"


def test_mpv_fallback_to_vlc_when_mpv_fails(make_controller, mocker):
    """При ошибке MPV — fallback на VLC."""
    pc = make_controller(use_mpv_player=True, use_libvlc=True)

    mocker.patch.object(pc, "_play_via_mpv", return_value=False)
    spy_vlc = mocker.patch.object(pc, "_play_via_vlc")

    pc.play_link("/videos/ep1.m3u8", title_id=1)

    spy_vlc.assert_called_once()


def test_open_web_link_builds_full_url_and_calls_router(make_controller, dummy_router):
    """open_web_link строит полный URL и вызывает router."""
    pc = make_controller(host="db-host.com")

    pc.open_web_link("/watch/1", title_id=1)

    assert dummy_router.opened_urls == ["https://db-host.com/watch/1"]


def test_resolve_link_returns_none_for_empty_host(make_controller):
    """_resolve_link возвращает None если хост пустой."""
    pc = make_controller(host=None)  # DummyDB вернёт None

    result = pc._resolve_link("/path", title_id=999)

    # fallback на context.stream_video_url
    assert result == "https://fallback-host.com/path"