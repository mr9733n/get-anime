# api.py - AniLiberty API v1 client (endpoints only)
from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Sequence

from providers.aniliberty.v1.transport import HttpTransport
from providers.aniliberty.v1.settings import default_settings
from providers.aniliberty.v1.endpoints import RELEASES_LIST, RELEASES_RANDOM, SEARCH_RELEASES, SCHEDULE_NOW, \
                                              SCHEDULE_WEEK, CATALOG_RELEASES, APP_STATUS, RELEASES_LATEST, \
                                              TORRENTS_RSS, \
                                              torrents, release_members, franchise_by_release, franchise, \
                                              release, torrents_rss_release


class APIClient:
    """Thin API client: only endpoints, no orchestration/business logic."""

    def __init__(
        self,
        *,
        base_url: str,
        api_version: str,
        net_client: Any,
        logger: logging.Logger | None = None,
        utils_folder: str = "temp",
        sleep_fn=None,
        max_cache_items: int = 256,
        enable_dumps: bool = False,
    ) -> None:
        self.base_url = base_url
        self.logger = logger or logging.getLogger(__name__)
        settings = default_settings()

        self.transport = HttpTransport(
            net_client=net_client,
            base_url=f"https://{self.base_url}/api/{api_version}/",
            utils_folder=utils_folder,
            logger=self.logger,
            sleep_fn=sleep_fn,
            cache_policy=settings.cache_policy,
            max_cache_items=max_cache_items,
            enable_dumps=enable_dumps,
        )

    def close(self) -> None:
        self.transport.close()

    def _get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Any:
        return self.transport.request_json(endpoint, params=params, method="GET")

    def _post(self, endpoint: str, json_body: Optional[Dict[str, Any]] = None) -> Any:
        return self.transport.request_json(endpoint, params=json_body, method="POST")

    # ---- endpoints ----

    def get_status(self) -> Any:
        """GET /app/status — статус API."""
        return self._get(APP_STATUS)

    def get_schedule_week(self) -> Any:
        return self._get(SCHEDULE_WEEK)

    def get_schedule_now(self) -> Any:
        return self._get(SCHEDULE_NOW)

    def search_releases(self, query: str) -> Any:
        return self._get(SEARCH_RELEASES, params={"query": query})

    def get_release(self, release_id_or_alias: int | str) -> Any:
        return self._get(release(release_id_or_alias))

    def get_release_by_id(self, release_id: int) -> Any:
        return self.get_release(release_id)

    def get_release_by_alias(self, alias: str) -> Any:
        return self.get_release(alias)

    def get_releases_list(
        self,
        *,
        ids: Optional[Sequence[int]] = None,
        aliases: Optional[Sequence[str]] = None,
        page: int = 1,
        limit: int = 10,
    ) -> Any:
        params: Dict[str, Any] = {"page": page, "limit": limit}
        if ids:
            params["ids"] = ",".join(map(str, ids))
        if aliases:
            params["aliases"] = ",".join(aliases)
        return self._get(RELEASES_LIST, params=params)

    def get_catalog_releases(
        self,
        *,
        page: int = 1,
        limit: int = 10,
        filters: Optional[Dict[str, Any]] = None,
        use_post: bool = False,
    ) -> Any:
        """
        /anime/catalog/releases поддерживает GET и POST (по доке).
        filters — это то, что ты формируешь в приложении (оставляем формат на твоё усмотрение).
        """
        if use_post:
            body: Dict[str, Any] = {"page": page, "limit": limit}
            if filters:
                body.update(filters)
            return self._post(CATALOG_RELEASES, json_body=body)

        params: Dict[str, Any] = {"page": page, "limit": limit}
        if filters:
            params.update(filters)
        return self._get(CATALOG_RELEASES, params=params)

    def get_random_releases(self, limit: int = 1) -> Any:
        return self._get(RELEASES_RANDOM, params={"limit": int(limit)})

    # Backward-compat alias (у тебя это уже всплывало в логах)
    def get_random_release(self) -> Any:
        return self.get_random_releases(limit=1)

    def get_latest_releases(self, limit: int = 14) -> Any:
        return self._get(RELEASES_LATEST, params={"limit": limit})

    def get_release_torrents(self, release_id: int | str) -> Any:
        return self._get(torrents(release_id))

    def get_torrents_rss(self, *, limit: int = 10, pk: str | None = None) -> bytes:
        params: Dict[str, Any] = {"limit": limit}
        if pk:
            params["pk"] = pk
        return self.transport.request_raw(TORRENTS_RSS, params=params, method="GET")

    def get_torrents_rss_for_release(self, release_id: int, *, pk: str | None = None) -> bytes:
        params: Dict[str, Any] = {}
        if pk:
            params["pk"] = pk
        return self.transport.request_raw(torrents_rss_release(release_id), params=params, method="GET")

    def get_release_members(self, release_id: int | str) -> Any:
        return self._get(release_members(release_id))

    def get_franchise_by_release(self, release_id: int | str) -> Any:
        return self._get(franchise_by_release(release_id))

    def get_franchise_by_id(self, franchise_id: str) -> Any:
        return self._get(franchise(franchise_id))
