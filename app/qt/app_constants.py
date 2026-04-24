# app/qt/app_constants.py
from __future__ import annotations


# --- Security hashes (executables) ---
# Hash of compiled executable
VLC_PLAYER_HASH = "10ffd91b872a8002eabbfa3199fa906e58de12ee858a7f71a3f10513e7bc42b3"
# Hash of compiled executable
MPV_PLAYER_HASH = "3b6b1c4a7a59d69b40d2d2dec00b6e33a44ef308196c960922f94485f6358a14"
# Hash of compiled executable
MINI_BROWSER_HASH = "4fc6e5e3e7ce72cc86a04b5f197ca798eb613c4d9487fc66f4e0a3b79368c6ed"

# --- Providers ---
PROVIDER_ANILIBERTY = "aniliberty"
PROVIDER_ANIMEDIA = "animedia"

# --- UI show modes ---
SHOW_DEFAULT = "default"
SHOW_SYSTEM = "system"
SHOW_ONE_TITLE = "one_title"
SHOW_AM_SCHEDULE = "animedia_schedule"
SHOW_AM_TITLES = "animedia_titles"

# --- AniMedia cache keys ---
SCHEDULE_KEY: str = "am_schedule_cache"
ALL_TITLES_KEY: str = "am_all_titles_cache"

# --- App constants
DEFAULT_TEMPLATE = "default"
DOWNLOAD_AFTER_AGE = 7 # Days
FINAL_AGE = 90 # Days
APP_WIDTH = 1000
APP_HEIGHT = 800
APP_X_POS = 100
APP_Y_POS = 100

# --- State runtime
LIST_MODES = {"titles_list", "franchise_list", "need_to_see_list", "ongoing_list"}
