# layout_metadata.py

# 1. Adding a New Button:
#    Example in `all_layout_metadata`:
#    {
#        "layout": "bottom",
#        "type": "button",
#        "text": "NEW BUTTON",
#        "callback_key": "new_button_callback",
#        "callback_type": "simple",
#        "color_index": 5
#    },
#    {
#        "layout": "top",
#        "type": "split_button",
#        "text": "FIND",
#        "default_callback_key": "get_search_by_title",
#        "menu_items": [
#            {
#                "text": "AniLiberty",
#                "callback_key": "get_search_by_title_al"
#            },
#            {
#                "text": "AniMedia",
#                "callback_key": "get_search_by_title_am"
#            }
#            ],
#        "callback_type": "complex",\
#        "color_index": 0,
#     },
#
# Parameter Descriptions:
# - "layout": Determines where the button will be positioned on the screen (e.g., "top", "bottom").
# - "type": The type of UI element, in this case - "button".
# - "text": The label text shown on the button.
# - "callback_key": A unique identifier used to link the button to a callback function.
# - "callback_type": The type of callback action - can be "simple" for basic functions or "complex" for more elaborate operations.
# - "color_index": Defines the button's color index for UI appearance purposes.

# 2. Adding a New Display Mode (`show_mode`):
#    Example in `show_mode_metadata`:
#    'new_mode': {
#        "create_method": "create_new_widget",
#        "description": "New Mode Description",
#        "batch_size": 10,
#        "columns": 3,
#        "generator": "_generate_new_html",
#        "data_fetcher": "get_new_data_from_db"
#    }
#
# Parameter Descriptions:
# - "create_method": Specifies the method responsible for creating the widget. Possible values include:
#   * "create_system_widget"
#   * "create_list_widget"
#   * "create_one_title_widget"
#   * "create_default_widget"
# - "description": Describes the mode, used for logging or UI display.
# - "batch_size": Number of data items to load per batch. Use `None` if not applicable.
# - "columns": Number of columns used for displaying the content. This is relevant when displaying lists of items.
# - "generator": The method that generates the HTML for rendering the UI. Possible values include:
#   * "_generate_system_html"
#   * "_generate_list_html"
#   * "_generate_one_title_html"
#   * "_generate_default_html"
# - "data_fetcher": Function used to fetch data for the mode. Possible values include:
#   * "get_titles_list_from_db"
#   * "get_franchises_from_db"
#   * "get_need_to_see_from_db"
#   * Other custom functions.

# 3. Adding a Callback for the New Button:
#    Example in `app.py`:
#    Add a new branch in the `generate_simple_callback` method:
#    def generate_simple_callback(self, callback_name):
#        ...
#        elif callback_name == "new_button_callback":
#            # Call the relevant function to handle the action of the new button
#            self.display_titles(show_mode='new_mode', batch_size=self.titles_list_batch_size)
#
# Notes:
# - Ensure that the `callback_key` specified in the button definition matches the `callback_name` here.
# - Implement the logic to handle the button action properly, such as calling a display function or fetching data from the database.


