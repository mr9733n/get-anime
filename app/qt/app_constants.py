# app/qt/app_constants.py
from __future__ import annotations


# --- Security hashes (executables) ---
# Hash of compiled executable
VLC_PLAYER_HASH = "d13f499d59afb4cc85f0c6a8e832479617ce885589dac79e697b082269a19ec0"
# Hash of compiled executable
MPV_PLAYER_HASH = "a27a84b2d83b491ecfeea67d0e2eaf832303037537a8201c704b8fd73bb94d68"
# Hash of compiled executable
MINI_BROWSER_HASH = "081287a90dce56ba7cec0e7253e3b3e1afc487fb7bf56bf33f17c3ca7605eb73"

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
