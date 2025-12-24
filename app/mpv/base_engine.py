# player/base_engine.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Callable, Optional, Protocol


@dataclass
class PlaybackState:
    is_playing: bool
    time_ms: int
    length_ms: int
    volume: int
    mrl: str | None = None


class PlayerEngine(Protocol):
    # lifecycle
    def set_video_widget(self, win_id: int) -> None: ...
    def shutdown(self) -> None: ...

    # load
    def load(self, url: str) -> None: ...

    # transport
    def play(self) -> None: ...
    def pause(self) -> None: ...
    def toggle_pause(self) -> None: ...
    def stop(self) -> None: ...

    # seek/volume
    def seek_ratio(self, ratio: float) -> None: ...
    def seek_ms(self, ms: int) -> None: ...
    def set_volume(self, volume: int) -> None: ...

    # info
    def get_state(self) -> PlaybackState: ...

    # events (опционально)
    on_eof: Optional[Callable[[], None]]
    on_error: Optional[Callable[[str], None]]
