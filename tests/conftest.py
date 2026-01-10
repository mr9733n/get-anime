import sys
import pytest
from pathlib import Path
from dataclasses import dataclass


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


@dataclass(slots=True)
class FakeBackendContext:
    user_id: int = 42

    titles_enrich_default: bool = True
    titles_search_limit_default: int = 50
    titles_search_offset_default: int = 0

    sync_max_results_default: int = 10
    sync_limit_default: int = 3
    sync_mode_default: str = "title"

    update_mode_default: str = "title_full"
    mode: str = "title"


class FakeTitlesController:
    def titles_search(self, *, query: str, user_id: int = 42, enrich: bool = True, limit: int = 50, offset: int = 0):
        # handlers ожидают список DTO-шек (любой jsonable)
        return [{"title_id": 1, "query": query, "user_id": user_id, "enrich": enrich, "limit": limit, "offset": offset}]

    def titles_get(self, *, title_ids: list[int], user_id: int = 42, enrich: bool = True):
        return [{"title_id": tid, "user_id": user_id, "enrich": enrich} for tid in title_ids]


class FakeStreamsController:
    def streams_get(self, *, title_id: int, episode_number: int, user_id: int = 42):
        return {
            "title_id": title_id,
            "episode_id": 1,
            "episode_number": episode_number,
            "url_sd": "sd.m3u8",
            "url_hd": "hd.m3u8",
            "url_fhd": None,
            "best_url": "hd.m3u8",
            "best_quality": "hd",
        }


class FakePlaylistsController:
    def compose(self, *, title_id: int, quality: str = "best"):
        return f"/tmp/{title_id}-{quality}.m3u8"

    def compose_multi(self, *, title_ids: list[int], quality: str, mode: str, name: str | None, preview_count: int,
                      user_id: int):
        return {
            "title_ids": title_ids,
            "quality": quality,
            "mode": mode,
            "name": name,
            "preview_count": preview_count,
            "user_id": user_id,
            "path": "/tmp/multi.m3u8",
        }


class FakeTitlesUpdateController:
    async def update_titles(self, *, title_ids, provider_code=None, mode="title_full", max_results=5):
        return {"ok": True, "applied": [{"title_ids": title_ids}], "skipped": 0, "error": None}


class FakeBackend:
    def __init__(self):
        self.titles = FakeTitlesController()
        self.streams = FakeStreamsController()
        self.playlists = FakePlaylistsController()
        self.titles_update = FakeTitlesUpdateController()
        self.ctx = FakeBackendContext()

    # handlers.py вызывает backend.streams_get(...)
    def streams_get(self, *, title_id: int, episode_number: int, user_id: int = 42):
        return self.streams.streams_get(title_id=title_id, episode_number=episode_number, user_id=user_id)

    # handlers.py вызывает backend.playlist_compose(...) / playlist_compose_multi(...)
    def playlist_compose(self, *, title_id: int, quality: str = "best"):
        return self.playlists.compose(title_id=title_id, quality=quality)

    def playlist_compose_multi(self, *, title_ids: list[int], quality: str, mode: str, name: str | None, user_id: int,
                               preview_count: int):
        return self.playlists.compose_multi(
            title_ids=title_ids,
            quality=quality,
            mode=mode,
            name=name,
            preview_count=preview_count,
            user_id=user_id,
        )

    # handlers.py для list_episodes дергает backend.title_list_episodes (опечатка/старое имя) + batch backend.titles_list_episodes
    def title_list_episodes(self, *, title_id: int):
        return [{"episode_number": 1, "title_id": title_id}]

    def titles_list_episodes(self, *, title_ids: list[int]):
        return {tid: [{"episode_number": 1, "title_id": tid}] for tid in title_ids}

    # sync handlers
    async def sync_search_and_process(self, *, provider_code: str, query: str, mode: str = "title",
                                      max_results: int = 10, limit: int = 5):
        return {
            "ok": True,
            "provider_code": provider_code,
            "query": query,
            "applied": [{"provider_code": provider_code, "details": {"storage_result": [True, 1]}} for _ in
                        range(limit)],
            "skipped": max(0, max_results - limit),
            "error": None,
        }

    async def sync_fetch_and_process(self, *, provider_code: str, external_id=None, query=None, mode: str = "title_full", max_results: int = 5):
        return {"provider_code": provider_code, "external_id": external_id, "query": query, "mode": mode, "max_results": max_results}

    async def sync_search_external_ids(self, *, provider_code: str, query: str, max_results: int = 10):
        return [1, 2, 3][:max_results]

    async def sync_fetch_payload(self, *, provider_code: str, external_id=None, query=None, max_results: int = 10):
        return {"provider_code": provider_code, "external_id": external_id, "query": query, "max_results": max_results}


@pytest.fixture()
def backend():
    return FakeBackend()


@pytest.fixture()
def handlers():
    from backend.transport.json_tool.handlers import HANDLERS
    return HANDLERS


def call_op(backend, op: str, params: dict):
    from backend.transport.json_tool.handlers import HANDLERS
    return HANDLERS[op](backend, params)
