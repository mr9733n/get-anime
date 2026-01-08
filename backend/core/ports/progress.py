from __future__ import annotations
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class TitleProgress:
    title_id: int
    last_watched_episode_number: int  # 0 if nothing watched


class ProgressRepo(Protocol):
    def get_last_watched_episode_numbers(
        self,
        *,
        user_id: int,
        title_ids: list[int],
    ) -> dict[int, int]:
        """
        Returns mapping: title_id -> last watched episode_number (0 if none).
        """
        ...
