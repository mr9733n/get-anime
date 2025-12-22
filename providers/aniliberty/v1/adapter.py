# adapter.py
"""
Refactored API v1 adapter:
- network/orchestration вынесены в ReleaseBundleService
- mapping вынесен в LegacyMapper
- APIAdapter остаётся фасадом для старого кода (process.py и т.п.)

Важно:
- публичные методы сохранены (get_schedule, get_search_by_title, get_release_full, ...)
- allow_network в _enrich_and_adapt означает "можно ли догружать отдельными эндпоинтами";
  базовый release (который уже пришёл) маппится всегда.
"""
from __future__ import annotations

import threading
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence

from providers.aniliberty.v1.legacy_mapper import LegacyMapper
from providers.aniliberty.v1.service import ReleaseBundleService


class APIAdapter:
    def __init__(self, client, logger):
        self.client = client
        self.logger = logger

        self.mapper = LegacyMapper(logger=logger)
        self.service = ReleaseBundleService(api_client=client, logger=logger)

        # оставим локи в адаптере только для методов, которые работают с входным release,
        # чтобы не было двойных запросов на один и тот же release_id при гонках
        self._title_locks_guard = threading.Lock()
        self._title_locks: Dict[int, threading.Lock] = {}

    def _lock_for(self, release_id: int) -> threading.Lock:
        with self._title_locks_guard:
            lock = self._title_locks.get(release_id)
            if not lock:
                lock = threading.Lock()
                self._title_locks[release_id] = lock
            return lock

    # ============================================
    # APP STATUS
    # ============================================

    def get_app_status(self) -> dict:
        try:
            data = self.client.get_status()
            return data if isinstance(data, dict) else {"data": data}
        except Exception as e:
            self.logger.error(f"Error in get_app_status: {e}")
            return {"error": str(e)}

    # ============================================
    # SCHEDULE
    # ============================================

    def get_schedule(self, day):
        """Получает расписание для конкретного дня."""
        try:
            today = datetime.now().isoweekday()
            day = int(day)
            if day == today:
                self.logger.info(f"Requesting TODAY's schedule (day={day}) via /schedule/now")
                return self._get_schedule_now(day)
            else:
                self.logger.info(f"Requesting schedule for day={day} (today={today}) via /schedule/week")
                return self._get_schedule_week(day)
        except Exception as e:
            self.logger.error(f"Error in get_schedule: {e}")
            return {'error': str(e)}

    def _get_schedule_now(self, day):
        """Загружает расписание на СЕГОДНЯ."""
        try:
            now_data = self.client.get_schedule_now()
            if isinstance(now_data, dict) and 'error' in now_data:
                return now_data

            today_items = self._extract_releases(now_data)

            adapted_releases = []
            for release in today_items:
                adapted = self._enrich_and_adapt(
                    release,
                    fetch_episodes=True,
                    fetch_torrents=True,
                    fetch_team=True,
                    fetch_franchises=True,
                    allow_network=True,
                )
                adapted_releases.append(adapted)

            return [{'day': day, 'list': adapted_releases}]

        except Exception as e:
            self.logger.error(f"Error in _get_schedule_now: {e}")
            return {'error': str(e)}

    def _get_schedule_week(self, day):
        """Загружает расписание на неделю и отфильтровывает нужный день."""
        try:
            week_data = self.client.get_schedule_week()
            if isinstance(week_data, dict) and 'error' in week_data:
                return week_data

            releases = self._extract_releases(week_data)
            filtered = []
            for release in releases:
                try:
                    rel = release.get("release") if isinstance(release, dict) else None
                    obj = rel if isinstance(rel, dict) else release

                    wd = ((obj.get("publish_day") or {}).get("value"))
                    if wd is None:
                        continue
                    if int(wd) == int(day):
                        filtered.append(obj)
                except Exception:
                    continue

            adapted_releases = []
            for release in filtered:
                adapted = self._enrich_and_adapt(
                    release,
                    fetch_episodes=True,
                    fetch_torrents=True,
                    fetch_team=True,
                    fetch_franchises=True,
                    allow_network=True,
                )
                adapted_releases.append(adapted)

            return [{'day': day, 'list': adapted_releases}]
        except Exception as e:
            self.logger.error(f"Error in _get_schedule_week: {e}")
            return {'error': str(e)}

    # ============================================
    # SEARCH
    # ============================================

    def get_search_by_title(self, query: str):
        try:
            data = self.client.search_releases(query)
            if 'error' in data:
                return data
            releases = self._extract_releases(data)
            adapted = [self._enrich_and_adapt(r, fetch_episodes=False, fetch_torrents=False,
                                             fetch_team=False, fetch_franchises=False,
                                             allow_network=False)
                       for r in releases]
            return adapted
        except Exception as e:
            self.logger.error(f"Error in get_search_by_title: {e}")
            return {'error': str(e)}

    def get_search_by_alias(self, alias: str):
        try:
            data = self.client.get_release(str(alias))
            if 'error' in data:
                return data
            adapted = self._enrich_and_adapt(
                data,
                fetch_episodes=True,
                fetch_torrents=True,
                fetch_team=True,
                fetch_franchises=True,
                allow_network=True,
            )
            return {'list': [adapted]}
        except Exception as e:
            self.logger.error(f"Error in get_search_by_alias: {e}")
            return {'error': str(e)}

    def get_search_by_title_id(self, external_id: int):
        """title_id must be external_id. don't use internal title_id"""
        try:
            data = self.client.get_release(int(external_id))
            if 'error' in data:
                return data
            adapted = self._enrich_and_adapt(
                data,
                fetch_episodes=True,
                fetch_torrents=True,
                fetch_team=True,
                fetch_franchises=True,
                allow_network=True,
            )
            return {'list': [adapted]}
        except Exception as e:
            self.logger.error(f"Error in get_search_by_title_id: {e}")
            return {'error': str(e)}

    def get_search_by_title_ids(self, title_ids: Sequence[int]):
        """title_ids : list of external_id. don't use internal title_id"""
        out = []
        for tid in title_ids:
            out.append(self.get_search_by_title_id(tid))
        return out

    def get_random_title(self):
        try:
            data = self.client.get_random_releases()
            if 'error' in data:
                return data
            releases = self._extract_releases(data)
            if not releases:
                return {'error': 'No releases'}
            # API can return many
            release = releases[0]
            item = self._enrich_and_adapt(
                release,
                fetch_episodes=True,
                fetch_torrents=True,
                fetch_team=True,
                fetch_franchises=True,
                allow_network=True,
            )
            return {'list': [item]}
        except Exception as e:
            self.logger.error(f"Error in get_random_title: {e}")
            return {'error': str(e)}

    # ============================================
    # Catalog and Latest releases
    # ============================================

    def get_latest_releases(self, limit: int = 14):
        """
        Возвращает список "последние релизы" в legacy формате.
        """
        try:
            data = self.client.get_latest_releases(limit=limit)
            if isinstance(data, dict) and "error" in data:
                return data

            releases = self._extract_releases(data)
            adapted = [
                self._enrich_and_adapt(
                    r,
                    fetch_episodes=True,
                    fetch_torrents=True,
                    fetch_team=True,
                    fetch_franchises=True,
                    allow_network=True,
                )
                for r in releases
            ]
            return {"list": adapted}
        except Exception as e:
            self.logger.error(f"Error in get_latest_releases: {e}")
            return {"error": str(e)}

    def get_catalog_releases(self, *, page: int = 1, limit: int = 10, filters: Optional[Dict[str, Any]] = None, use_post: bool = False):
        try:
            data = self.client.get_catalog_releases(page=page, limit=limit, filters=filters, use_post=use_post)
            if isinstance(data, dict) and "error" in data:
                return data

            releases = self._extract_releases(data)
            adapted = [
                self._enrich_and_adapt(
                    r,
                    fetch_episodes=False,
                    fetch_torrents=False,
                    fetch_team=False,
                    fetch_franchises=False,
                    allow_network=False,
                )
                for r in releases
            ]
            if isinstance(data, dict):
                return {"list": adapted, "meta": {k: v for k, v in data.items() if k not in ("data", "releases")}}
            return {"list": adapted}
        except Exception as e:
            self.logger.error(f"Error in get_catalog_releases: {e}")
            return {"error": str(e)}

    # ============================================
    # RSS (torrents)
    # ============================================

    def get_torrents_rss(self, *, limit: int = 10, pk: str | None = None) -> Dict[str, Any]:
        """
        RSS лента торрентов (XML -> JSON).
        """
        try:
            xml_bytes = self.client.get_torrents_rss(limit=limit, pk=pk)
            return self.mapper.adapt_rss_feed(xml_bytes)
        except Exception as e:
            self.logger.error(f"Error in get_torrents_rss: {e}")
            return {"error": str(e)}

    def get_torrents_rss_for_release(self, external_id: int, *, pk: str | None = None) -> Dict[str, Any]:
        """
        RSS лента торрентов конкретного релиза.
        ВАЖНО: endpoint требует external_id. Alias не поддерживаем — UI должен прислать id.
        """
        try:
            if not external_id:
                return {"error": f"Cannot resolve release id for '{external_id}'"}
            xml_bytes = self.client.get_torrents_rss_for_release(external_id, pk=pk)
            return self.mapper.adapt_rss_feed(xml_bytes)
        except Exception as e:
            self.logger.error(f"Error in get_torrents_rss_for_release: {e}")
            return {"error": str(e)}

    # ============================================
    # CORE: enrich + map to legacy
    # ============================================

    def _enrich_and_adapt(
        self,
        release: Dict[str, Any],
        *,
        fetch_episodes: bool = True,
        fetch_torrents: bool = True,
        fetch_team: bool = True,
        fetch_franchises: bool = True,
        single_episode: Optional[int] = None,
        allow_network: bool = True,
    ) -> Dict[str, Any]:
        """
        Главный метод адаптации.
        - Если allow_network=True: докачиваем части через ReleaseBundleService (параллельно).
        - Если allow_network=False: маппим только то, что уже есть в release (без доп. эндпоинтов).
        """
        try:
            release_id = int(release.get('id') or 0)
            lock = self._lock_for(release_id) if release_id else None

            if lock:
                lock.__enter__()

            try:
                if allow_network and release_id:
                    need = []
                    if fetch_torrents:
                        need.append("torrents")
                    if fetch_team:
                        need.append("members")
                    if fetch_franchises:
                        need.append("franchises")
                    if fetch_episodes:
                        need.append("episodes")

                    raw = self.service.fetch_bundle(
                        release_id,
                        need=tuple(need) if need else (),
                        max_workers=4,
                        prefer_embedded=True,
                        allow_network=True,
                    )
                    if not raw or 'error' in raw:
                        raw = release
                else:
                    raw = release

                # 2) Map base release
                self.mapper.stream_video_host = None
                adapted = self.mapper.adapt_structure(raw)

                # 3) Episodes
                if fetch_episodes:
                    episodes_raw = raw.get("episodes")
                    # episodes может быть list или dict{list:[]}
                    eps_list = self.service._episodes_to_list(episodes_raw)
                    if single_episode is not None:
                        eps_list = [e for e in eps_list if int(e.get('ordinal') or 0) == int(single_episode)]

                    if eps_list:
                        adapted_episodes = [self.mapper.adapt_episode(ep) for ep in eps_list]
                        adapted['player']['list'] = adapted_episodes
                    else:
                        adapted['player']['list'] = []

                    adapted['player']['host'] = self.mapper.stream_video_host

                # 4) Torrents
                if fetch_torrents:
                    torrents_raw = raw.get("torrents")
                    t_list = []
                    if isinstance(torrents_raw, dict):
                        t_list = torrents_raw.get("list") or []
                    elif isinstance(torrents_raw, list):
                        t_list = torrents_raw
                    if t_list:
                        adapted['torrents']['list'] = [self.mapper.adapt_torrent(t) for t in t_list]
                    else:
                        adapted['torrents']['list'] = []

                # 5) Team (members)
                if fetch_team:
                    members_raw = raw.get("members") or []
                    adapted['team'] = self.mapper.adapt_team(members_raw)

                # 6) Franchises
                if fetch_franchises:
                    fr_raw = raw.get("franchises")
                    fr_list = []
                    if isinstance(fr_raw, dict):
                        fr_list = [fr_raw]
                    elif isinstance(fr_raw, list):
                        fr_list = fr_raw
                    adapted_fr = []
                    for fr in fr_list:
                        if not isinstance(fr, dict):
                            continue
                        mapped = self.mapper.adapt_franchise(fr)
                        if mapped:
                            adapted_fr.append(mapped)
                    adapted['franchises'] = adapted_fr

                return adapted

            finally:
                if lock:
                    lock.__exit__(None, None, None)

        except Exception as e:
            self.logger.error(f"Error enriching release {release.get('id')}: {e}", exc_info=True)
            try:
                self.mapper.stream_video_host = None
                return self.mapper.adapt_structure(release)
            except Exception:
                return {'error': str(e)}

    # ============================================
    # Utils
    # ============================================

    def _extract_releases(self, data):
        """Извлекает массив релизов из ответа API."""
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            if 'data' in data:
                return data['data']
            if 'releases' in data:
                return data['releases']
            if 'today' in data:
                return data['today']
        return []

    # ============================================
    # Batch full (like old fetch_release_bundle(s))
    # ============================================

    def get_release_full(self, release_id, *, need=('torrents', 'members', 'franchises', 'episodes'), max_workers=4):
        """
        Полные данные по релизу за один вызов адаптера.
        Внутри: сервис собирает RAW, далее маппим в legacy.
        """
        try:
            rid = int(release_id)
            raw = self.service.fetch_bundle(
                rid,
                need=need,
                max_workers=max_workers,
                prefer_embedded=True,
                allow_network=True,
            )
            if not raw or 'error' in raw:
                return raw
            return self._enrich_and_adapt(raw, allow_network=False,
                                         fetch_episodes=('episodes' in need),
                                         fetch_torrents=('torrents' in need),
                                         fetch_team=('members' in need),
                                         fetch_franchises=('franchises' in need))
        except Exception as e:
            return {'error': str(e)}

    def get_releases_full(self, release_ids, *, need=('torrents', 'members', 'franchises', 'episodes'), max_workers=8):
        """
        Пакетная загрузка бандлов, затем маппинг.
        Возвращает list legacy releases (в том же порядке, что release_ids).
        """
        try:
            rids = [int(x) for x in release_ids]
            bundles = self.service.fetch_bundles(
                rids,
                need=need,
                max_workers=max_workers,
                prefer_embedded=True,
                allow_network=True,
            )
            out = []
            for rid in rids:
                raw = bundles.get(rid) or {'error': f'missing bundle for {rid}'}
                if isinstance(raw, dict) and 'error' in raw:
                    out.append(raw)
                else:
                    out.append(self._enrich_and_adapt(raw, allow_network=False,
                                                     fetch_episodes=('episodes' in need),
                                                     fetch_torrents=('torrents' in need),
                                                     fetch_team=('members' in need),
                                                     fetch_franchises=('franchises' in need)))
            return out
        except Exception as e:
            return [{'error': str(e)}]
