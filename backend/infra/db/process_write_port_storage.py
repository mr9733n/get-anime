from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from backend.core.ports.process_write import IProcessWritePort, ApplyProviderPayloadResult


def _unpack_process_titles(res: Any) -> tuple[bool, int | None]:
    """Unpack the return value of ProcessManager.process_titles().

    ProcessManager.process_titles() returns a ``(ok: bool, title_id: int | None)``
    tuple.  Guard against future dict-returning implementations too.

    Returns:
        (ok, title_id) where title_id may be None on failure.
    """
    if isinstance(res, tuple) and len(res) >= 2:
        ok_flag = bool(res[0])
        tid = res[1]
        return ok_flag, (int(tid) if tid is not None else None)
    if isinstance(res, dict):
        ok_flag = bool(res.get("ok", True))
        tid = res.get("title_id") or (res.get("result") or {}).get("title_id")
        return ok_flag, (int(tid) if tid is not None else None)
    # Fallback: truthy return (e.g. True) means ok but no title_id
    return (bool(res) if res is not None else False), None


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

    IMPORTANT — title_id injection:
    process_titles() returns (ok, title_id).  process_episodes() and
    process_torrents() read title_data["title_id"] to set the FK.  We MUST
    inject the DB-assigned title_id into a copy of the payload before calling
    those methods, otherwise episodes/torrents are saved with title_id=None and
    the FK constraint silently stores NULL (or raises).
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
                ok_flag, title_id = _unpack_process_titles(res)
                return self._with_poster(
                    ApplyProviderPayloadResult(
                        ok=ok_flag,
                        provider_code=provider_code,
                        mode=m,
                        title_id=title_id,
                        details={"applied": applied, "storage_result": res},
                        error=None if ok_flag else "process_titles_failed",
                    ),
                    payload,
                )

            if m in ("title_full", "full"):
                res_title = self.storage.process_titles(payload)
                applied.append("title")
                ok_flag, title_id = _unpack_process_titles(res_title)

                # Inject the DB-assigned title_id so process_episodes / process_torrents
                # can set the correct FK.  Use a shallow copy — never mutate the caller's dict.
                enriched = {**payload, "title_id": title_id} if (
                    title_id is not None and isinstance(payload, dict)
                ) else payload

                res_eps = None
                ep_list = (enriched.get("player") or {}).get("list") if isinstance(enriched, dict) else None
                if title_id is not None and ep_list:
                    res_eps = self.storage.process_episodes(enriched)
                    applied.append("episodes")

                res_torr = None
                if title_id is not None and isinstance(enriched, dict) and enriched.get("torrents"):
                    res_torr = self.storage.process_torrents(enriched)
                    applied.append("torrents")

                return self._with_poster(
                    ApplyProviderPayloadResult(
                        ok=ok_flag,
                        provider_code=provider_code,
                        mode=m,
                        title_id=title_id,
                        details={
                            "applied": applied,
                            "storage_result": {"title": res_title, "episodes": res_eps, "torrents": res_torr},
                        },
                        error=None if ok_flag else "process_titles_failed",
                    ),
                    payload,
                )

            if m == "episodes":
                res = self.storage.process_episodes(payload)
                applied.append("episodes")
                title_id = payload.get("title_id") if isinstance(payload, dict) else None
                return self._with_poster(
                    ApplyProviderPayloadResult(ok=True, provider_code=provider_code, mode=m, title_id=title_id,
                                              details={"applied": applied, "storage_result": res}),
                    payload,
                )

            if m == "torrents":
                res = self.storage.process_torrents(payload)
                applied.append("torrents")
                title_id = payload.get("title_id") if isinstance(payload, dict) else None
                return self._with_poster(
                    ApplyProviderPayloadResult(ok=True, provider_code=provider_code, mode=m, title_id=title_id,
                                              details={"applied": applied, "storage_result": res}),
                    payload,
                )

            return self._with_poster(
                ApplyProviderPayloadResult(ok=False, provider_code=provider_code, mode=m, title_id=None,
                                          error=f"unsupported_mode:{m}"),
                payload,
            )

        except Exception as e:
            return ApplyProviderPayloadResult(ok=False, provider_code=provider_code, mode=m, title_id=None,
                                             error=str(e))

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
