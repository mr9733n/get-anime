from __future__ import annotations
from backend.core.ports.titles_enricher_port import ITitlesEnricherPort
from storage.queries.title_enricher import enrich_titles_for_render

class SqlAlchemyTitlesEnricherPort(ITitlesEnricherPort):
    def __init__(self, db_manager):
        self._db = db_manager

    def enrich_titles(self, titles, *, user_id: int):
        if not titles:
            return titles
        return enrich_titles_for_render(self._db, user_id, titles)
