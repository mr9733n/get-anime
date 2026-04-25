from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any


class TitleViewMode(str, Enum):
    """Controls which DTO type is produced and how deeply the enricher fetches.

    FULL — TitleDetailsDTO with all related entities (episodes, torrents,
           team_members, franchises, history). Every per-episode / per-torrent
           history query runs.  Use for detail / player view.

    CARD — TitleCardDTO without heavy sub-lists. Per-episode N+1 loops are
           skipped.  Use for search results and list views.
    """
    FULL = "full"
    CARD = "card"


# --- leaf DTOs ---

@dataclass(frozen=True)
class GenreDTO:
    genre_id: int | None
    name: str | None


@dataclass(frozen=True)
class FranchiseDTO:
    id: int
    franchise_id: int
    code: str | None
    ordinal: int | None
    name_ru: str | None
    name_en: str | None
    name_alternative: str | None
    # franchise itself (optional)
    franchise_name: str | None = None


@dataclass(frozen=True)
class TeamMemberDTO:
    id: int
    name: str
    role: str


@dataclass(frozen=True)
class TorrentDTO:
    torrent_id: int
    episodes_range: str | None
    range_first: int | None
    range_last: int | None
    quality: str | None
    quality_type: str | None
    resolution: str | None
    encoder: str | None
    leechers: int | None
    seeders: int | None
    downloads: int | None
    total_size: int | None
    size_string: str | None
    url: str | None
    magnet_link: str | None
    uploaded_timestamp: datetime | None
    api_updated_at: datetime | None
    label: str | None
    filename: str | None
    hash: str | None


@dataclass(frozen=True)
class ProviderLinkDTO:
    id: int
    provider_id: int
    provider_code: str | None
    provider_name: str | None
    external_title_id: str


@dataclass(frozen=True)
class ProductionStudioDTO:
    id: int
    name: str


@dataclass(frozen=True)
class RatingDTO:
    rating_id: int
    rating_name: str
    rating_value: int
    name_external: str | None
    score_external: float | None
    last_updated: datetime | None


@dataclass(frozen=True)
class HistoryDTO:
    id: int
    user_id: int
    title_id: int
    episode_id: int | None
    torrent_id: int | None
    is_watched: bool
    last_watched_at: datetime | None
    previous_watched_at: datetime | None
    watch_change_count: int | None
    is_download: bool
    last_download_at: datetime | None
    previous_download_at: datetime | None
    download_change_count: int | None


@dataclass(frozen=True)
class ScheduleDTO:
    day_of_week: int
    day_name: str | None
    last_updated: datetime | None


@dataclass(frozen=True)
class EpisodeDTO:
    episode_id: int
    episode_number: int
    name: str | None

    hls_sd: str | None
    hls_hd: str | None
    hls_fhd: str | None

    # computed abs urls (backend adds base host)
    hls_sd_abs: str | None
    hls_hd_abs: str | None
    hls_fhd_abs: str | None

    preview_path: str | None
    preview_abs: str | None

    skips_opening: str | None
    skips_ending: str | None


# --- card DTO (list-view, lightweight) ---

@dataclass(frozen=True)
class TitleCardDTO:
    """Lightweight DTO for list / search views. No episodes, torrents, team, history."""
    title_id: int
    code: str | None
    name_ru: str | None
    name_en: str | None
    alternative_name: str | None

    status_string: str | None
    status_code: int | None

    type_string: str | None
    type_code: int | None
    type_episodes: str | None
    type_length: str | None

    season_year: int | None
    season_string: str | None
    season_code: int | None

    day_of_week: int | None
    day_name: str | None

    host_for_player: str | None

    poster_path_small: str | None
    poster_path_medium: str | None
    poster_path_original: str | None   # needed for providers that only supply original size (AniMedia)

    genres: list[GenreDTO]
    provider_links: list[ProviderLinkDTO]
    production_studio: ProductionStudioDTO | None
    ratings: list[RatingDTO]

    # Enrichment (scalar)
    provider: str | None
    studio: str | None
    team: str | None
    rating_name: str | None
    rating_value: int | None

    need_to_see: bool
    title_watched: bool
    all_episodes_watched: bool

    enriched: bool
    missing: list[str]


# --- main DTO ---

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
    type_episodes: str | None
    type_length: str | None

    season_year: int | None
    season_string: str | None
    season_code: int | None

    description: str | None

    day_of_week: int | None
    day_name: str | None

    host_for_player: str | None

    # poster paths directly from titles table (no blobs)
    poster_path_small: str | None
    poster_path_medium: str | None
    poster_path_original: str | None

    # children
    genres: list[GenreDTO]
    episodes: list[EpisodeDTO]
    schedules: list[ScheduleDTO]

    franchises: list[FranchiseDTO]
    team_members: list[TeamMemberDTO]
    torrents: list[TorrentDTO]
    provider_links: list[ProviderLinkDTO]
    production_studio: ProductionStudioDTO | None
    ratings: list[RatingDTO]
    history: list[HistoryDTO]

    # -----------------------
    # Enrichment (DB-only prefs)
    # -----------------------
    provider: str | None
    studio: str | None
    team: str | None
    rating_name: str | None
    rating_value: int | None

    need_to_see: bool
    title_watched: bool
    all_episodes_watched: bool
    watched_episode_ids: list[int]
    downloaded_torrent_ids: list[int]

    enriched: bool
    missing: list[str]
