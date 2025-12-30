# app/qt/controllers/callbacks.py
from __future__ import annotations

from typing import Any, Callable


class CallbackController:
    """
    Переходный контроллер (stage-2/3):
    - svc: доступ к db/api/ui/logger/config/playlist
    - app: доступ к orchestration-методам (display_titles, show_error_notification, invoke_database_save, ...)
    """

    def __init__(self, app: Any, svc: Any, layout: Any):
        self.app = app
        self.svc = svc
        self.layout = layout

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

    def generate_callbacks(self) -> dict[str, Callable]:
        callbacks = {
            "get_search_by_title": self.app.get_search_by_title,
            "get_search_by_title_all": self.app.get_search_by_title_aniliberty,
            "get_search_by_title_am": self.app.get_search_by_title_animedia,
            "get_update_title": self.app.get_update_title,
            "get_update_title_all": self.app.get_update_title_aniliberty,
            "get_update_title_am": self.app.get_update_title_animedia,
            "get_random_title": self.app.get_random_title,
            "get_animedia_new_titles": self.app.get_animedia_new_titles,
            "get_animedia_all_titles": self.app.get_animedia_all_titles,
            "refresh_display": self.app.refresh_display,
            "save_playlist_wrapper": self.app.save_playlist_wrapper,
            "play_playlist_wrapper": self.app.play_playlist_wrapper,
            "reload_schedule": self.app.reload_schedule,
        }

        for metadata in self.layout:
            callback_key = metadata.get("callback_key")
            callback_type = metadata.get("callback_type", "complex")

            if callback_key and callback_type == "simple" and callback_key not in callbacks:
                callbacks[callback_key] = self._generate_simple_callback(callback_key)

        days_of_week = ["MO", "TU", "WE", "TH", "FR", "SA", "SU"]
        for i, day in enumerate(days_of_week):
            callbacks[f"display_titles_for_day_{i}"] = lambda checked, i=i: self.app.display_titles_for_day(i + 1)

        return callbacks

    def _generate_simple_callback(self, callback_name):
        """Создает простой колбек, который вызывает display_titles с соответствующими параметрами."""

        def simple_callback(*args, **kwargs):
            self.log.info(f"Вызван простой колбек: {callback_name}")
            if callback_name == "load_previous_titles":
                self.app.display_titles(show_previous=True)
            elif callback_name == "load_more_titles":
                self.app.display_titles(show_next=True)
            elif callback_name == "display_titles_text_list":
                self.app.display_titles(show_mode='titles_list', batch_size=self.app.titles_list_batch_size)
            elif callback_name == "display_ongoing_list":
                self.app.display_titles(show_mode='ongoing_list', batch_size=self.app.titles_list_batch_size)
            elif callback_name == "display_franchises":
                self.app.display_titles(show_mode='franchise_list', batch_size=self.app.titles_list_batch_size)
            elif callback_name == "toggle_need_to_see":
                self.app.display_titles(show_mode='need_to_see_list', batch_size=self.app.titles_list_batch_size)
            elif callback_name == "display_system":
                self.app.display_titles(show_mode='system')
            else:
                self.log.warning(f"Неизвестный колбек: {callback_name}")

        return simple_callback