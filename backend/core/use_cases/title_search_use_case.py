from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class TitleSearchResult:
    ok: bool
    title_ids: list[int] | None = None
    used_provider: str | None = None  # "aniliberty" / "animedia" / None
    current_data: Any = None          # raw response for ctx.current_data
    error: str | None = None          # message for UI to show if needed


@dataclass
class TitleUpdateResult:
    ok: bool
    updated: int = 0
    failed: int = 0
    updated_title_ids: list[int] | None = None
    errors: list[str] | None = None
    error: str | None = None


class TitleSearchUseCase:
    """
    Миграционный use-case, который повторяет текущую логику ActionsController:
      DB -> AniLiberty -> AniMedia(async)
    Никакого Qt/UI внутри. Только данные и решение.
    """

    def __init__(
        self,
        *,
        db: Any,
        api: Any,
        persistence: Any,
        animedia_adapter: Any,
        provider_aniliberty: str,
        provider_animedia: str,
    ) -> None:
        self._db = db
        self._api = api
        self._persistence = persistence
        self._animedia = animedia_adapter
        self._P_AL = provider_aniliberty
        self._P_AM = provider_animedia

    # ---------------------------------------------------------------------
    # Public API
    # ---------------------------------------------------------------------

    async def search_by_title(
        self,
        search_text: str,
        provider_filter: str | None,
        *,
        max_titles_animedia: int = 5,
    ) -> TitleSearchResult:
        """
        Полный сценарий: сначала БД, потом внешние провайдеры.
        """
        search_text = (search_text or "").strip()
        if not search_text:
            return TitleSearchResult(ok=False, error="Empty search text")

        # 1) DB
        try:
            title_ids, providers = self._db.get_titles_by_keywords(search_text)
        except Exception as e:
            return TitleSearchResult(ok=False, error=f"DB error: {e}")

        if title_ids and self._providers_match_filter(providers, provider_filter):
            return TitleSearchResult(
                ok=True,
                title_ids=title_ids,
                used_provider=None,
                current_data=None,
            )

        # 2) External providers
        return await self._search_external(search_text, provider_filter, max_titles_animedia=max_titles_animedia)

    async def update_titles(
            self,
            search_text: str,
            provider_filter: str | None,
            *,
            max_titles_animedia: int = 5,
    ) -> TitleUpdateResult:
        search_text = (search_text or "").strip()
        if not search_text:
            return TitleUpdateResult(ok=False, error="Empty update text")

        # 1) получить тайтлы из БД по запросу (как твой ActionsController._resolve_titles_for_query)
        try:
            rows = self._db.get_titles_search_query(search_text)  # ожидаем list[dict]
        except Exception as e:
            return TitleUpdateResult(ok=False, error=f"DB error: {e}")

        if not rows:
            return TitleUpdateResult(ok=False, error="No titles found for update.")

        updated_ids: list[int] = []
        errors: list[str] = []
        updated = 0
        failed = 0

        for t in rows:
            try:
                title_id = t.get("title_id")
                if title_id is None:
                    continue

                # провайдер/имя/external_id лежат в providers[0]
                providers = t.get("providers", []) or []
                primary = providers[0] if providers else None
                provider = primary.get("provider") if primary else None
                external_id = primary.get("external_id") if primary else None

                # фильтр по провайдеру
                if provider_filter is not None and provider != provider_filter:
                    continue

                name_en = t.get("name_en")
                name_ru = t.get("name_ru")

                # 2) обновить через нужный провайдер (миграционно, как сейчас)
                if provider == self._P_AL or provider_filter == self._P_AL:
                    query = str(external_id or title_id) or name_en or name_ru or str(title_id)
                    ids, _ = self._load_and_save_from_aniliberty(query)
                    if ids:
                        updated += 1
                        updated_ids.extend(ids)
                elif provider == self._P_AM or provider_filter == self._P_AM:
                    query = name_en or name_ru or str(external_id or title_id)
                    ids, _ = await self._load_and_save_from_animedia(query, max_titles=max_titles_animedia)
                    if ids:
                        updated += 1
                        updated_ids.extend(ids)
                else:
                    # неизвестный провайдер — считаем как failed
                    failed += 1
                    errors.append(f"Unknown provider for title_id={title_id}: {provider}")

            except Exception as e:
                failed += 1
                errors.append(str(e))

        if updated == 0 and failed == 0:
            return TitleUpdateResult(ok=False, error="Nothing to update (filtered out).")

        return TitleUpdateResult(
            ok=True,
            updated=updated,
            failed=failed,
            updated_title_ids=updated_ids or None,
            errors=errors or None,
        )

    # ---------------------------------------------------------------------
    # Internal helpers (ported from ActionsController)
    # ---------------------------------------------------------------------

    def _providers_match_filter(self, providers: list, provider_filter: str | None) -> bool:
        if provider_filter is None:
            return True
        non_empty = [p for p in providers if p]
        if not non_empty:
            return False
        return all(p == provider_filter for p in non_empty)

    async def _search_external(
        self,
        search_text: str,
        provider_filter: str | None,
        *,
        max_titles_animedia: int,
    ) -> TitleSearchResult:
        # Try AniLiberty
        if provider_filter in (None, self._P_AL):
            try:
                title_ids, data = self._load_and_save_from_aniliberty(search_text)
                if title_ids:
                    return TitleSearchResult(
                        ok=True,
                        title_ids=title_ids,
                        used_provider=self._P_AL,
                        current_data=data,
                    )
            except Exception as e:
                # не падаем, пробуем дальше
                al_err = str(e)
            else:
                al_err = None
        else:
            al_err = None

        # Try AniMedia
        if provider_filter in (None, self._P_AM):
            try:
                title_ids, data = await self._load_and_save_from_animedia(
                    search_text,
                    max_titles=max_titles_animedia,
                )
                if title_ids:
                    return TitleSearchResult(
                        ok=True,
                        title_ids=title_ids,
                        used_provider=self._P_AM,
                        current_data=data,
                    )
            except Exception as e:
                am_err = str(e)
            else:
                am_err = None
        else:
            am_err = None

        # Not found anywhere
        msg_parts = []
        if al_err:
            msg_parts.append(f"AniLiberty: {al_err}")
        if am_err:
            msg_parts.append(f"AniMedia: {am_err}")

        return TitleSearchResult(
            ok=False,
            title_ids=None,
            used_provider=None,
            current_data=None,
            error="No titles found." + (f" Details: {'; '.join(msg_parts)}" if msg_parts else ""),
        )

    def _load_and_save_from_aniliberty(self, search_text: str) -> tuple[list[int] | None, Any]:
        """
        Полностью повторяет ActionsController._handle_get_titles_from_api(),
        но не показывает UI errors, а кидает исключение или возвращает None.
        """
        keywords = [kw.strip() for kw in search_text.split(",") if kw.strip()]

        if len(keywords) == 1 and keywords[0].isdigit():
            data = self._api.get_release_full(int(keywords[0]))
        elif keywords and all(kw.isdigit() for kw in keywords):
            data = self._api.get_releases_full([int(kw) for kw in keywords])
        else:
            data = self._api.get_search_by_title(search_text)

        title_list = self._extract_title_list(data)
        if not title_list:
            return None, data

        title_ids = self._persistence.invoke_database_save(title_list)
        return title_ids, data

    async def _load_and_save_from_animedia(self, search_text: str, *, max_titles: int) -> tuple[list[int] | None, Any]:
        """
        AniMedia async path. Ожидаем, что animedia_adapter.get_by_title возвращает list[dict] или list.
        """
        data = await self._animedia.get_by_title(search_text, max_titles=max_titles)

        title_list = self._extract_title_list(data)
        if not title_list:
            return None, data

        title_ids = self._persistence.invoke_database_save(title_list)
        return title_ids, data

    def _extract_title_list(self, data: Any) -> list[dict] | None:
        """
        Портированная логика ActionsController._extract_title_list(),
        но без display/ui уведомлений.
        """
        if isinstance(data, dict):
            if "error" in data:
                # пусть это будет "жёсткая" ошибка провайдера
                raise RuntimeError(str(data["error"]))
            if "list" in data:
                lst = data.get("list", [])
                return lst if isinstance(lst, list) else None
            if "external_id" in data:
                return [data]
        elif isinstance(data, list):
            return data

        return None
