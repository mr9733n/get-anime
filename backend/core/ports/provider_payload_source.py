from __future__ import annotations
from typing import Any, Awaitable, Protocol, TypeAlias

MaybeAwaitable: TypeAlias = Any | Awaitable[Any]

class IProviderPayloadSource(Protocol):
    """Источник raw payload от провайдера (read-side для sync)."""

    def fetch_payload_by_external_id(
        self,
        external_id: str | int,
        *,
        force_refresh: bool = False,
    ) -> MaybeAwaitable:
        """Вернуть raw payload (legacy dict) для process->save.

        Возвращает:
          - dict[str, Any] (успех)
          - None (не найдено)
          - dict с ключом 'error' (ошибка провайдера)
        """
        ...

    def search_external_ids(self, query: str, *, max_results: int = 10) -> MaybeAwaitable:
        """Найти подходящие external_id по строке запроса.

        Для провайдеров, у которых нет стабильного external_id (например, AniMedia),
        external_id может быть "нативным ключом" провайдера (например, title name).
        """
        ...
