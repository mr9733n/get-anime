from __future__ import annotations

from backend.core.controllers.titles_controller import TitlesController
from backend.core.controllers.sync_controller import SyncController


class TitlesUpdateController:
    def __init__(self, *, titles: TitlesController, sync: SyncController) -> None:
        self._titles = titles
        self._sync = sync

    @staticmethod
    def _pick_provider_from_title(t, provider_code: str | None) -> str | None:
        if provider_code:
            return provider_code.strip().lower()

        # 1) явные поля (если вдруг есть)
        for attr in ("provider_code", "provider"):
            v = getattr(t, attr, None)
            if isinstance(v, str) and v.strip():
                return v.strip().lower()

        # 2) provider_links (как в enriched-ответе titles.get)
        links = getattr(t, "provider_links", None)
        if isinstance(links, list) and links:
            # link может быть dict или объектом
            first = links[0]
            v = first.get("provider_code") if isinstance(first, dict) else getattr(first, "provider_code", None)
            if isinstance(v, str) and v.strip():
                return v.strip().lower()

        return None

    @staticmethod
    def _pick_external_id_from_links(t, provider_code: str) -> str | int | None:
        links = getattr(t, "provider_links", None)
        if not (isinstance(links, list) and links):
            return None

        for link in links:
            pc = link.get("provider_code") if isinstance(link, dict) else getattr(link, "provider_code", None)
            if not (isinstance(pc, str) and pc.strip()):
                continue
            if pc.strip().lower() != provider_code:
                continue

            ext = link.get("external_title_id") if isinstance(link, dict) else getattr(link, "external_title_id", None)
            if ext is None:
                return None
            ext_str = str(ext).strip()

            # AniMedia requires a compound "id@@name" token so its adapter can do a
            # name-search and then select the correct item by ID.  Legacy DB rows that
            # were linked before the compound format was introduced store only the bare
            # numeric ID (e.g. "2002").  Rebuild the token when the @@-separator is
            # missing so that fetch_payload_by_external_id gets a usable query string.
            if provider_code == "animedia" and "@@" not in ext_str:
                name = TitlesUpdateController._fallback_query(t) or ""
                if name:
                    return f"{ext_str}@@{name}"

            return ext_str

        return None

    @staticmethod
    def _fallback_query(t) -> str | None:
        # твой текущий titles.get отдаёт name_ru/name_en/code
        for attr in ("name_en", "name_ru", "code"):
            v = getattr(t, attr, None)
            if isinstance(v, str) and v.strip():
                return v.strip()

        # если вдруг новый DTO будет с names/name
        names = getattr(t, "names", None)
        if isinstance(names, dict):
            v = names.get("en") or names.get("ru")
            if isinstance(v, str) and v.strip():
                return v.strip()

        v = getattr(t, "name", None)
        if isinstance(v, str) and v.strip():
            return v.strip()

        return None

    async def update_titles(
        self,
        *,
        title_ids: list[int],
        provider_code: str | None = None,
        mode: str = "title_full",
        max_results: int = 5,
    ) -> dict:
        # ВАЖНО: enrich=True, иначе provider_links обычно пустые и нечего маппить.
        dtos = self._titles.titles_get(
            title_ids=[int(x) for x in title_ids],
            user_id=42,
            enrich=True,
        )

        applied: list[dict] = []
        skipped = 0

        for t in dtos:
            upd_provider = self._pick_provider_from_title(t, provider_code)
            if not upd_provider:
                skipped += 1
                continue

            external_id = self._pick_external_id_from_links(t, upd_provider)
            query = None if external_id is not None else self._fallback_query(t)

            if external_id is None and not query:
                skipped += 1
                continue

            res = await self._sync.fetch_and_process(
                provider_code=upd_provider,
                external_id=external_id,
                query=query,
                mode=mode,
                max_results=max_results,
            )
            applied.append(res)

        return {"ok": True, "applied": applied, "skipped": skipped, "error": None}
