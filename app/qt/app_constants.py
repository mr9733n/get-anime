# app/qt/app_constants.py
from __future__ import annotations


# --- Security hashes (executables) ---
VLC_PLAYER_HASH = "2b3e49bce530b0403ad5f7617a06fea62f437cfc0d4eb2f01c7784cb4c78fb80"
MPV_PLAYER_HASH = "b25e49c0a8d7f4f7ae23a9316154aa357c88f2b2a095f2d1829534db0924a66c"
MINI_BROWSER_HASH = "5b03e0919016a3af239eaf92b6507b3ffd80a76f7dfa6d40aa0f48e1f2dfdf1c"

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