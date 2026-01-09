from __future__ import annotations

from backend.core.dto.streams import StreamInfoDTO
from backend.core.utils.urls import make_base_url, abs_url, norm_str


class StreamsController:
    def __init__(self, db):
        self._db = db

    def streams_get(self, title_id: int, episode_number: int) -> StreamInfoDTO:
        titles = self._db.get_titles_from_db(title_id=int(title_id))
        if not titles:
            raise ValueError(f"title_id not found: {title_id}")
        t = titles[0]

        host = norm_str(getattr(t, "host_for_player", None))
        base = make_base_url(host)

        eps = getattr(t, "episodes", []) or []
        ep = next((e for e in eps if int(getattr(e, "episode_number", -1)) == int(episode_number)), None)
        if not ep:
            raise ValueError(f"episode not found: title_id={title_id} episode_number={episode_number}")

        sd = norm_str(getattr(ep, "hls_sd", None))
        hd = norm_str(getattr(ep, "hls_hd", None))
        fhd = norm_str(getattr(ep, "hls_fhd", None))

        best_url = fhd or hd or sd
        best_quality = "fhd" if fhd else ("hd" if hd else ("sd" if sd else None))

        return StreamInfoDTO(
            title_id=int(title_id),
            episode_id=int(getattr(ep, "episode_id")),
            episode_number=int(getattr(ep, "episode_number")),
            url_sd=abs_url(base, sd),
            url_hd=abs_url(base, hd),
            url_fhd=abs_url(base, fhd),
            best_url=abs_url(base, best_url),
            best_quality=best_quality,
        )
