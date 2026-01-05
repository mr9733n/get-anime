# app/qt/controllers/actions.py
from __future__ import annotations

from typing import TYPE_CHECKING
from dataclasses import dataclass

from app.qt.app_constants import PROVIDER_ANILIBERTY, PROVIDER_ANIMEDIA
from app.qt.app_exceptions import APIClientError
from app.qt.app_state import TitleRef
from app.qt.protocols import (
    IDisplayController,
    IPersistenceController,
    IUIManager,
    IAPIAdapter,
)
if TYPE_CHECKING:
    from logging import Logger
    from app.qt.app_context import AppContext
    from providers.animedia.v0.adapter import AniMediaAdapter


@dataclass
class ActionsControllerDeps:
    """Явные зависимости ActionsController"""
    logger: Logger
    db: any  # DBManager — можно тоже сделать протокол
    api: IAPIAdapter
    ui: IUIManager
    display: IDisplayController
    persistence: IPersistenceController
    context: AppContext
    animedia_adapter: AniMediaAdapter  # для async worker


class ActionsController:
    """
    Контроллер поиска и обновления тайтлов.
    Все зависимости — явные, через конструктор.
    """

    def __init__(self, deps: ActionsControllerDeps):
        self._deps = deps
        self._last_search_text: str | None = None
        self._animedia_worker = None

    # --- Properties для удобства ---

    @property
    def log(self):
        return self._deps.logger

    @property
    def db(self):
        return self._deps.db

    @property
    def api(self):
        return self._deps.api

    @property
    def ui(self):
        return self._deps.ui

    @property
    def display(self) -> IDisplayController:
        return self._deps.display

    @property
    def persistence(self) -> IPersistenceController:
        return self._deps.persistence

    @property
    def ctx(self) -> AppContext:
        return self._deps.context

    # --- Public API ---

    def get_update_title(self) -> bool:
        """Обновление с авто-определением провайдера."""
        return self._update_titles(provider_filter=None)

    def get_update_title_aniliberty(self) -> bool:
        """Обновление только через AniLiberty."""
        return self._update_titles(provider_filter=PROVIDER_ANILIBERTY)

    def get_update_title_animedia(self) -> bool:
        """Обновление только через AniMedia."""
        return self._update_titles(provider_filter=PROVIDER_ANIMEDIA)

    def get_search_by_title(self) -> bool:
        """Поиск тайтла: локальная БД → AniLiberty → Animedia."""
        return self._search_by_title(provider_filter=None, search_text=None)

    def get_search_by_title_aniliberty(self) -> bool:
        """Поиск тайтла: локальная БД → AniLiberty."""
        return self._search_by_title(provider_filter=PROVIDER_ANILIBERTY, search_text=None)

    def get_search_by_title_animedia(self, search_text: str | None = None) -> bool:
        """Поиск тайтла: локальная БД (провайдер = Animedia) → Animedia (async)."""
        return self._search_by_title(provider_filter=PROVIDER_ANIMEDIA, search_text=search_text)

    # --- Private implementation ---

    def _get_search_text(self) -> str:
        """Получает текст поиска из UI или текущего состояния"""
        search_text = ""

        if self.ctx.title_search_entry:
            search_text = self.ctx.title_search_entry.text().strip()
            self.ctx.title_search_entry.clear()

        return search_text

    def _get_fallback_search_text(self) -> str | None:
        """Fallback: используем текущие title_ids"""
        if self.ctx.current_title_ids:
            return ",".join(str(tid) for tid in self.ctx.current_title_ids)
        elif self.ctx.current_title_id is not None:
            return str(self.ctx.current_title_id)
        return None

    def _resolve_titles_for_query(self, search_text: str) -> list[TitleRef]:
        """Ищет тайтлы в БД и приводит результат к единому виду."""
        titles_list = self.db.get_titles_search_query(search_text)
        results: list[TitleRef] = []

        for t in titles_list:
            title_id = t.get("title_id")
            if title_id is None:
                continue

            providers = t.get("providers", []) or []
            if providers:
                primary = providers[0]
                provider = primary.get("provider")
                provider_name = primary.get("name")
                external_id = primary.get("external_id")
            else:
                provider = provider_name = external_id = None

            results.append(TitleRef(
                title_id=title_id,
                name_ru=t.get("name_ru"),
                name_en=t.get("name_en"),
                provider=provider,
                provider_name=provider_name,
                external_id=external_id,
            ))

        return results

    def _update_titles(self, provider_filter: str | None) -> bool:
        """Общая логика обновления тайтлов."""
        try:
            self.ui.show_loader("Updating title info...")
            self.ui.set_buttons_enabled(False)

            search_text = self._get_search_text()
            if not search_text:
                search_text = self._get_fallback_search_text()
                if not search_text:
                    self.log.warning("Unable to update title(s): missing title ID(s)")
                    self.display.show_error_notification(
                        "Error", "Unable to update title(s): missing title ID(s)"
                    )
                    return False

            self.log.info(f"Updating title(s). Keywords: {search_text}")
            titles = self._resolve_titles_for_query(search_text)

            if not titles:
                self.log.warning(f"No titles found in DB for update by query: {search_text}")
                self.display.show_error_notification("Update", "No titles found for update.")
                return False

            for tref in titles:
                self._update_single_title(tref, provider_filter)

            return True

        except Exception as e:
            self.log.error(f"Error on update title(s): {e}")
            return False
        finally:
            self.ui.hide_loader()
            self.ui.set_buttons_enabled(True)

    def _update_single_title(self, tref: TitleRef, provider_filter: str | None) -> None:
        """Обновляет один тайтл через соответствующий провайдер."""
        if provider_filter is not None and tref.provider != provider_filter:
            self.log.info(
                f"Skip title_id={tref.title_id}: provider={tref.provider}, filter={provider_filter}"
            )
            return

        if tref.provider == PROVIDER_ANILIBERTY or provider_filter == PROVIDER_ANILIBERTY:
            self._update_via_aniliberty(tref)
        elif tref.provider == PROVIDER_ANIMEDIA or provider_filter == PROVIDER_ANIMEDIA:
            self._update_via_animedia(tref)
        else:
            self.log.warning(
                f"Unknown provider for title_id={tref.title_id}: {tref.provider}"
            )

    def _update_via_aniliberty(self, tref: TitleRef) -> None:
        """Обновление через AniLiberty API."""
        query_name = str(tref.external_id or tref.title_id) or tref.name_en or tref.name_ru
        self.log.info(f"Updating via AniLiberty API: query={query_name}")

        title_ids = self._handle_get_titles_from_api(query_name)
        if title_ids:
            self._handle_found_titles(title_ids, query_name)

    def _update_via_animedia(self, tref: TitleRef) -> None:
        """Обновление через AniMedia (async)."""
        from app.qt.workers import AsyncWorker

        query_name = tref.name_en or tref.name_ru or str(tref.external_id or tref.title_id)
        self.log.info(f"Updating via AniMedia: query={query_name}")

        self._last_search_text = query_name
        self._animedia_worker = AsyncWorker(
            self._deps.animedia_adapter.get_by_title,
            query_name,
            max_titles=5,
        )
        self._animedia_worker.finished.connect(self._on_animedia_result)
        self._animedia_worker.error.connect(self._on_animedia_error)
        self._animedia_worker.start()

    def _search_by_title(self, provider_filter: str | None, search_text: str | None) -> bool:
        """Общая логика поиска тайтлов по названию."""
        try:
            self.ui.show_loader("Fetching by title...")
            self.ui.set_buttons_enabled(False)

            if not search_text:
                search_text = self._get_search_text()
            if not search_text:
                return False

            self.log.debug(f"keywords: {search_text}")
            title_ids, providers = self.db.get_titles_by_keywords(search_text)

            if title_ids and self._providers_match_filter(providers, provider_filter):
                self.log.info(f"Found {len(title_ids)} titles in local DB for '{search_text}'")
                self._handle_found_titles(title_ids, search_text)
                return True

            self.log.info(f"No suitable titles in local DB for '{search_text}'")
            return self._search_external_providers(search_text, provider_filter)

        except Exception as e:
            self.log.error(f"Error while fetching get_search_by_title: {e}")
            return False
        finally:
            self.ui.hide_loader()
            self.ui.set_buttons_enabled(True)

    def _providers_match_filter(self, providers: list, provider_filter: str | None) -> bool:
        """Проверяет, соответствуют ли провайдеры фильтру."""
        if provider_filter is None:
            return True
        non_empty = [p for p in providers if p]
        if not non_empty:
            return False
        return all(p == provider_filter for p in non_empty)

    def _search_external_providers(self, search_text: str, provider_filter: str | None) -> bool:
        """Поиск во внешних провайдерах."""
        # Пробуем AniLiberty
        if provider_filter in (None, PROVIDER_ANILIBERTY):
            try:
                self.log.info("...Try to load from AniLiberty provider")
                title_ids = self._handle_get_titles_from_api(search_text)
                if title_ids:
                    self._handle_found_titles(title_ids, search_text)
                    return True
            except Exception as e:
                self.log.warning(f"AniLiberty provider error: {e}")

        # Пробуем AniMedia
        if provider_filter in (None, PROVIDER_ANIMEDIA):
            return self._search_via_animedia(search_text)

        self.log.warning(f"No titles found anywhere for '{search_text}'")
        self.display.show_error_notification("Search", "No titles found.")
        return False

    def _search_via_animedia(self, search_text: str) -> bool:
        """Асинхронный поиск через AniMedia."""
        from app.qt.workers import AsyncWorker

        try:
            self.log.info("...Try to load from Animedia (async)")
            self._last_search_text = search_text
            self._animedia_worker = AsyncWorker(
                self._deps.animedia_adapter.get_by_title,
                search_text,
                max_titles=5,
            )
            self._animedia_worker.finished.connect(self._on_animedia_result)
            self._animedia_worker.error.connect(self._on_animedia_error)
            self._animedia_worker.start()
            return True
        except Exception as e:
            self.log.error(f"Error starting Animedia worker: {e}")
            return False

    def _handle_found_titles(self, title_ids: list[int], search_text: str) -> None:
        """Обрабатывает найденные тайтлы — отображает в UI."""
        if len(title_ids) == 1:
            self.display.display_info(title_ids[0])  # ← IDE видит тип!
        else:
            self.log.debug(f"Get titles from DB with title_ids: {title_ids}")
            self.display.display_titles(title_ids)  # ← IDE видит тип!

    def _handle_get_titles_from_api(self, search_text: str) -> list[int] | None:
        """Получает тайтлы из API и сохраняет в БД."""
        try:
            keywords = [kw.strip() for kw in search_text.split(',')]

            if len(keywords) == 1 and keywords[0].isdigit():
                data = self.api.get_release_full(int(keywords[0]))
            elif all(kw.isdigit() for kw in keywords):
                data = self.api.get_releases_full([int(kw) for kw in keywords])
            else:
                data = self.api.get_search_by_title(search_text)

            title_list = self._extract_title_list(data)
            if not title_list:
                return None

            title_ids = self.persistence.invoke_database_save(title_list)  # ← IDE видит тип!
            self.ctx.current_data = data
            return title_ids

        except APIClientError as api_error:
            self.log.error(f"API Client Error: {api_error}")
            self.display.show_error_notification("API Error", str(api_error))
        except Exception as e:
            self.log.error(f"Error while fetching title from AL: {e}")
            self.display.show_error_notification("Error", "Unexpected error. Check logs.")

        return None

    def _extract_title_list(self, data) -> list[dict] | None:
        """Извлекает список тайтлов из ответа API."""
        if isinstance(data, dict):
            if 'error' in data:
                self.log.error(data['error'])
                self.display.show_error_notification("API Error", data['error'])
                return None
            if 'list' in data:
                return data['list']
            if 'external_id' in data:
                return [data]
        elif isinstance(data, list):
            return data

        self.log.error("No titles found in the response.")
        self.display.show_error_notification("Error", "No titles found.")
        return None

    def _on_animedia_error(self, message: str) -> None:
        """Callback для ошибок AniMedia worker."""
        self.log.error(f"AniMedia worker error: {message}")
        self.ui.hide_loader()
        self.ui.set_buttons_enabled(True)
        self.display.show_error_notification("AniMedia error", message)

    def _on_animedia_result(self, data: list) -> None:
        """Callback для результатов AniMedia worker."""
        try:
            if not data:
                self.display.show_error_notification("AniMedia", "No titles found.")
                return

            title_list = self._extract_title_list(data)
            if not title_list:
                return

            title_ids = self.persistence.invoke_database_save(title_list)
            self.ctx.current_data = data

            if not title_ids:
                self.display.show_error_notification("AniMedia", "Failed to save titles.")
                return

            self._handle_found_titles(title_ids, self._last_search_text or "")

        except Exception as e:
            self.log.error(f"Error in _on_animedia_result: {e}")
            self.display.show_error_notification("Error", "Unexpected error.")
        finally:
            self.ui.hide_loader()
            self.ui.set_buttons_enabled(True)