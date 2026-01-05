# app/qt/app_constants.py
from __future__ import annotations


# --- Security hashes (executables) ---
# Hash of compiled executable
VLC_PLAYER_HASH = "d2ee562a6a1271103a6362db8eabace95b8b35fcf9b3aa0364bcb3cb7430e0b1"
# Hash of compiled executable
MPV_PLAYER_HASH = "2a8b0896144c9a1a1b633c2e001002cec8aaa799ab7f6855f807932d858661ba"
# Hash of compiled executable
MINI_BROWSER_HASH = "7e7b820e4ea349c3a443a759a34fe0ff105c5d01b4bf9c01ddf76029286da324"

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
