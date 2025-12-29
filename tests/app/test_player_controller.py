import types
from pathlib import Path
import pytest
import logging
logging.getLogger(__name__).setLevel(logging.CRITICAL)

from app.qt.controllers.players import PlayerController


class DummyResolver:
    def resolve(self, url):
        return None


class DummyDB:
    def __init__(self, host="example.com"):
        self._host = host

    def get_player_host_by_title_id(self, title_id):
        return self._host


class DummyPlaylistManager:
    def make_full_url(self, link, host):
        # повторяем ожидаемую логику: https://{host}{link}
        if not host:
            return None
        return f"https://{host}{link}"

    playlist_path = "playlists"


class DummyUI:
    pass


class DummySvc:
    def __init__(self, db):
        self.db = db
        self.ui = DummyUI()
        self.logger = types.SimpleNamespace(
            info=lambda *a, **k: None,
            debug=lambda *a, **k: None,
            warning=lambda *a, **k: None,
            error=lambda *a, **k: None,
            exception=lambda *a, **k: None,
        )
        self.api = None


def make_app(
    *,
    use_mpv_player=False,
    use_libvlc=True,
    proxy_enabled=False,
    proxy_url="http://proxy:8080",
    mpv_log_enabled=False,
):
    # минимальный "app stub" с теми полями, которые читает PlayerController
    return types.SimpleNamespace(
        proxy_enabled=proxy_enabled,
        proxy_url=proxy_url,
        mpv_log_enabled=mpv_log_enabled,
        mpv_verbose="info",
        mpv_player_executable_name="mpv_player.exe",
        log_enabled=False,
        verbose="2",
        use_mpv_player=use_mpv_player,
        use_libvlc=use_libvlc,
        current_template="default",
        prod_key=None,
        stream_video_url="fallback-host.com",
        url_resolver=DummyResolver(),
        playlist_manager=DummyPlaylistManager(),
        router=types.SimpleNamespace(
            open_web_urls=lambda urls: None,
            open_web_file=lambda p: None
        ),
        config_manager=types.SimpleNamespace(get_vlc_player_executable_name=lambda: "vlc_player.exe"),
        video_player_path="C:/player.exe",
        current_title_id=123,
        playlists={},
        pre="https://",
    )


def test_play_link_full_url_uses_as_is(mocker):
    app = make_app(use_mpv_player=True)
    svc = DummySvc(db=DummyDB(host="db-host.com"))
    pc = PlayerController(app, svc)

    # mpv "успешно"
    spy = mocker.patch.object(pc, "open_standalone_mpv_player", return_value=True)

    pc.play_link("https://cdn.site/video.m3u8", title_id=55)

    spy.assert_called_once()
    called_url = spy.call_args.args[0]
    assert called_url == "https://cdn.site/video.m3u8"


def test_play_link_relative_uses_db_host(mocker):
    app = make_app(use_mpv_player=True)
    svc = DummySvc(db=DummyDB(host="db-host.com"))
    pc = PlayerController(app, svc)

    spy = mocker.patch.object(pc, "open_standalone_mpv_player", return_value=True)

    pc.play_link("/videos/ep1.m3u8", title_id=777)

    called_url = spy.call_args.args[0]
    assert called_url == "https://db-host.com/videos/ep1.m3u8"


def test_play_link_relative_without_leading_slash_is_fixed(mocker):
    app = make_app(use_mpv_player=True)
    svc = DummySvc(db=DummyDB(host="db-host.com"))
    pc = PlayerController(app, svc)

    spy = mocker.patch.object(pc, "open_standalone_mpv_player", return_value=True)

    pc.play_link("videos/ep1.m3u8", title_id=777)

    called_url = spy.call_args.args[0]
    assert called_url == "https://db-host.com/videos/ep1.m3u8"


def test_mpv_fallback_to_vlc_when_mpv_fails(mocker):
    app = make_app(use_mpv_player=True, use_libvlc=True)
    svc = DummySvc(db=DummyDB(host="db-host.com"))
    pc = PlayerController(app, svc)

    mocker.patch.object(pc, "open_standalone_mpv_player", return_value=False)
    spy_vlc = mocker.patch.object(pc, "open_standalone_vlc_player")

    pc.play_link("/videos/ep1.m3u8", title_id=1)

    spy_vlc.assert_called_once()


def test_open_web_link_builds_full_url_and_calls_router(mocker):
    app = make_app()
    svc = DummySvc(db=DummyDB(host="db-host.com"))
    pc = PlayerController(app, svc)

    spy = mocker.spy(app.router, "open_web_urls")

    pc.open_web_link("/watch/1", title_id=1)

    spy.assert_called_once()
    assert spy.call_args.args[0] == ["https://db-host.com/watch/1"]
