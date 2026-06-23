# app.mpv — custom MPV player module
#
# Launch from project root:
#   python -m app.mpv.main --playlist <url> --title_id <id>
#
# Programmatic usage:
#   from app.mpv import run_player, PlaybackRequest
#   from app.mpv import MpvEngine, PlayerWindow

from app.mpv.base_engine import PlayerEngine, PlaybackState
from app.mpv.playback_request import PlaybackRequest
from app.mpv.mpv_engine import MpvEngine
from app.mpv.player_window import PlayerWindow
from app.mpv.runner import run_player

__all__ = [
    "PlayerEngine",
    "PlaybackState",
    "PlaybackRequest",
    "MpvEngine",
    "PlayerWindow",
    "run_player",
]
