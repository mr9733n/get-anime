# app/mpv/runner.py
from __future__ import annotations

from app.mpv.mpv_engine import MpvEngine
from app.mpv.player_window import PlayerWindow
from app.mpv.playback_request import PlaybackRequest

def run_player(request: PlaybackRequest) -> PlayerWindow:
    engine = MpvEngine(
        proxy=request.proxy,
        loglevel=("info" if request.verbose else "warn"),
        log_file=request.log_file
    )
    w = PlayerWindow(
        engine,
        playlist=request.playlist,
        title_id=request.title_id,
        skip_data=request.skip_data_b64,
        proxy=request.proxy,
        autoplay=request.autoplay,
        template=request.template,
    )
    w.show()
    return w
