# providers/animedia/v0/models.py
from dataclasses import dataclass, field
from typing import Optional, Any
from enum import Enum
import uuid


class TitleStatus(Enum):
    ONGOING = 1
    FINISHED = 2
    ANNOUNCED = 3

    def to_legacy(self) -> dict[str, Any]:
        """Конвертация в legacy формат."""
        mapping = {
            TitleStatus.ONGOING: {"code": 1, "string": "В работе"},
            TitleStatus.FINISHED: {"code": 2, "string": "Завершён"},
            TitleStatus.ANNOUNCED: {"code": 3, "string": "Анонс"},
        }
        return mapping.get(self, {"code": 2, "string": "Завершён"})


@dataclass
class Episode:
    number: int
    name: str
    hls_sd: str = ""
    hls_hd: str = ""
    hls_fhd: str = ""
    preview: Optional[str] = None
    created_timestamp: int = 0
    uuid: str = field(default_factory=lambda: str(uuid.uuid4()))

    def to_legacy(self) -> dict[str, Any]:
        """Конвертация в legacy формат для player.list."""
        return {
            "hls": {
                "sd": self.hls_sd,
                "hd": self.hls_hd,
                "fhd": self.hls_fhd,
            },
            "uuid": self.uuid,
            "created_timestamp": self.created_timestamp,
            "episode": self.number,
            "name": self.name,
            "preview": self.preview,
            "skips": {"ending": [None, None], "opening": [None, None]},
        }


@dataclass
class Title:
    external_id: int
    name_ru: str
    name_en: str
    name_alt: str = ""
    description: str = ""
    poster_url: str = ""
    status: TitleStatus = TitleStatus.FINISHED
    year: int = 0
    season: str = ""
    genres: list[str] = field(default_factory=list)
    episodes: list[Episode] = field(default_factory=list)
    studio: str = ""
    rating: float = 0.0
    video_host: str = ""
    updated_timestamp: int = 0
    type_string: str = ""
    type_full: str = ""
    episodes_count: int = 0
    episode_length: Optional[int] = None

    @property
    def code(self) -> str:
        """Slug для URL."""
        from .legacy_mapper import replace_spaces_to_hyphen
        return replace_spaces_to_hyphen(self.name_en) or ""

    @property
    def sanitized_name_ru(self) -> str:
        """Название без кавычек."""
        from .legacy_mapper import replace_brackets
        return replace_brackets(self.name_ru) or ""

    def to_legacy(self) -> dict[str, Any]:
        """Полная конвертация в legacy формат для БД."""
        # Episodes dict: {"1": {...}, "2": {...}}
        episodes_dict = {
            str(ep.number): ep.to_legacy() for ep in self.episodes
        }

        # Проставить timestamp во все эпизоды
        for ep_data in episodes_dict.values():
            ep_data["created_timestamp"] = self.updated_timestamp

        return {
            "external_id": self.external_id,
            "provider": "AniMedia",
            "code": self.code,
            "announce": "",
            "names": {
                "ru": self.sanitized_name_ru,
                "en": self.name_en,
                "alternative": self.name_alt,
            },
            "description": self.description,
            "season": {
                "code": None,
                "string": self.season,
                "year": self.year,
                "week_day": None,
            },
            "status": self.status.to_legacy(),
            "type": {
                "code": 0,
                "string": self.type_string,
                "full_string": self.type_full,
                "episodes": self.episodes_count,
                "length": self.episode_length,
            },
            "studio": self.studio,
            "rating": {
                "name": "AniMedia",
                "score": self.rating,
            },
            "genres": self.genres,
            "posters": {
                "small": {},
                "medium": {},
                "original": {"url": self.poster_url},
            },
            "updated": self.updated_timestamp,
            "last_change": self.updated_timestamp,
            "in_favorites": 0,
            "blocked": {
                "copyrights": False,
                "geoip": False,
                "geoip_list": [],
            },
            "player": {
                "host": self.video_host,
                "alternative_player": "",
                "list": episodes_dict,
            },
            "team": {"voice": [], "translator": [], "timing": []},
            "franchises": [],
            "torrents": {"list": []},
        }


@dataclass
class ScheduleItem:
    """Элемент расписания (новый тайтл/анонс)."""
    title_id: str
    title: str
    meta: str = ""
    episode: Optional[str] = None
    poster_url: Optional[str] = None
    link: Optional[str] = None

    @classmethod
    def from_separator_string(cls, s: str, separator: str = "\u00B7") -> "ScheduleItem":
        """Парсинг из строки формата 'title·meta·episode·id·poster·link'."""
        parts = s.split(separator)
        return cls(
            title=parts[0] if len(parts) > 0 else "",
            meta=parts[1] if len(parts) > 1 else "",
            episode=parts[2] if len(parts) > 2 else None,
            title_id=parts[3] if len(parts) > 3 else "",
            poster_url=parts[4] if len(parts) > 4 else None,
            link=parts[5] if len(parts) > 5 else None,
        )