all_layout_metadata = [
    {"layout": "top", "type": "input_field", "placeholder": "TITLE ID OR NAME", "min_width": 100, "max_width": 255, "callback_type": "complex","widget_key": "title_input"},
    {"layout": "top","type": "split_button","text": "FIND", "default_callback_key": "get_search_by_title","menu_items": [{"text": "AniLiberty", "callback_key": "get_search_by_title_al"},{"text": "AniMedia", "callback_key": "get_search_by_title_am"}],"callback_type": "complex","color_index": 0,},
    {"layout": "top","type": "split_button","text": "UT⮂", "default_callback_key": "get_update_title","menu_items": [{"text": "AniLiberty", "callback_key": "get_update_title_al"},{"text": "AniMedia", "callback_key": "get_update_title_am"}],"callback_type": "complex","color_index": 0,},
    {"layout": "top", "type": "button", "text": "RANDOM", "callback_key": "get_random_title", "callback_type": "complex", "color_index": 0},
    *[{"layout": "top", "type": "button", "text": day, "callback_key": f"display_titles_for_day_{i}", "callback_type": "complex", "color_index": 1}
      for i, day in enumerate(["MO", "TU", "WE", "TH", "FR", "SA", "SU"])],
    {"layout": "top", "type": "button", "text": "RS⮂", "callback_key": "reload_schedule", "callback_type": "complex", "color_index": 0},
    {"layout": "top", "type": "dropdown", "items": ["fhd", "hd", "sd"], "callback_key": "refresh_display", "callback_type": "complex", "widget_key": "quality_dropdown"},
    {"layout": "bottom", "type": "button", "text": "LOAD PREV", "callback_key": "load_previous_titles", "callback_type": "simple", "color_index": 1},
    {"layout": "bottom", "type": "button", "text": "LOAD MORE", "callback_key": "load_more_titles", "callback_type": "simple", "color_index": 4},
    {"layout": "bottom", "type": "button", "text": "ONGOING", "callback_key": "display_ongoing_list", "callback_type": "simple", "color_index": 6},
    {"layout": "bottom", "type": "button", "text": "TITLES LIST", "callback_key": "display_titles_text_list", "callback_type": "simple", "color_index": 7},
    {"layout": "bottom", "type": "button", "text": "FRANCHISES", "callback_key": "display_franchises", "callback_type": "simple", "color_index": 8},
    {"layout": "bottom", "type": "button", "text": "NEED TO SEE", "callback_key": "toggle_need_to_see", "callback_type": "simple", "color_index": 1},
    {"layout": "bottom", "type": "button", "text": "SYSTEM", "callback_key": "display_system", "callback_type": "simple", "color_index": 2},
    {"layout": "bottom", "type": "button", "text": "SAVE", "callback_key": "save_playlist_wrapper", "callback_type": "simple", "color_index": 4},
    {"layout": "bottom", "type": "button", "text": "PLAY", "callback_key": "play_playlist_wrapper", "callback_type": "simple", "color_index": 4}
]

show_mode_metadata = {
    'system': {"create_method": "create_system_widget", "description": "System View", "batch_size": None, "columns": None, "generator": "_generate_system_html", "data_fetcher": 'system'},
    'franchise_list': {"create_method": "create_list_widget", "description": "Franchise List", "batch_size": 12, "columns": 4, "generator": "_generate_list_html", "data_fetcher": "get_franchises_from_db"},
    'titles_list': {"create_method": "create_list_widget", "description": "Titles List", "batch_size": 12, "columns": 4, "generator": "_generate_list_html", "data_fetcher": "get_titles_list_from_db"},
    'ongoing_list': {"create_method": "create_list_widget", "description": "Ongoing List", "batch_size": 12, "columns": 4, "generator": "_generate_list_html", "data_fetcher": "get_ongoing_titles"},
    'titles_genre_list': {"create_method": "create_list_widget", "description": "Titles by Genre", "batch_size": 12, "columns": 4, "generator": "_generate_list_html", "data_fetcher": "titles_genre_list"},
    'titles_team_member_list': {"create_method": "create_list_widget", "description": "Titles by Team Member", "batch_size": 12, "columns": 4, "generator": "_generate_list_html", "data_fetcher": "titles_team_member_list"},
    'titles_year_list': {"create_method": "create_list_widget", "description": "Titles by Year", "batch_size": 12, "columns": 4, "generator": "_generate_list_html", "data_fetcher": "titles_year_list"},
    'titles_status_list': {"create_method": "create_list_widget", "description": "Titles by Status", "batch_size": 12, "columns": 4, "generator": "_generate_list_html", "data_fetcher": "titles_status_list"},
    'need_to_see_list': {"create_method": "create_list_widget", "description": "Need to See List", "batch_size": 12, "columns": 4, "generator": "_generate_list_html", "data_fetcher": "get_need_to_see_from_db"},
    'one_title': {"create_method": "create_one_title_widget", "description": "One Title", "batch_size": None, "columns": None, "generator": "_generate_one_title_html", "data_fetcher": ''},
    'default': {"create_method": "create_default_widget", "description": "Default View", "batch_size": 2, "columns": 2, "generator": "_generate_default_html", "data_fetcher": ''}
}
