# endpoints.py

APP_STATUS = "app/status"

SCHEDULE_WEEK = "anime/schedule/week"
SCHEDULE_NOW = "anime/schedule/now"
SEARCH_RELEASES = "app/search/releases"

CATALOG_RELEASES = "anime/catalog/releases"

RELEASES_PREFIX = "anime/releases/"
RELEASES_LIST = "anime/releases/list"
RELEASES_RANDOM = "anime/releases/random"
RELEASES_LATEST = "anime/releases/latest"

TORRENTS_PREFIX = "anime/torrents/release/"
TORRENTS_RSS = "anime/torrents/rss"
TORRENTS_RSS_RELEASE_PREFIX = "anime/torrents/rss/release/"

MEMBERS = "/members"

FRANCHISE_BY_RELEASE_PREFIX = "anime/franchises/release/"
FRANCHISE_PREFIX = "anime/franchises/"

def release(release_id_or_alias: int | str) -> str:
    return f"{RELEASES_PREFIX}{release_id_or_alias}"

def release_members(release_id: int | str) -> str:
    return f"{RELEASES_PREFIX}{release_id}{MEMBERS}"

def torrents(release_id: int | str) -> str:
    return f"{TORRENTS_PREFIX}{release_id}"

def torrents_rss_release(release_id: int | str) -> str:
    return f"{TORRENTS_RSS_RELEASE_PREFIX}{release_id}"

def franchise_by_release(release_id: int | str) -> str:
    return f"{FRANCHISE_BY_RELEASE_PREFIX}{release_id}"

def franchise(franchise_id: str) -> str:
    return f"{FRANCHISE_PREFIX}{franchise_id}"
