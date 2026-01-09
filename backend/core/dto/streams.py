from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StreamInfoDTO:
    title_id: int
    episode_id: int
    episode_number: int

    url_sd: str | None
    url_hd: str | None
    url_fhd: str | None

    best_url: str | None
    best_quality: str | None  # "fhd" | "hd" | "sd" | None
