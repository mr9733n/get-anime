from __future__ import annotations

from typing import Protocol

from backend.core.dto.titles import TitleDetailsDTO, EpisodeDTO
from backend.core.ports.playlists import IPlaylistComposer


_ALLOWED_QUALITIES = {"best", "fhd", "hd", "sd"}
_ALLOWED_MODES = {"by_title", "by_episode_number", "preview", "latest", "continue"}


def _title_display_name(t: TitleDetailsDTO) -> str:
    return t.name_en or t.name_ru or t.code or f"title_{t.title_id}"


def _pick_episode_link(ep: EpisodeDTO, quality: str) -> str | None:
    # предполагаем что в DTO могут быть и absolute и relative — storage нормализует
    if quality == "fhd":
        return ep.hls_fhd_abs or ep.hls_fhd
    if quality == "hd":
        return ep.hls_hd_abs or ep.hls_hd
    if quality == "sd":
        return ep.hls_sd_abs or ep.hls_sd
    # best
    return (ep.hls_fhd_abs or ep.hls_fhd) or (ep.hls_hd_abs or ep.hls_hd) or (ep.hls_sd_abs or ep.hls_sd)


class ModeBuilder(Protocol):
    def build(self, titles: list[TitleDetailsDTO], quality: str, user_id: int, preview_count: int, progress_repo: object | None) -> list[str]:
        ...


class ByTitleMode:
    def build(self, titles, quality, user_id, preview_count, progress_repo) -> list[str]:
        links: list[str] = []
        for t in titles:
            for ep in (t.episodes or []):
                url = _pick_episode_link(ep, quality)
                if url:
                    links.append(url)
        return links


class LatestMode:
    def build(self, titles, quality, user_id, preview_count, progress_repo) -> list[str]:
        links: list[str] = []
        for t in titles:
            eps = t.episodes or []
            if not eps:
                continue
            last_ep = max(eps, key=lambda e: int(e.episode_number or 0))
            url = _pick_episode_link(last_ep, quality)
            if url:
                links.append(url)
        return links


class PreviewMode:
    def build(self, titles, quality, user_id, preview_count, progress_repo) -> list[str]:
        n = int(preview_count)
        if n < 1 or n > 10:
            raise ValueError("preview_count must be in 1..10")
        links: list[str] = []
        for t in titles:
            eps = sorted((t.episodes or []), key=lambda e: int(e.episode_number or 0))
            for ep in eps[:n]:
                url = _pick_episode_link(ep, quality)
                if url:
                    links.append(url)
        return links


class ByEpisodeNumberMode:
    def build(self, titles, quality, user_id, preview_count, progress_repo) -> list[str]:
        per: list[dict[int, EpisodeDTO]] = []
        max_ep = 0
        for t in titles:
            m: dict[int, EpisodeDTO] = {}
            for ep in (t.episodes or []):
                k = int(ep.episode_number or 0)
                if k <= 0:
                    continue
                m[k] = ep
                max_ep = max(max_ep, k)
            per.append(m)

        links: list[str] = []
        for ep_num in range(1, max_ep + 1):
            for m in per:
                ep = m.get(ep_num)
                if not ep:
                    continue
                url = _pick_episode_link(ep, quality)
                if url:
                    links.append(url)
        return links


class ContinueMode:
    def build(self, titles, quality, user_id, preview_count, progress_repo) -> list[str]:
        if progress_repo is None:
            raise ValueError("progress_repo is required for mode=continue")

        title_ids = [int(t.title_id) for t in titles]
        last_map = progress_repo.get_last_watched_episode_numbers(user_id=int(user_id), title_ids=title_ids)

        links: list[str] = []
        for t in titles:
            eps = t.episodes or []
            if not eps:
                continue

            last = int(last_map.get(int(t.title_id), 0) or 0)
            next_num = last + 1 if last > 0 else 1
            next_ep = next((e for e in eps if int(e.episode_number or 0) == next_num), None)
            if not next_ep:
                continue
            url = _pick_episode_link(next_ep, quality)
            if url:
                links.append(url)

        return links


class PlaylistComposer(IPlaylistComposer):
    """
    Реализует IPlaylistComposer: собирает links и имя.
    """
    def __init__(self):
        self._modes: dict[str, ModeBuilder] = {
            "by_title": ByTitleMode(),
            "latest": LatestMode(),
            "preview": PreviewMode(),
            "by_episode_number": ByEpisodeNumberMode(),
            "continue": ContinueMode(),
        }

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
        if quality not in _ALLOWED_QUALITIES:
            raise ValueError("quality must be one of: best|fhd|hd|sd")
        if mode not in _ALLOWED_MODES:
            raise ValueError("mode must be one of: by_title|by_episode_number|preview|latest|continue")

        # host берём “единый”: либо первый непустой
        host = None
        for t in titles:
            if getattr(t, "host_for_player", None):
                host = t.host_for_player
                break

        # name parts (для имени файла)
        name_parts = []
        for t in titles:
            part = (t.code or _title_display_name(t)).strip()
            if part:
                name_parts.append(part)

        builder = self._modes[mode]
        links = builder.build(titles, quality, user_id, preview_count, progress_repo)

        return links, host, name_parts
