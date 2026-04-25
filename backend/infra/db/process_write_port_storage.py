from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from backend.core.ports.process_write import IProcessWritePort, ApplyProviderPayloadResult

@dataclass
class StorageProcessWritePort(IProcessWritePort):
    """Адаптер над storage/db_manager.process_*.

    Текущий storage (infra/storage/database_manager.py) принимает один аргумент
    `title_data` и НЕ принимает именованные параметры (provider_code/payload).
    Этот адаптер приводит новый протокол core к существующему API.

    Это позволяет:
      - core: apply_provider_payload(provider_code, payload, mode)
      - infra/storage: process_titles(title_data), process_episodes(title_data), ...

    poster_job: optional PosterJobAdapter — if set, poster URLs in the payload are
    queued for background download after a title is successfully saved.
    """
    storage: Any
    poster_job: Any = field(default=None, compare=False, repr=False)

    def apply_provider_payload(
        self,
        *,
        provider_code: str,
        payload: dict[str, Any],
        mode: str = "auto",
    ) -> ApplyProviderPayloadResult:
        m = (mode or "auto").strip().lower()

        # простая авто-детекция
        if m == "auto":
            if isinstance(payload, dict) and ("torrents" in payload or "player" in payload or "episodes" in payload):
                m = "title_full"
            else:
                m = "title"

        try:
            applied: list[str] = []
            if m in ("title", "titles"):
                res = self.storage.process_titles(payload)
                applied.append("title")
                title_id = None
                if isinstance(res, dict):
                    title_id = res.get("title_id") or (res.get("result") or {}).get("title_id")
                return self._with_poster(
                    ApplyProviderPayloadResult(
                        ok=True,
                        provider_code=provider_code,
                        mode=m,
                        title_id=title_id,
                        details={"applied": applied, "storage_result": res},
                    ),
                    payload,
                )

            if m in ("title_full", "full"):
                res_title = self.storage.process_titles(payload)
                applied.append("title")

                res_eps = None
                if isinstance(payload, dict) and (payload.get("player") or {}).get("list"):
                    res_eps = self.storage.process_episodes(payload)
                    applied.append("episodes")

                res_torr = None
                if isinstance(payload, dict) and payload.get("torrents"):
                    res_torr = self.storage.process_torrents(payload)
                    applied.append("torrents")

                title_id = None
                for r in (res_title, res_eps, res_torr):
                    if isinstance(r, dict):
                        cand = r.get("title_id") or (r.get("result") or {}).get("title_id")
                        if cand:
                            title_id = cand
                            break

                return self._with_poster(
                    ApplyProviderPayloadResult(
                        ok=True,
                        provider_code=provider_code,
                        mode=m,
                        title_id=title_id,
                        details={
                            "applied": applied,
                            "storage_result": {"title": res_title, "episodes": res_eps, "torrents": res_torr},
                        },
                    ),
                    payload,
                )

            if m == "episodes":
                res = self.storage.process_episodes(payload)
                applied.append("episodes")
                title_id = res.get("title_id") if isinstance(res, dict) else None
                return self._with_poster(
                    ApplyProviderPayloadResult(ok=True, provider_code=provider_code, mode=m, title_id=title_id, details={"applied": applied, "storage_result": res}),
                    payload,
                )

            if m == "torrents":
                res = self.storage.process_torrents(payload)
                applied.append("torrents")
                title_id = res.get("title_id") if isinstance(res, dict) else None
                return self._with_poster(
                    ApplyProviderPayloadResult(ok=True, provider_code=provider_code, mode=m, title_id=title_id, details={"applied": applied, "storage_result": res}),
                    payload,
                )

            return self._with_poster(
                ApplyProviderPayloadResult(ok=False, provider_code=provider_code, mode=m, title_id=None, error=f"unsupported_mode:{m}"),
                payload,
            )

        except Exception as e:
            return ApplyProviderPayloadResult(ok=False, provider_code=provider_code, mode=m, title_id=None, error=str(e))

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _with_poster(
        self,
        result: ApplyProviderPayloadResult,
        payload: Any,
    ) -> ApplyProviderPayloadResult:
        """Queue poster download after a successful save. Never raises."""
        if result.ok and result.title_id is not None and self.poster_job is not None:
            try:
                self.poster_job.queue_posters_for_payload(result.title_id, payload)
            except Exception:
                pass  # poster failures must never break the sync path
        return result
