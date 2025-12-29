# app/qt/controllers/actions.py
from __future__ import annotations

from typing import Any, Optional, Iterable

from app.qt.app_constants import PROVIDER_ANILIBERTY, PROVIDER_ANIMEDIA
from app.qt.app_exceptions import APIClientError
from app.qt.app_state import TitleRef
from providers.animedia.v0.qt_async_worker import AsyncWorker


class ActionsController:
    """
    Переходный контроллер (stage-2/3):
    - svc: доступ к db/api/ui/logger/config/playlist
    - app: доступ к orchestration-методам (display_titles, show_error_notification, invoke_database_save, ...)
    """

    def __init__(self, app: Any, svc: Any):
        self.app = app
        self.svc = svc

    @property
    def db(self):
        return self.svc.db

    @property
    def ui(self):
        return self.svc.ui

    @property
    def log(self):
        return self.svc.logger

    @property
    def api(self):
        return self.svc.api

    def get_update_title(self):
        """Обновление с авто-определением провайдера."""
        return self._update_titles(provider_filter=None)


    def get_update_title_aniliberty(self):
        """Обновление только через AniLiberty."""
        return self._update_titles(provider_filter=PROVIDER_ANILIBERTY)


    def get_update_title_animedia(self):
        """Обновление только через AniMedia."""
        return self._update_titles(provider_filter=PROVIDER_ANIMEDIA)


    def get_search_by_title(self):
        """Поиск тайтла: локальная БД → AniLiberty → Animedia."""
        return self._search_by_title(provider_filter=None, search_text=None)


    def get_search_by_title_aniliberty(self):
        """Поиск тайтла: локальная БД → AniLiberty."""
        return self._search_by_title(provider_filter=PROVIDER_ANILIBERTY, search_text=None)


    def get_search_by_title_animedia(self, search_text=None):
        """Поиск тайтла: локальная БД (где провайдер = Animedia) → Animedia (async)."""
        if search_text:
            return self._search_by_title(provider_filter=PROVIDER_ANIMEDIA, search_text=search_text)
        return self._search_by_title(provider_filter=PROVIDER_ANIMEDIA, search_text=None)

    def _resolve_titles_for_query(self, search_text: str) -> list[TitleRef]:
        """Ищет тайтлы в БД и приводит результат к единому виду."""
        titles_list = self.db.get_titles_search_query(search_text)
        results: list[TitleRef] = []

        for t in titles_list:
            title_id = t.get("title_id")
            name_ru = t.get("name_ru")
            name_en = t.get("name_en")
            providers = t.get("providers", []) or []

            if providers:
                primary = providers[0]
                provider = primary.get("provider")
                provider_name = primary.get("name")
                external_id = primary.get("external_id")
            else:
                provider = None
                external_id = None

            self.log.info(
                f"Found title: {title_id}, {name_ru}, {name_en}, {provider}, {provider_name}, {external_id}"
            )

            if title_id is None:
                continue

            results.append(
                TitleRef(
                    title_id=title_id,
                    name_ru=name_ru,
                    name_en=name_en,
                    provider=provider,
                    provider_name=provider_name,
                    external_id=external_id,
                )
            )

        return results

    def _update_titles(self, provider_filter: str | None) -> bool:
        """
        Общая логика обновления тайтлов.
        :param provider_filter:
            None               → авто (по полю provider у тайтла)
            PROVIDER_ANILIBERTY → только AniLiberty
            PROVIDER_ANIMEDIA   → только AniMedia
        """
        try:
            self.ui.show_loader("Updating title info...")
            self.ui.set_buttons_enabled(False)

            search_text = self.app.title_search_entry.text().strip()
            if not search_text:
                if self.app.current_title_ids:
                    search_text = ",".join(str(tid) for tid in self.app.current_title_ids)
                elif self.app.current_title_id is not None:
                    search_text = str(self.app.current_title_id)
                else:
                    self.log.warning("Unable to update title(s): missing title ID(s)")
                    self.app.show_error_notification("Error", "Unable to update title(s): missing title ID(s)")
                    return False
                self.log.debug(f"Used current title_id(s): {search_text} for update")
            else:
                self.app.title_search_entry.clear()

            self.log.info(f"Updating title(s). Keywords: {search_text}")
            titles = self._resolve_titles_for_query(search_text)
            if not titles:
                self.log.warning(f"No titles found in DB for update by query: {search_text}")
                self.app.show_error_notification("Update", "No titles found for update.")
                return False

            for tref in titles:
                self.log.info(
                    f"Updating title: {tref.title_id}, {tref.name_ru}, {tref.name_en}, "
                    f"{tref.provider}, {tref.external_id}"
                )
                if provider_filter is not None and tref.provider != provider_filter:
                    self.log.info(
                        f"Skip title_id={tref.title_id}: provider={tref.provider}, filter={provider_filter}"
                    )
                    continue
                if tref.provider == PROVIDER_ANILIBERTY or provider_filter == PROVIDER_ANILIBERTY:
                    query_name = str(tref.external_id or tref.title_id) or tref.name_en or tref.name_ru
                    self.log.info(f"Updating via AniLiberty API: query={query_name}")
                    title_ids = self._handle_get_titles_from_api(query_name)
                    if title_ids:
                        self._handle_found_titles(title_ids, query_name)
                    continue
                if tref.provider == PROVIDER_ANIMEDIA or provider_filter == PROVIDER_ANIMEDIA:
                    query_name = tref.name_en or tref.name_ru or str(tref.external_id or tref.title_id)

                    self.log.info(f"Updating via AniMedia: query={query_name}")
                    self._last_search_text = query_name
                    self.animedia_worker = AsyncWorker(
                        self.app.animedia_adapter.get_by_title,
                        query_name,
                        max_titles=5,
                    )
                    self.animedia_worker.finished.connect(self._on_animedia_result)
                    self.animedia_worker.error.connect(self.on_animedia_error)
                    self.animedia_worker.start()
                    continue

                self.log.warning(
                    f"Unknown or missing provider for title_id={tref.title_id}: {tref.provider} "
                    f"(filter={provider_filter})"
                )

            return True

        except Exception as e:
            self.log.error(f"Error on update title(s): {e}")
            return False
        finally:
            # TODO: для асинхронного пути Animedia надо делать внутри рутин
            self.ui.hide_loader()
            self.ui.set_buttons_enabled(True)

    def _search_by_title(self, provider_filter: str | None, search_text: str | None) -> bool:
        """
        Общая логика поиска тайтлов по названию.
        :param provider_filter:
            None                → авто: ищем в БД у всех, fallback AniLiberty + Animedia
            PROVIDER_ANILIBERTY → фокус на AniLiberty (БД + AniLiberty)
            PROVIDER_ANIMEDIA   → фокус на Animedia (БД + Animedia)
        """
        try:
            self.ui.show_loader("Fetching by title...")
            self.ui.set_buttons_enabled(False)

            if not search_text:
                search_text = self.app.title_search_entry.text().strip()
            self.app.title_search_entry.clear()
            if not search_text:
                return False

            self.log.debug(f"keywords: {search_text}")
            title_ids, providers = self.db.get_titles_by_keywords(search_text)

            def providers_match_filter() -> bool:
                if provider_filter is None:
                    return True
                non_empty = [p for p in providers if p]
                if not non_empty:
                    return False
                return all(p == provider_filter for p in non_empty)

            if title_ids and providers_match_filter():
                self.log.info(
                    f"Found {len(title_ids)} titles in local DB for '{search_text}' "
                    f"(filter={provider_filter})"
                )
                self._handle_found_titles(title_ids, search_text)
                return True

            self.log.info(
                f"No suitable titles in local DB for '{search_text}' (filter={provider_filter})."
            )

            if provider_filter in (None, PROVIDER_ANILIBERTY):
                try:
                    self.log.info("...Try to load from AniLiberty provider")
                    title_ids = self._handle_get_titles_from_api(search_text)
                    if title_ids:
                        self.log.info(
                            f"AniLiberty returned {len(title_ids)} titles for '{search_text}'"
                        )
                        self._handle_found_titles(title_ids, search_text)
                        return True
                except Exception as e:
                    self.log.warning(f"AniLiberty provider error: {e}")

            if provider_filter in (None, PROVIDER_ANIMEDIA):
                try:
                    self.log.info("...Try to load from Animedia (async)")
                    self._last_search_text = search_text
                    self.animedia_worker = AsyncWorker(
                        self.app.animedia_adapter.get_by_title,
                        search_text,
                        max_titles=5,
                    )
                    self.animedia_worker.finished.connect(self._on_animedia_result)
                    self.animedia_worker.error.connect(self.on_animedia_error)
                    self.animedia_worker.start()
                    return True
                except Exception as e:
                    self.log.error(f"Error starting Animedia worker: {e}")
                    return False

            self.log.warning(f"No titles found anywhere for '{search_text}'")
            self.app.show_error_notification("Search", "No titles found.")
            return False

        except Exception as e:
            self.log.error(f"Error while fetching get_search_by_title: {e}")
            return False
        finally:
            # TODO: для асинхронного пути Animedia надо делать внутри рутин
            self.ui.hide_loader()
            self.ui.set_buttons_enabled(True)

    def _handle_found_titles(self, title_ids, search_text):
        if len(title_ids) == 1:
            self.app.display_info(title_ids[0])
        else:
            self.log.debug(f"Get titles from DB with title_ids: {title_ids} by keyword {search_text}")
            self.app.display_titles(title_ids)

    def _handle_get_titles_from_api(self, search_text) -> list[int] | None:
        try:
            keywords = search_text.split(',')
            keywords = [kw.strip() for kw in keywords]
            if len(keywords) == 1 and keywords[0].isdigit():
                title_id = int(keywords[0])
                data = self.api.get_release_full(title_id)
            elif all(kw.isdigit() for kw in keywords):
                title_ids = [int(kw) for kw in keywords]
                data = self.api.get_releases_full(title_ids)
            else:
                data = self.api.get_search_by_title(search_text)

            if isinstance(data, dict) and 'error' in data:
                self.log.error(data['error'])
                self.app.show_error_notification("API Error", data['error'])
                return

            if isinstance(data, dict) and 'list' in data:
                title_list = data['list']
            elif isinstance(data, dict) and 'external_id' in data:
                title_list = [data]
            elif isinstance(data, list):
                title_list = data
            else:
                self.log.error("No titles found in the response.")
                self.app.show_error_notification("Error", "No titles found in the response.")
                return

            if not title_list:
                self.log.error("No titles found in the response.")
                self.app.show_error_notification("Error", "No titles found in the response.")
                return

            self.log.debug(f"Processing title data: {title_list}")
            title_ids = self.app.invoke_database_save(title_list)

            self.current_data = data
            return title_ids
        except APIClientError as api_error:
            self.log.error(f"API Client Error: {api_error}")
            self.app.show_error_notification("API Error", str(api_error))
        except Exception as e:
            self.log.error(f"Error while fetching title from AL: {e}")
            self.app.show_error_notification("Error", "Unexpected error. Check logs for details.")

    def on_animedia_error(self, message: str):
        try:
            self.log.error(f"AniMedia worker error: {message}")
            self.ui.hide_loader()
            self.ui.set_buttons_enabled(True)
            self.app.show_error_notification("AniMedia error", message)

        except Exception as msg:
            self.log.error(f"Unexpected error in _on_animedia_error: {msg}")
            self.app.show_error_notification("Error", f"Unexpected error. Check logs for details {msg}")
        finally:
            self.ui.hide_loader()
            self.ui.set_buttons_enabled(True)

    def _on_animedia_result(self, data: list) -> list[int] | None:
        """
        `data` – список словарей, который вернул `get_by_title`.
        Здесь можно сохранить в БД, отобразить в UI и т.п.
        """
        try:
            if not data:
                self.app.show_error_notification("AniMedia", "No titles found on Animedia.")
                return

            self.log.info(f"Animedia returned {len(data)} items")

            if isinstance(data, dict) and 'error' in data:
                self.log.error(data['error'])
                self.app.show_error_notification("AniMedia scraper Error", data['error'])
                return None

            if isinstance(data, dict) and 'list' in data:
                title_list = data['list']
            elif isinstance(data, dict) and 'external_id' in data:
                title_list = [data]
            elif isinstance(data, list):
                title_list = data
            else:
                self.log.error("No titles found in the response.")
                self.app.show_error_notification("Error", "No titles found in the response.")
                return

            if not title_list:
                self.log.error("No titles found in the response.")
                self.app.show_error_notification("Error", "No titles found in the response.")
                return

            self.log.debug(f"Processing title data: {title_list}")
            title_ids = self.app.invoke_database_save(title_list)
            self.current_data = data

            if not title_ids:
                self.log.error("No title_ids returned after saving Animedia titles")
                self.app.show_error_notification("AniMedia", "Failed to save titles to database.")
                return

            search_text = getattr(self, "_last_search_text", "")
            self._handle_found_titles(title_ids, search_text)

        except Exception as e:
            self.log.error(f"Error while fetching title AM: {e}")
            self.app.show_error_notification("Error", "Unexpected error. Check logs for details.")
        finally:
            self.ui.hide_loader()
            self.ui.set_buttons_enabled(True)