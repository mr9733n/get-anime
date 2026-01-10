from __future__ import annotations

from typing import Callable, Any

from backend.transport.json_tool.protocol import ok
from backend.transport.json_tool.request_context import RequestContext
from backend.transport.json_tool.serializers import to_jsonable
from backend.transport.json_tool.async_runner import run


Handler = Callable[[Any, dict], dict]  # (backend, params) -> response dict


def h_titles_ids_search(backend, params):
    query = (params.get("query") or "").strip()
    provider = params.get("provider")
    provider = provider.strip() if isinstance(provider, str) and provider.strip() else None
    res = backend.titles_search(query=query, provider=provider)
    return ok({"title_ids": res.title_ids, "providers": res.providers})


def h_titles_search(backend, params):
    ctx = RequestContext(backend, params)

    dtos = backend.titles.titles_search(
        query=ctx.query or "",
        user_id=ctx.user_id,
        enrich=ctx.enrich,
        limit=ctx.limit(backend.ctx.titles_search_limit_default),
        offset=ctx.offset(backend.ctx.titles_search_offset_default),
    )
    return ok({"titles": to_jsonable(dtos)})

def h_titles_get(backend, params):
    user_id = int(params.get("user_id", backend.ctx.user_id))
    enrich = bool(params.get("enrich", backend.ctx.titles_enrich_default))
    if "title_ids" in params:
        title_ids = params["title_ids"]
        if not isinstance(title_ids, list):
            raise ValueError("title_ids must be a list[int]")
        title_ids = [int(x) for x in title_ids]
        dtos = backend.titles.titles_get(title_ids=title_ids, user_id=user_id, enrich=enrich)
    elif "title_id" in params:
        title_id = int(params["title_id"])
        dtos = backend.titles.titles_get(title_ids=[title_id], user_id=user_id, enrich=enrich)
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


def h_sync_fetch_and_process(backend, params):
    """Дёргает провайдера (query/external_id), затем применяет write-path (process->save)."""
    ctx = RequestContext(backend, params)
    if not ctx.provider_code:
        raise ValueError("provider_code is required")

    res = run(
        backend.sync_fetch_and_process(
            provider_code=ctx.provider_code,
            external_id=ctx.external_id,
            query=ctx.query,
            mode=ctx.mode(backend.ctx.sync_mode_default),
            max_results=ctx.max_results(backend.ctx.sync_max_results_default),
        )
    )
    return ok({"result": to_jsonable(res)})

def h_sync_search_external_ids(backend, params):
    provider_code = (params.get("provider_code") or "").strip().lower()
    query = (params.get("query") or "").strip()
    max_results = int(params.get("max_results", 10))

    if provider_code == "":
        raise ValueError("provider_code is required")

    res = run(
        backend.sync_search_external_ids(
            provider_code=provider_code,
            query=query,
            max_results=max_results,
        )
    )
    return ok({"external_ids": to_jsonable(res)})


def h_sync_fetch_payload(backend, params):
    provider_code = (params.get("provider_code") or "").strip().lower()
    max_results = int(params.get("max_results", 10))
    external_id = params.get("external_id")
    query = params.get("query")

    if provider_code == "":
        raise ValueError("provider_code is required")

    if isinstance(external_id, bool):
        external_id = None

    res = run(
        backend.sync_fetch_payload(
            provider_code=provider_code,
            external_id=external_id,
            query=query,
            max_results=max_results,
        )
    )
    return ok({"payload": to_jsonable(res)})


def h_sync_search_and_process(backend, params):
    provider_code = (params.get("provider_code") or "").strip().lower()
    query = (params.get("query") or "").strip()
    max_results = int(params.get("max_results", backend.ctx.sync_max_results_default))
    limit = int(params.get("limit", backend.ctx.sync_limit_default))
    mode = (params.get("mode") or backend.ctx.sync_mode_default).strip().lower()

    res = run(
        backend.sync_search_and_process(
            provider_code=provider_code,
            query=query,
            mode=mode,
            max_results=max_results,
            limit=limit,
        )
    )
    return ok({"result": to_jsonable(res)})


def h_titles_update(backend, params):
    title_ids = params.get("title_ids")
    if not isinstance(title_ids, list) or not title_ids:
        raise ValueError("title_ids must be a non-empty list[int]")
    title_ids = [int(x) for x in title_ids]

    provider_code = params.get("provider_code")
    provider_code = provider_code.strip().lower() if isinstance(provider_code, str) and provider_code.strip() else None

    mode = (params.get("mode") or backend.ctx.update_mode_default).strip().lower()
    max_results = int(params.get("max_results", backend.ctx.sync_max_results_default))

    res = run(
        backend.titles_update.update_titles(
            title_ids=title_ids,
            provider_code=provider_code,
            mode=mode,
            max_results=max_results,
        )
    )
    return ok({"result": to_jsonable(res)})


HANDLERS: dict[str, Handler] = {
    "titles_ids.search": h_titles_ids_search,
    "titles.search": h_titles_search,
    "titles.get": h_titles_get,
    "streams.get": h_streams_get,
    "playlist.compose": h_playlist_compose,
    "playlist.compose_multi": h_playlist_compose_multi,
    "titles.list_episodes": h_titles_list_episodes,
    "sync.fetch_and_process": h_sync_fetch_and_process,
    "sync.search_external_ids": h_sync_search_external_ids,
    "sync.fetch_payload": h_sync_fetch_payload,
    "sync.search_and_process": h_sync_search_and_process,
    "titles.update": h_titles_update,

}