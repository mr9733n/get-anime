# app/qt/app_constants.py
from __future__ import annotations


# --- Security hashes (executables) ---
# Hash of compiled executable
VLC_PLAYER_HASH = "4d798e851aba59aba38df447ee87ecc6984f25546e53ccf9335f7adc540d990b"
# Hash of compiled executable
MPV_PLAYER_HASH = "f6a4a38df7c810bb0fee14bfb135faf83c4ed8e69fbffe1c1d75dd2d771e42c8"
# Hash of compiled executable
MINI_BROWSER_HASH = "3efaaec9afd88cf422f0a79f5b49529fa5ffebf261cf3725f120e3c71c71a80e"

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
