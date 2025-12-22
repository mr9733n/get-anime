# bundle_service.py
from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, Iterable, Optional, Sequence, Tuple


class ReleaseBundleService:
    """
    Service layer: orchestration & policies.
    - может делать сеть через api_client
    - может делать параллельность (threads)
    - может содержать правила fallback / 404 episodes / prefer-embedded

    ВАЖНО: service НЕ строит legacy-структуру. Он возвращает raw-enriched release.
    """

    def __init__(self, api_client: Any, logger: Any):
        self.api = api_client
        self.logger = logger
        self._title_locks_guard = threading.Lock()
        self._title_locks: Dict[int, threading.Lock] = {}

    def _lock_for(self, release_id: int) -> threading.Lock:
        with self._title_locks_guard:
            lock = self._title_locks.get(release_id)
            if not lock:
                lock = threading.Lock()
                self._title_locks[release_id] = lock
            return lock

    # ---------
    # helpers
    # ---------
    @staticmethod
    def _episodes_to_list(episodes: Any) -> list:
        """
        Нормализация episodes из v1:
        - None -> []
        - {"first":..,"last":..,"list":[...]} -> list
        - {"list":[...]} -> list
        - list -> list
        """
        if not episodes:
            return []
        if isinstance(episodes, list):
            return episodes
        if isinstance(episodes, dict):
            lst = episodes.get("list")
            if isinstance(lst, list):
                return lst
        return []

    def fetch_bundle(
        self,
        release_id: int,
        *,
        need: Sequence[str] = ("torrents", "members", "franchises", "episodes"),
        max_workers: int = 4,
        prefer_embedded: bool = True,
        allow_network: bool = True,
    ) -> Dict[str, Any]:
        """
        Возвращает raw release, обогащённый полями torrents/members/franchises/episodes (если удалось).

        prefer_embedded:
            True -> сначала используем вложенные поля из base release, и только если пусто — идём в сеть.
        allow_network:
            False -> никогда не обращаемся к отдельным эндпоинтам, полагаемся только на base release.
        """
        rid = int(release_id)
        lock = self._lock_for(rid)
        with lock:
            base = self.api.get_release_by_id(rid)
            if not base or "error" in base:
                return base

            # episodes embedded?
            base_eps_list = self._episodes_to_list(base.get("episodes"))
            have_episodes = bool(base_eps_list)

            def should_fetch(field: str, current: Any) -> bool:
                if not allow_network:
                    return False
                if not prefer_embedded:
                    return True
                # если embedded есть — не трогаем сеть
                if field == "episodes":
                    return not have_episodes
                return not current

            # embedded fields
            embedded_torrents = (base.get("torrents") or {}).get("list") if isinstance(base.get("torrents"), dict) else base.get("torrents")
            embedded_members = base.get("members")
            embedded_franchises = base.get("franchises")

            tasks = {}
            with ThreadPoolExecutor(max_workers=max_workers) as ex:
                if "torrents" in need and should_fetch("torrents", embedded_torrents):
                    tasks["torrents"] = ex.submit(self.api.get_release_torrents, rid)
                if "members" in need and should_fetch("members", embedded_members):
                    tasks["members"] = ex.submit(self.api.get_release_members, rid)
                if "franchises" in need and should_fetch("franchises", embedded_franchises):
                    tasks["franchises"] = ex.submit(self.api.get_franchise_by_release, rid)
                if "episodes" in need and should_fetch("episodes", base_eps_list):
                    tasks["episodes"] = ex.submit(self.api.get_release_episodes, rid)

                results: Dict[str, Any] = {}
                for k, fut in tasks.items():
                    try:
                        results[k] = fut.result()
                    except Exception as e:
                        results[k] = {"error": str(e)}

            # apply embedded first (if requested) or fetched
            if "torrents" in need:
                torrents = embedded_torrents if (prefer_embedded and embedded_torrents) else results.get("torrents")
                if torrents and "error" not in torrents:
                    # API v1 torrents endpoint returns dict? or list? keep as-is
                    base["torrents"] = torrents

            if "members" in need:
                members = embedded_members if (prefer_embedded and embedded_members) else results.get("members")
                if members and "error" not in members:
                    base["members"] = members

            if "franchises" in need:
                franchises = embedded_franchises if (prefer_embedded and embedded_franchises) else results.get("franchises")
                if franchises and "error" not in franchises:
                    base["franchises"] = franchises

            if "episodes" in need:
                if have_episodes:
                    base["episodes"] = base_eps_list
                else:
                    episodes = results.get("episodes")
                    # важный кейс: 404 /episodes -> это норма, считаем как "нет эпизодов"
                    if isinstance(episodes, dict) and episodes.get("status_code") == 404:
                        base["episodes"] = []
                    elif episodes and "error" not in episodes:
                        base["episodes"] = self._episodes_to_list(episodes)

            return base

    def fetch_bundles(
        self,
        release_ids: Iterable[int],
        *,
        need: Sequence[str] = ("torrents", "members", "franchises", "episodes"),
        max_workers: int = 8,
        prefer_embedded: bool = True,
        allow_network: bool = True,
    ) -> Dict[int, Dict[str, Any]]:
        """
        Параллельно собирает бандлы по списку релизов.
        Возвращает dict: {release_id: bundle_or_error}
        """
        out: Dict[int, Dict[str, Any]] = {}

        def job(rid: int) -> Tuple[int, Dict[str, Any]]:
            return rid, self.fetch_bundle(
                rid,
                need=need,
                max_workers=max_workers,
                prefer_embedded=prefer_embedded,
                allow_network=allow_network,
            )

        with ThreadPoolExecutor(max_workers=max_workers) as ex:
            futures = [ex.submit(job, int(rid)) for rid in release_ids]
            for fut in as_completed(futures):
                rid, bundle = fut.result()
                out[rid] = bundle

        return out
