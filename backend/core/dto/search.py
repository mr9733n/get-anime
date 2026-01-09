from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class TitlesSearchResult:
    title_ids: list[int]
    providers: list[str]
