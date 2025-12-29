# app/qt/proxy_api.py

from typing import Dict, Tuple

# public_name -> (controller_attr, method_name)
PROXY_API: Dict[str, Tuple[str, str]] = {
    # Bootstrap
    "get_cfg": ("bootstrap", "get_cfg"),
    "setup_paths": ("bootstrap", "setup_paths"),
    # Actions
    "restore_state": ("state_runtime", "restore_state"),
    "set_view_state": ("state_runtime", "set_view_state"),
    "get_current_state": ("state_runtime", "get_current_state"),
    "navigate_animedia_mode": ("state_runtime", "navigate_animedia_mode"),
    # Actions
    "get_update_title": ("actions", "get_update_title"),
    "get_search_by_title": ("actions", "get_search_by_title"),
    "get_update_title_animedia": ("actions", "get_update_title_animedia"),
    "get_update_title_aniliberty": ("actions", "get_update_title_aniliberty"),
    "get_search_by_title_animedia": ("actions", "get_search_by_title_animedia"),
    "get_search_by_title_aniliberty": ("actions", "get_search_by_title_aniliberty"),
    # Display
    "init_ui": ("display", "init_ui"),
    "reset_offset": ("display", "reset_offset"),
    "clear_layout": ("display", "clear_layout"),
    "display_info": ("display", "display_info"),
    "display_titles": ("display", "display_titles"),
    "refresh_display": ("display", "refresh_display"),
    "navigate_pagination": ("display", "navigate_pagination"),
    "setup_pagination_ui": ("display", "setup_pagination_ui"),
    "display_titles_in_ui": ("display", "display_titles_in_ui"),
    "create_title_browser": ("display", "create_title_browser"),
    "create_system_browser": ("display", "create_system_browser"),
    "display_titles_for_day": ("display", "display_titles_for_day"),
    "show_error_notification": ("display", "show_error_notification"),
    "create_animedia_titles_browser": ("display", "create_animedia_titles_browser"),
    "create_animedia_schedule_browser": ("display", "create_animedia_schedule_browser"),
    # Callbacks
    "generate_callbacks": ("callback", "generate_callbacks"),
    # AniMedia
    "get_animedia_new_titles": ("animedia", "get_animedia_new_titles"),
    "get_animedia_all_titles": ("animedia", "get_animedia_all_titles"),
    "display_animedia_titles_screen": ("animedia", "display_animedia_titles_screen"),
    "display_animedia_schedule_screen": ("animedia", "display_animedia_schedule_screen"),
    # AniLiberty
    "reload_schedule": ("aniliberty", "reload_schedule"),
    "get_random_title": ("aniliberty", "get_random_title"),
    "fetch_and_process_schedule": ("aniliberty", "fetch_and_process_schedule"),
    # Persistence
    "save_titles_list": ("persistence", "save_titles_list"),
    "save_parsed_data": ("persistence", "save_parsed_data"),
    "invoke_database_save": ("persistence", "invoke_database_save"),
    # Torrent
    "save_torrent_wrapper": ("torrent", "save_torrent_wrapper"),
    # Poster
    "sanitize_filename": ("poster", "sanitize_filename"),
    "clear_previous_posters": ("poster", "clear_previous_posters"),
    "get_poster_or_placeholder": ("poster", "get_poster_or_placeholder"),
    # Player
    "play_link": ("player", "play_link"),
    "open_web_link": ("player", "open_web_link"),
    "save_playlist_wrapper": ("player", "save_playlist_wrapper"),
    "play_playlist_wrapper": ("player", "play_playlist_wrapper"),
    "ensure_playlist_bundle": ("player", "ensure_playlist_bundle"),
    "get_mini_browser_command": ("player", "get_mini_browser_command"),
}

