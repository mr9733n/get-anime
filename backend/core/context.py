from __future__ import annotations
from dataclasses import dataclass

DEFAULT_USER_ID = 42
DEFAULT_TITLES_ENRICH = True

DEFAULT_TITLES_SEARCH_LIMIT = 50
DEFAULT_TITLES_SEARCH_OFFSET = 0

DEFAULT_SYNC_MAX_RESULTS = 10
DEFAULT_SYNC_LIMIT = 3
DEFAULT_SYNC_MODE = "title"
DEFAULT_UPDATE_MODE = "title_full"


@dataclass(frozen=True, slots=True)
class BackendContext:
    user_id: int = DEFAULT_USER_ID

    titles_enrich_default: bool = DEFAULT_TITLES_ENRICH
    titles_search_limit_default: int = DEFAULT_TITLES_SEARCH_LIMIT
    titles_search_offset_default: int = DEFAULT_TITLES_SEARCH_OFFSET

    sync_max_results_default: int = DEFAULT_SYNC_MAX_RESULTS
    sync_limit_default: int = DEFAULT_SYNC_LIMIT
    sync_mode_default: str = DEFAULT_SYNC_MODE

    update_mode_default: str = DEFAULT_UPDATE_MODE

    @staticmethod
    def from_config(cfg) -> "BackendContext":
        # cfg у тебя уже существует как ConfigManager
        user_id = DEFAULT_USER_ID
        try:
            # подстрой под свой API ConfigManager (как у тебя в проекте)
            user_id = int(cfg.get_setting("Settings", "user_id"))
        except Exception:
            pass
        return BackendContext(user_id=user_id)
