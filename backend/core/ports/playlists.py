from __future__ import annotations

from typing import Protocol, Callable, Iterable

from backend.core.dto.playlists import PlaylistBundleDTO
from backend.core.dto.titles import TitleDetailsDTO


GetTitlesFn = Callable[[list[int]], list[TitleDetailsDTO]]


class IPlaylistStorage(Protocol):
    """
    Хранилище плейлистов (файлы/облако/что угодно).
    В нашем случае будет адаптер вокруг utils.playlists.PlaylistManager.
    """
    def save_bundle(
        self,
        *,
        sanitized_titles: list[str],
        links: list[str],
        host: str | None,
    ) -> tuple[str, str, str, str, int, int]:
        """
        Возвращает:
        (m3u_name, m3u_path, urls_name, urls_path, streams_count, web_count)
        """
        ...


class IPlaylistComposer(Protocol):
    """
    Компоновщик плейлиста из DTO TitleDetailsDTO.
    Режимы могут расширяться без правки контроллера.
    """
    def compose_links(
        self,
        *,
        titles: list[TitleDetailsDTO],
        mode: str,
        quality: str,
        user_id: int,
        preview_count: int,
        progress_repo: object | None,
    ) -> tuple[list[str], str | None, list[str]]:
        """
        Возвращает (links, host, name_parts)
        - links: список ссылок (m3u8 и web вперемешку — storage сам разделит)
        - host: host_for_player для нормализации относительных ссылок
        - name_parts: части имени (коды/имена) для имени файла
        """
        ...


class IPlaylistsController(Protocol):
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
        ...
