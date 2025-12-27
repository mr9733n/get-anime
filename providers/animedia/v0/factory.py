# providers/animedia/v0/factory.py
import logging
from pathlib import Path
from typing import Any

from .adapter import AniMediaAdapter
from .service import AniMediaService
from .repository import AniMediaRepository
from .client import AniMediaHttpClient
from .transport import HttpxTransport
from .parser import AniMediaParser
from .cache_manager import AniMediaCacheManager, AniMediaCacheConfig


def create_animedia_adapter(
        base_url: str,
        net_client: Any,
        cache_dir: Path,
        logger: logging.Logger | None = None,
) -> AniMediaAdapter:
    """
    Factory function: создаёт полностью собранный AniMediaAdapter.

    Args:
        base_url: Base URL сайта (e.g., "https://amd.online")
        net_client: Ваш кастомный net_client с методом create_async_httpx_client
        cache_dir: Директория для файлового кэша
        logger: Опциональный логгер

    Returns:
        Готовый к использованию AniMediaAdapter
    """
    log = logger or logging.getLogger(__name__)

    # 1. Infrastructure layer
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/140.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "keep-alive",
    }

    transport = HttpxTransport(
        net_client=net_client,
        headers=headers,
        timeout=30.0,
        follow_redirects=True,
        logger=log,
    )

    cache_cfg = AniMediaCacheConfig(base_dir=cache_dir)
    cache = AniMediaCacheManager(base_dir=cache_dir)

    # 2. Data layer
    http_client = AniMediaHttpClient(
        base_url=base_url,
        transport=transport,
        logger=log,
    )

    parser = AniMediaParser(
        base_url=base_url,
        logger=log,
    )

    repository = AniMediaRepository(
        http_client=http_client,
        cache=cache,
        parser=parser,
        cache_cfg=cache_cfg,
        logger=log,
    )

    # 3. Business layer
    service = AniMediaService(
        repository=repository,
        logger=log,
    )

    # 4. API layer
    adapter = AniMediaAdapter(
        service=service,
        logger=log,
    )

    log.info(f"AniMedia adapter created for {base_url}")
    return adapter


# Convenience alias
def create_adapter(
        base_url: str,
        net_client: Any,
        cache_dir: Path | str,
        logger: logging.Logger | None = None,
) -> AniMediaAdapter:
    """Alias for create_animedia_adapter with Path coercion."""
    return create_animedia_adapter(
        base_url=base_url,
        net_client=net_client,
        cache_dir=Path(cache_dir) if isinstance(cache_dir, str) else cache_dir,
        logger=logger,
    )