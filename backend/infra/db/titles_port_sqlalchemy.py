from __future__ import annotations

from sqlalchemy.orm import joinedload

from backend.core.ports.titles_port import ITitlesPort

# Импорты моделей — подстрой под реальный путь
# Судя по твоему коду в get.py: TitleProviderMap и Provider точно есть.
from storage.tables import TitleProviderMap  # <-- подставь реальный импорт


class SqlAlchemyTitlesPort(ITitlesPort):
    def __init__(self, db_manager):
        self._db = db_manager

    # --- titles ---
    def get_titles(
        self,
        *,
        show_all: bool = False,
        day_of_week: int | None = None,
        batch_size: int | None = None,
        title_id: int | None = None,
        title_ids: list[int] | None = None,
        offset: int = 0,
    ):
        return self._db.get_titles_from_db(
            show_all=show_all,
            day_of_week=day_of_week,
            batch_size=batch_size,
            title_id=title_id,
            title_ids=title_ids,
            offset=offset,
        )

    # --- search ---
    def search_title_ids(self, query: str, *, limit: int = 50, offset: int = 0) -> list[int]:
        """
        Используем существующий get_titles_search_query, который возвращает list[dict],
        и нормализуем до списка title_ids.
        """
        rows = self._db.get_titles_search_query(query=query)  # list[dict]
        ids: list[int] = []
        for r in rows or []:
            if isinstance(r, dict) and "title_id" in r:
                try:
                    ids.append(int(r["title_id"]))
                except Exception:
                    continue

        # применяем offset/limit на уровне python (т.к. исходный метод уже отдал list)
        if offset:
            ids = ids[int(offset):]
        if limit is not None:
            ids = ids[: int(limit)]
        return ids

    def search_title_ids_with_providers(self, query: str) -> tuple[list[int], list[str]]:
        """
        Быстрый поиск (для titles_ids.search): используем существующий DbManager.get_titles_by_keywords.
        """
        title_ids, providers = self._db.get_titles_by_keywords(query)
        title_ids = [int(x) for x in (title_ids or [])]
        providers = list(providers or [])
        return title_ids, providers
    
    def count_search_titles(self, query: str) -> int:
        rows = self._db.get_titles_search_query(query=query)
        return len(rows) if rows else 0

    # --- provider links ---
    def get_provider_links_map(self, title_ids: list[int]) -> dict[int, list[dict]]:
        """
        Это НЕ DbManager метод, поэтому реализуем тут (infra).
        Никаких вызовов из controller, только через порт.
        """
        if not title_ids:
            return {}

        title_ids = [int(x) for x in title_ids]
        out: dict[int, list[dict]] = {tid: [] for tid in title_ids}

        # используем Session фабрику, которая уже есть внутри db_manager
        # у тебя в DbManager методы делают: `with self.Session as session:`
        # Значит self._db.Session — это контекст-менеджер.
        with self._db.Session as session:
            links = (
                session.query(TitleProviderMap)
                .options(joinedload(TitleProviderMap.provider))
                .filter(TitleProviderMap.title_id.in_(title_ids))
                .all()
            )

            for link in links:
                tid = int(getattr(link, "title_id"))
                p = getattr(link, "provider", None)
                out.setdefault(tid, []).append(
                    {
                        "id": int(getattr(link, "id")),
                        "provider_id": int(getattr(link, "provider_id")),
                        "provider_code": getattr(p, "code", None) if p else None,
                        "provider_name": getattr(p, "name", None) if p else None,
                        "external_title_id": str(getattr(link, "external_title_id")),
                    }
                )

        return out
