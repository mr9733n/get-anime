# providers/animedia/v0/client.py
import asyncio
import logging
import re
from typing import Optional
from urllib.parse import urlparse

from .transport import HttpxTransport
from .retry_manager import retry_async

CONCURRENCY = 8
BATCH_SIZE = 30
INTER_BATCH_DELAY = 1.5
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".svg"}


class AniMediaHttpClient:
    """
    HTTP client: только сетевые операции.
    НЕ отвечает за: кэширование, парсинг, бизнес-логику.
    """

    def __init__(
            self,
            base_url: str,
            transport: HttpxTransport,
            logger: logging.Logger | None = None,
    ):
        self._base_url = base_url.rstrip("/")
        if not self._base_url.startswith(("http://", "https://")):
            self._base_url = f"https://{self._base_url}"
        self._transport = transport
        self._logger = logger or logging.getLogger(__name__)

    @property
    def base_url(self) -> str:
        return self._base_url

    @property
    def ajax_url(self) -> str:
        return f"{self._base_url}/engine/mods/custom/ajax.php"

    # ══════════════════════════════════════════════════════════
    # Basic HTTP operations
    # ══════════════════════════════════════════════════════════

    async def get_page(self, url: str) -> str:
        """GET запрос, возвращает HTML."""
        return await self._transport.get(url)

    async def get_search_page(self, query: str) -> str:
        """Страница поиска."""
        url = f"{self._base_url}/index.php?do=search&story={query}"
        return await self._transport.get(url)

    async def get_ajax_page(self, page: int) -> str:
        """AJAX-запрос для расписания."""
        payload = {
            "name": "poslednie-serii",
            "cstart": str(page),
            "action": "getpage",
        }
        return await self._transport.post(self.ajax_url, data=payload)

    async def get_catalog_page(self, page: int) -> str:
        """Страница каталога."""
        if page == 1:
            url = self._base_url
        else:
            url = f"{self._base_url}/page/{page}/"
        return await self._transport.get(url)

    # ══════════════════════════════════════════════════════════
    # VLNK resolution
    # ══════════════════════════════════════════════════════════

    async def resolve_vlnks(self, vlnk_urls: list[str]) -> list[str]:
        """
        Resolve multiple vlnk URLs to actual file URLs.
        Handles concurrency, batching, and rate limiting.
        """
        # Filter and normalize URLs
        valid_urls = [
            self._ensure_absolute_url(u)
            for u in vlnk_urls
            if u and not self._is_image_placeholder(u)
        ]
        valid_urls = [u for u in valid_urls if u]

        if not valid_urls:
            return []

        self._logger.info(f"Resolving {len(valid_urls)} vlnk URLs")

        # Separate m3u8 (need resolution) from direct links
        m3u8_urls = [u for u in valid_urls if "aser.pro" in u]
        direct_urls = [u for u in valid_urls if "aser.pro" not in u]

        results: list[str] = []

        # Process m3u8 URLs with batching
        semaphore = asyncio.Semaphore(CONCURRENCY)

        async def limited_resolve(url: str) -> Optional[str]:
            async with semaphore:
                return await self._resolve_single_vlnk(url)

        for i in range(0, len(m3u8_urls), BATCH_SIZE):
            batch = m3u8_urls[i:i + BATCH_SIZE]
            self._logger.debug(f"Processing batch {i // BATCH_SIZE + 1}")

            batch_results = await asyncio.gather(
                *(limited_resolve(u) for u in batch),
                return_exceptions=True,
            )

            for result in batch_results:
                if isinstance(result, str) and result:
                    results.append(result)

            if i + BATCH_SIZE < len(m3u8_urls):
                await asyncio.sleep(INTER_BATCH_DELAY)

        # Add direct URLs as-is
        results.extend(direct_urls)

        self._logger.info(f"Resolved {len(results)} file URLs")
        return results

    @retry_async(max_tries=5, base_delay=2.0)
    async def _resolve_single_vlnk(self, vlnk_url: str) -> Optional[str]:
        """Resolve single vlnk to actual file URL."""
        html = await self._transport.get(vlnk_url)

        # Extract file URL from response
        match = re.search(r'file\s*[:=]\s*["\']([^"\']+)["\']', html)
        if not match:
            raise ValueError(f"file not found in response for {vlnk_url}")

        return match.group(1)

    # ══════════════════════════════════════════════════════════
    # URL helpers
    # ══════════════════════════════════════════════════════════

    def _ensure_absolute_url(self, url: str) -> Optional[str]:
        """Ensure URL is absolute."""
        if not url:
            return None

        parsed = urlparse(url)
        if parsed.scheme in ("http", "https"):
            return url
        if url.startswith("/"):
            return f"{self._base_url}{url}"

        self._logger.warning(f"Invalid URL, skipping: {url!r}")
        return None

    @staticmethod
    def _is_image_placeholder(url: str) -> bool:
        """Check if URL looks like an image."""
        parsed = urlparse(url)
        path = parsed.path.lower()
        return any(path.endswith(ext) for ext in IMAGE_EXTS)