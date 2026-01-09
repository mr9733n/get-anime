from __future__ import annotations

from backend.core.dto.playlists import PlaylistBundleDTO
from backend.core.ports.playlists import GetTitlesFn, IPlaylistStorage, IPlaylistComposer
from utils.playlists.playlist_key import calc_bundle_key  # sha1 util :contentReference[oaicite:3]{index=3}


def _sanitize_filename(name: str, *, max_len: int = 100) -> str:
    # простая безопасная версия; можно заменить на PlaylistManager.sanitize_filename
    safe = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in str(name)).strip()
    return (safe[:max_len] if safe else "playlist")


class PlaylistsController:
    def __init__(
        self,
        *,
        get_titles: GetTitlesFn,
        storage: IPlaylistStorage,
        composer: IPlaylistComposer,
        progress_repo: object | None = None,
    ):
        self._get_titles = get_titles
        self._storage = storage
        self._composer = composer
        self._progress = progress_repo

    def compose_multi(
        self,
        *,
        title_ids: list[int],
        quality: str = "best",
        mode: str = "by_title",
        user_id: int = 42,
        preview_count: int = 1,
        name: str | None = None,
        make_key: bool = False,
    ) -> PlaylistBundleDTO:
        title_ids = [int(x) for x in (title_ids or [])]
        if not title_ids:
            raise ValueError("title_ids is required")

        titles = self._get_titles(title_ids)
        if not titles:
            raise ValueError("No titles found for given title_ids")

        links, host, name_parts = self._composer.compose_links(
            titles=titles,
            mode=mode,
            quality=quality,
            user_id=int(user_id),
            preview_count=int(preview_count),
            progress_repo=self._progress,
        )

        if not links:
            raise ValueError("No links composed for playlist")

        # имя бандла
        if name:
            bundle_name = _sanitize_filename(name)
        else:
            bundle_name = _sanitize_filename("_".join(name_parts) or ("pack_" + "_".join(map(str, title_ids))))

        # сохранение через утилиту
        m3u_name, m3u_path, urls_name, urls_path, streams_count, web_count = self._storage.save_bundle(
            sanitized_titles=[bundle_name],
            links=links,
            host=host,
        )

        key = None
        if make_key:
            # для multi title_id смысла мало — берём 0, чтобы не ломать сигнатуру утилиты
            key = calc_bundle_key(0, links, host)

        return PlaylistBundleDTO(
            name=bundle_name,
            mode=mode,
            quality=quality,
            m3u_name=m3u_name,
            m3u_path=m3u_path,
            urls_name=urls_name,
            urls_path=urls_path,
            streams_count=int(streams_count),
            web_count=int(web_count),
            key=key,
            host=host,
        )
