# app/qt/app_callbacks.py
from __future__ import annotations

from typing import Dict, Callable, Any


def generate_callbacks(self, all_layout_metadata)-> dict[str, dict[str, Callable]]:
    callbacks = {
        "get_search_by_title": self.get_search_by_title,
        "get_search_by_title_all": self.get_search_by_title_aniliberty,
        "get_search_by_title_am": self.get_search_by_title_animedia,
        "get_update_title": self.get_update_title,
        "get_update_title_all": self.get_update_title_aniliberty,
        "get_update_title_am": self.get_update_title_animedia,
        "get_random_title": self.get_random_title,
        "get_animedia_new_titles": self.get_animedia_new_titles,
        "get_animedia_all_titles": self.get_animedia_all_titles,
        "refresh_display": self.refresh_display,
        "save_playlist_wrapper": self.save_playlist_wrapper,
        "play_playlist_wrapper": self.play_playlist_wrapper,
        "reload_schedule": self.reload_schedule,
    }

    for metadata in all_layout_metadata:
        callback_key = metadata.get("callback_key")
        callback_type = metadata.get("callback_type", "complex")

        if callback_key and callback_type == "simple" and callback_key not in callbacks:
            callbacks[callback_key] = self.generate_simple_callback(callback_key)

    return callbacks

def generate_simple_callback(self, callback_name):
    """Создает простой колбек, который вызывает display_titles с соответствующими параметрами."""

    def simple_callback(*args, **kwargs):
        self.logger.info(f"Вызван простой колбек: {callback_name}")
        if callback_name == "load_previous_titles":
            self.display_titles(show_previous=True)
        elif callback_name == "load_more_titles":
            self.display_titles(show_next=True)
        elif callback_name == "display_titles_text_list":
            self.display_titles(show_mode='titles_list', batch_size=self.titles_list_batch_size)
        elif callback_name == "display_ongoing_list":
            self.display_titles(show_mode='ongoing_list', batch_size=self.titles_list_batch_size)
        elif callback_name == "display_franchises":
            self.display_titles(show_mode='franchise_list', batch_size=self.titles_list_batch_size)
        elif callback_name == "toggle_need_to_see":
            self.display_titles(show_mode='need_to_see_list', batch_size=self.titles_list_batch_size)
        elif callback_name == "display_system":
            self.display_titles(show_mode='system')
        else:
            self.logger.warning(f"Неизвестный колбек: {callback_name}")

    return simple_callback