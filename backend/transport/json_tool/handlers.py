from __future__ import annotations
from typing import Callable, Any

from backend.transport.json_tool.protocol import ok
from backend.transport.json_tool.serializers import to_jsonable


Handler = Callable[[Any, dict], dict]  # (backend, params) -> response dict


def h_titles_search(backend, params):
    query = (params.get("query") or "").strip()
    provider = params.get("provider")
    provider = provider.strip() if isinstance(provider, str) and provider.strip() else None
    res = backend.titles_search(query=query, provider=provider)
    return ok({"title_ids": res.title_ids, "providers": res.providers})


def h_titles_get(backend, params):
    if "title_ids" in params:
        title_ids = params["title_ids"]
        if not isinstance(title_ids, list):
            raise ValueError("title_ids must be a list[int]")
        title_ids = [int(x) for x in title_ids]
        dtos = backend.titles_get(title_ids=title_ids)
    elif "title_id" in params:
        title_id = int(params["title_id"])
        dtos = backend.titles_get(title_ids=[title_id])  # всегда list
    else:
        raise ValueError("titles.get expects title_id or title_ids")

    return ok({"titles": to_jsonable(dtos)})


def h_streams_get(backend, params):
    title_id = int(params["title_id"])
    episode_number = int(params["episode_number"])
    dto = backend.streams_get(title_id=title_id, episode_number=episode_number)
    return ok({"stream": to_jsonable(dto)})


def h_playlist_compose(backend, params):
    title_id = int(params["title_id"])
    quality = (params.get("quality") or "best").strip().lower()
    return ok({"path": backend.playlist_compose(title_id=title_id, quality=quality)})


def h_playlist_compose_multi(backend, params):
    title_ids = params.get("title_ids")
    if not isinstance(title_ids, list) or not title_ids:
        raise ValueError("title_ids must be a non-empty list[int]")
    title_ids = [int(x) for x in title_ids]

    quality = (params.get("quality") or "best").strip().lower()
    mode = (params.get("mode") or "by_title").strip().lower()
    name = params.get("name")
    name = str(name) if name is not None else None

    user_id = int(params.get("user_id", 42))
    preview_count = int(params.get("preview_count", 1))

    path = backend.playlist_compose_multi(
        title_ids=title_ids,
        quality=quality,
        mode=mode,
        name=name,
        user_id=user_id,
        preview_count=preview_count,
    )
    return ok({"path": path})


def h_titles_list_episodes(backend, params):
    if "title_ids" in params:
        title_ids = params["title_ids"]
        if not isinstance(title_ids, list):
            raise ValueError("title_ids must be a list[int]")
        title_ids = [int(x) for x in title_ids]
        m = backend.titles_list_episodes(title_ids=title_ids)
        return ok({"episodes_by_title": to_jsonable(m)})
    elif "title_id" in params:
        title_id = int(params["title_id"])
        eps = backend.title_list_episodes(title_id=title_id)
        return ok({"episodes": to_jsonable(eps)})
    else:
        raise ValueError("titles.list_episodes expects title_id or title_ids")


HANDLERS: dict[str, Handler] = {
    "titles.search": h_titles_search,
    "titles.get": h_titles_get,
    "streams.get": h_streams_get,
    "playlist.compose": h_playlist_compose,
    "playlist.compose_multi": h_playlist_compose_multi,
    "titles.list_episodes": h_titles_list_episodes,
}
