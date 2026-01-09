from __future__ import annotations
from typing import Protocol, Any

class ITitlesEnricherPort(Protocol):
    def enrich_titles(self, titles: list[Any], *, user_id: int) -> list[Any]:
        """Мутирует/обогащает ORM Title (через _pref_*), возвращает titles."""
        ...
