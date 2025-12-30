# app/qt/controllers/callback.py
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable, Any

if TYPE_CHECKING:
    from logging import Logger
    from app.qt.app_context import AppContext


@dataclass
class CallbackControllerDeps:
    """Явные зависимости CallbackController"""
    logger: Logger
    context: AppContext
    layout_metadata: list[dict]

    # Controller getters (для генерации callbacks)
    get_actions: Callable[[], Any]
    get_display: Callable[[], Any]
    get_aniliberty: Callable[[], Any]
    get_animedia: Callable[[], Any]
    get_player: Callable[[], Any]


class CallbackController:
    """
    Контроллер для генерации UI callbacks.
    Создаёт маппинг callback_key -> функция.
    """

    def __init__(self, deps: CallbackControllerDeps):
        self._deps = deps

    @property
    def log(self) -> Logger:
        return self._deps.logger

    @property
    def ctx(self) -> AppContext:
        return self._deps.context

    # === Public API ===

    def generate_callbacks(self) -> dict[str, Callable]:
        """Генерирует все callbacks для UI."""
        callbacks = {}

        # Добавляем основные callbacks
        callbacks.update(self._get_search_callbacks())
        callbacks.update(self._get_update_callbacks())
        callbacks.update(self._get_aniliberty_callbacks())
        callbacks.update(self._get_animedia_callbacks())
        callbacks.update(self._get_display_callbacks())
        callbacks.update(self._get_player_callbacks())
        callbacks.update(self._get_day_callbacks())

        # Добавляем простые callbacks из layout metadata
        callbacks.update(self._get_simple_callbacks(callbacks))

        return callbacks

    # === Private: Callback Groups ===

    def _get_search_callbacks(self) -> dict[str, Callable]:
        """Callbacks для поиска."""
        actions = self._deps.get_actions()
        return {
            "get_search_by_title": actions.get_search_by_title,
            "get_search_by_title_all": actions.get_search_by_title_aniliberty,
            "get_search_by_title_am": actions.get_search_by_title_animedia,
        }

    def _get_update_callbacks(self) -> dict[str, Callable]:
        """Callbacks для обновления."""
        actions = self._deps.get_actions()
        return {
            "get_update_title": actions.get_update_title,
            "get_update_title_all": actions.get_update_title_aniliberty,
            "get_update_title_am": actions.get_update_title_animedia,
        }

    def _get_aniliberty_callbacks(self) -> dict[str, Callable]:
        """Callbacks для AniLiberty."""
        aniliberty = self._deps.get_aniliberty()
        return {
            "get_random_title": aniliberty.get_random_title,
            "reload_schedule": aniliberty.reload_schedule,
        }

    def _get_animedia_callbacks(self) -> dict[str, Callable]:
        """Callbacks для AniMedia."""
        animedia = self._deps.get_animedia()
        return {
            "get_animedia_new_titles": animedia.get_animedia_new_titles,
            "get_animedia_all_titles": animedia.get_animedia_all_titles,
        }

    def _get_display_callbacks(self) -> dict[str, Callable]:
        """Callbacks для отображения."""
        display = self._deps.get_display()
        return {
            "refresh_display": display.refresh_display,
        }

    def _get_player_callbacks(self) -> dict[str, Callable]:
        """Callbacks для плеера."""
        player = self._deps.get_player()
        return {
            "save_playlist_wrapper": player.save_playlist_wrapper,
            "play_playlist_wrapper": player.play_playlist_wrapper,
        }

    def _get_day_callbacks(self) -> dict[str, Callable]:
        """Callbacks для дней недели."""
        display = self._deps.get_display()
        days = ["MO", "TU", "WE", "TH", "FR", "SA", "SU"]

        callbacks = {}
        for i, day in enumerate(days):
            day_num = i + 1
            callbacks[f"display_titles_for_day_{i}"] = \
                lambda checked, d=day_num: display.display_titles_for_day(d)

        return callbacks

    def _get_simple_callbacks(self, existing: dict) -> dict[str, Callable]:
        """Генерирует простые callbacks из layout metadata."""
        callbacks = {}
        display = self._deps.get_display()

        for metadata in self._deps.layout_metadata:
            callback_key = metadata.get("callback_key")
            callback_type = metadata.get("callback_type", "complex")

            if not callback_key:
                continue
            if callback_key in existing:
                continue
            if callback_type != "simple":
                continue

            callbacks[callback_key] = self._create_simple_callback(callback_key, display)

        return callbacks

    def _create_simple_callback(
            self,
            callback_name: str,
            display,
    ) -> Callable:
        """Создаёт простой callback."""

        def callback(*args, **kwargs):
            self.log.info(f"Simple callback: {callback_name}")

            if callback_name == "load_previous_titles":
                display.display_titles(show_previous=True)

            elif callback_name == "load_more_titles":
                display.display_titles(show_next=True)

            elif callback_name == "display_titles_text_list":
                display.display_titles(
                    show_mode='titles_list',
                    batch_size=self.ctx.titles_list_batch_size,
                )

            elif callback_name == "display_ongoing_list":
                display.display_titles(
                    show_mode='ongoing_list',
                    batch_size=self.ctx.titles_list_batch_size,
                )

            elif callback_name == "display_franchises":
                display.display_titles(
                    show_mode='franchise_list',
                    batch_size=self.ctx.titles_list_batch_size,
                )

            elif callback_name == "toggle_need_to_see":
                display.display_titles(
                    show_mode='need_to_see_list',
                    batch_size=self.ctx.titles_list_batch_size,
                )

            elif callback_name == "display_system":
                display.display_titles(show_mode='system')

            else:
                self.log.warning(f"Unknown callback: {callback_name}")

        return callback