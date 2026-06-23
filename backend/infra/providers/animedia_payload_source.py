from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from backend.core.ports.provider_payload_source import IProviderPayloadSource


@dataclass(frozen=True)
class AniMediaPayloadSource(IProviderPayloadSource):
    api: Any  # providers.animedia.v0.adapter.AniMediaAdapter

    def _pick_name(self, item: dict[str, Any], fallback: str) -> str:
        names = item.get("names") or {}
        for k in ("en", "ru", "alternative"):
            v = names.get(k)
            if isinstance(v, str) and v.strip():
                return v.strip()
        code = item.get("code")
        if isinstance(code, str) and code.strip():
            return code.strip()
        return fallback

    async def search_external_ids(self, query: str, *, max_results: int = 10) -> list[str]:
        q = (query or "").strip()
        if not q:
            return []

        # ВАЖНО: просим несколько тайтлов, а не 1
        items = await self.api.get_by_title(q, max_titles=max_results)
        if not items:
            return []

        out: list[str] = []
        for it in items:
            if not isinstance(it, dict):
                continue

            ext_id = it.get("external_id")
            if ext_id is None:
                continue

            try:
                ext_id_int = int(ext_id)
            except Exception:
                # если вдруг там не число — всё равно сохраним как строку
                ext_id_int = None

            name = self._pick_name(it, q)
            # токен вида "20693@@One Punch Man 3"
            if ext_id_int is not None:
                out.append(f"{ext_id_int}@@{name}")
            else:
                out.append(f"{str(ext_id).strip()}@@{name}")

            if len(out) >= max_results:
                break

        return out

    async def fetch_payload_by_external_id(
        self,
        external_id: str | int,
        *,
        force_refresh: bool = False,
    ) -> dict[str, Any] | None:
        token = str(external_id).strip()
        if not token:
            return None

        # token может быть:
        # 1) "20693@@One Punch Man 3"  -> найдём по name и выберем по external_id
        # 2) "One Punch Man"          -> просто search и первый результат
        ext_id_part: str | None = None
        name_part: str = token

        if "@@" in token:
            left, right = token.split("@@", 1)
            ext_id_part = left.strip() or None
            name_part = (right or "").strip() or token

        items = await self.api.get_by_title(
            name_part,
            max_titles=25,
            force_vlink_refresh=force_refresh,
        )
        if not items:
            return None

        # если есть external_id в токене — выбираем точное совпадение
        if ext_id_part is not None:
            for it in items:
                if not isinstance(it, dict):
                    continue
                if str(it.get("external_id", "")).strip() == ext_id_part:
                    return it
            # если не нашли — fallback на первый dict
        for it in items:
            if isinstance(it, dict):
                return it

        return None
