from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class GenreDTO:
    genre_id: int | None
    name: str | None


@dataclass(frozen=True)
class EpisodeDTO:
    episode_id: int
    episode_number: int
    name: str | None

    hls_sd: str | None
    hls_hd: str | None
    hls_fhd: str | None

    hls_sd_abs: str | None
    hls_hd_abs: str | None
    hls_fhd_abs: str | None

    preview_path: str | None
    skips_opening: str | None
    skips_ending: str | None


@dataclass(frozen=True)
class TitleDetailsDTO:
    title_id: int

    code: str | None
    name_ru: str | None
    name_en: str | None
    alternative_name: str | None

    status_string: str | None
    status_code: int | None

    type_full_string: str | None
    type_string: str | None
    type_code: int | None
    type_episodes: int | None
    type_length: str | None

    season_year: int | None
    season_string: str | None
    season_code: int | None

    description: str | None

    day_of_week: int | None
    day_name: str | None

    genres: list[GenreDTO]
    episodes: list[EpisodeDTO]

    host_for_player: str | None