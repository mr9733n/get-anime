from typing import Literal, Final
from dataclasses import dataclass


PosterSize = Literal["original", "medium", "small"]
POSTER_SIZES: Final[tuple[PosterSize, ...]] = ("original", "medium", "small")

@dataclass(frozen=True)
class PosterFieldMap:
    blob: str
    hash: str
    updated: str


POSTER_FIELDS: dict[PosterSize, PosterFieldMap] = {
    "original": PosterFieldMap(
        blob="poster_blob",
        hash="hash_value",
        updated="last_updated",
    ),
    "medium": PosterFieldMap(
        blob="medium_blob",
        hash="medium_hash",
        updated="medium_updated_at",
    ),
    "small": PosterFieldMap(
        blob="thumb_blob",
        hash="thumb_hash",
        updated="thumb_updated_at",
    ),
}