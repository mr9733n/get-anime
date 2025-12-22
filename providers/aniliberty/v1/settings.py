from dataclasses import dataclass
from providers.aniliberty.v1.cache_policy import CachePolicy, EndpointTTL
from providers.aniliberty.v1.endpoints import SCHEDULE_WEEK, SCHEDULE_NOW, RELEASES_RANDOM, RELEASES_LIST, RELEASES_PREFIX, \
    TORRENTS_PREFIX, MEMBERS, FRANCHISE_BY_RELEASE_PREFIX, FRANCHISE_PREFIX, CATALOG_RELEASES, APP_STATUS

TTL_MIN = 10
TTL_FAST = 30
TTL_DEFAULT = 60
TTL_FRANCHISE = 120


@dataclass(frozen=True)
class AniLibertyV1Settings:
    cache_policy: CachePolicy


def default_settings() -> AniLibertyV1Settings:
    return AniLibertyV1Settings(
        cache_policy=CachePolicy(
            endpoints=[
                EndpointTTL(APP_STATUS, TTL_MIN, "API status"),
                EndpointTTL(SCHEDULE_WEEK, TTL_DEFAULT, "Weekly schedule"),
                EndpointTTL(SCHEDULE_NOW, TTL_FAST, "Now schedule"),
                EndpointTTL(RELEASES_RANDOM, TTL_FAST, "Random releases"),
                EndpointTTL(RELEASES_LIST, TTL_DEFAULT, "Batch list"),
                EndpointTTL(CATALOG_RELEASES, TTL_DEFAULT, "Catalog releases"),

                # prefix rules:
                EndpointTTL(RELEASES_PREFIX, TTL_DEFAULT, "Release details (id/alias)"),
                EndpointTTL(TORRENTS_PREFIX, TTL_DEFAULT, "Release torrents"),
                EndpointTTL(MEMBERS, TTL_DEFAULT, "Release members"),
                EndpointTTL(FRANCHISE_BY_RELEASE_PREFIX, TTL_FRANCHISE, "Franchises by release"),
                EndpointTTL(FRANCHISE_PREFIX, TTL_FRANCHISE, "Franchise by id"),
            ]
        )
    )
