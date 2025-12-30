# app/qt/app_constants.py
from __future__ import annotations


# --- Security hashes (executables) ---
# Hash of compiled executable
VLC_PLAYER_HASH = "c6a14959dabf6d1c5cee0172c183ecc3ba465bd07a5c655b1ccf38bfc79d5e73"
# Hash of compiled executable
MPV_PLAYER_HASH = "c2bf50b35261d3117e7ac781d0c52c7ae8f0967e4c2b389841c6a3eba06b32b0"
# Hash of compiled executable
MINI_BROWSER_HASH = "b9ab020afbf6bd068f240b6733f6167681e509f5a168abb564b39d4765485b85"

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
