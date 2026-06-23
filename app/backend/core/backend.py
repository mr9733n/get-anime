from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.backend.core.ports.notify import NotifierPort
from app.backend.core.use_cases.title_search_use_case import TitleSearchUseCase


@dataclass
class BackendDeps:
    # storage / db layer
    db: Any

    # providers / adapters
    aniliberty_api: Any
    animedia_adapter: Any

    # persistence service (если у тебя уже есть)
    persistence: Any

    # misc
    notify: NotifierPort
    logger: Any | None = None


class Backend:
    """
    Единственный вход в 'бек' для фронта (Qt) и CLI.
    UI не должен ходить в db/providers напрямую — только сюда.
    """
    def __init__(self, deps: BackendDeps):
        self.db = deps.db
        self.api = deps.aniliberty_api
        self.animedia = deps.animedia_adapter
        self.persistence = deps.persistence
        self.notify = deps.notify
        self.logger = deps.logger

        # use-cases
        self._title_search_uc = TitleSearchUseCase(
            db=self.db,
            api=self.api,
            persistence=self.persistence,
            animedia_adapter=self.animedia,
            provider_aniliberty="aniliberty",
            provider_animedia="animedia",
        )

    # -------------------------
    # System / templates
    # -------------------------
    def list_templates(self) -> list[str]:
        return self.db.list_templates()

    def get_current_template(self) -> str:
        return self.db.get_current_template()

    def set_current_template(self, name: str) -> None:
        # тут можешь добавить валидацию
        self.db.save_template(name)

    def optimize_db(self) -> dict:
        return self.db.optimize_db()

    # -------------------------
    # Deleted / Audit (для окон)
    # -------------------------
    def get_deleted_titles(self, batch_size: int = 300, offset: int = 0):
        return self.db.get_deleted_titles(batch_size=batch_size, offset=offset)

    def restore_titles(self, ids: list[int]) -> None:
        self.db.restore_titles(ids)

    def purge_titles(self, csv_ids: str) -> None:
        self.db.purge_titles(csv_ids)

    def get_deleted_titles_log(self, limit: int = 300, offset: int = 0):
        return self.db.get_deleted_titles_log(limit=limit, offset=offset)

    def get_deleted_titles_log_item(self, log_id: int):
        return self.db.get_deleted_titles_log_item(log_id)

    # -------------------------
    # Search / update (use-case)
    # -------------------------
    async def search_by_title(self, text: str, provider: str | None = None):
        return await self._title_search_uc.search_by_title(text, provider)

    async def update_titles(self, text: str, provider: str | None = None):
        return await self._title_search_uc.update_titles(text, provider)
