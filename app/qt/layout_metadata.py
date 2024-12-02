# layout_metadata.py

all_layout_metadata = [
    # Верхний лейаут
    {"layout": "top", "type": "input_field", "placeholder": "TITLE ID OR NAME", "min_width": 150, "max_width": 255, "callback_type": "complex",
     "widget_key": "title_input"},
    {"layout": "top", "type": "button", "text": "FIND", "callback_key": "get_search_by_title", "callback_type": "complex", "color_index": 0},
    {"layout": "top", "type": "button", "text": "RANDOM", "callback_key": "get_random_title", "callback_type": "complex", "color_index": 0},
    # Кнопки дней недели
    *[{"layout": "top", "type": "button", "text": day, "callback_key": f"display_titles_for_day_{i}", "callback_type": "complex", "color_index": 1}
      for i, day in enumerate(["MO", "TU", "WE", "TH", "FR", "SA", "SU"])],

    {"layout": "top", "type": "button", "text": "RELOAD", "callback_key": "reload_schedule", "callback_type": "complex", "color_index": 0},
    {"layout": "top", "type": "dropdown", "items": ["fhd", "hd", "sd"], "callback_key": "refresh_display", "callback_type": "complex", "widget_key": "quality_dropdown"},
    # Нижний лейаут
    {"layout": "bottom", "type": "button", "text": "LOAD PREV", "callback_key": "load_previous_titles", "callback_type": "simple", "color_index": 1},
    {"layout": "bottom", "type": "button", "text": "LOAD MORE", "callback_key": "load_more_titles", "callback_type": "simple", "color_index": 4},
    {"layout": "bottom", "type": "button", "text": "TITLES LIST", "callback_key": "display_titles_text_list", "callback_type": "simple", "color_index": 7},
    {"layout": "bottom", "type": "button", "text": "FRANCHISES", "callback_key": "display_franchises", "callback_type": "simple", "color_index": 8},
    {"layout": "bottom", "type": "button", "text": "NEED TO SEE", "callback_key": "toggle_need_to_see", "callback_type": "simple", "color_index": 1},
    {"layout": "bottom", "type": "button", "text": "SYSTEM", "callback_key": "display_system", "callback_type": "simple", "color_index": 2},
    {"layout": "bottom", "type": "button", "text": "SAVE", "callback_key": "save_playlist_wrapper", "callback_type": "simple", "color_index": 4},
    {"layout": "bottom", "type": "button", "text": "PLAY", "callback_key": "play_playlist_wrapper", "callback_type": "simple", "color_index": 4}
]

# Добавляем новый show_mode с ключом и описанием
show_mode_metadata = {
    'system': {"create_method": "create_system_widget", "description": "System View", "batch_size": None, "columns": None, "generator": "_generate_system_html", "data_fetcher": 'system'},
    'franchise_list': {"create_method": "create_list_widget", "description": "Franchise List", "batch_size": 12, "columns": 4, "generator": "_generate_list_html", "data_fetcher": "get_franchises_from_db"},
    'titles_list': {"create_method": "create_list_widget", "description": "Titles List", "batch_size": 12, "columns": 4, "generator": "_generate_list_html", "data_fetcher": "get_titles_list_from_db"},
    'need_to_see_list': {"create_method": "create_list_widget", "description": "Need to See List", "batch_size": 12, "columns": 4, "generator": "_generate_list_html", "data_fetcher": "get_need_to_see_from_db"},
    'one_title': {"create_method": "create_one_title_widget", "description": "One Title", "batch_size": None, "columns": None, "generator": "_generate_one_title_html", "data_fetcher": ''},
    'default': {"create_method": "create_default_widget", "description": "Default View", "batch_size": 2, "columns": 2, "generator": "_generate_default_html", "data_fetcher": ''}
}
