# providers/animedia/v0/service.py
import asyncio
import logging
from typing import Any

from .repository import AniMediaRepository
from .models import Title

MAX_CONCURRENT = 3


class AniMediaService:
    """
    Business logic layer: policies, orchestration, concurrency strategies.
    """

    def __init__(
            self,
            repository: AniMediaRepository,
            logger: logging.Logger | None = None,
    ):
        self._repo = repository
        self._logger = logger or logging.getLogger(__name__)

    # ══════════════════════════════════════════════════════════
    # Title search
    # ══════════════════════════════════════════════════════════

    async def get_titles_by_name(self, name: str, max_titles: int = 5) -> list[Title]:
        """
        Поиск и загрузка полных данных тайтлов.
        Policy: ограничение concurrent запросов.
        """
        urls = await self._repo.search_title_urls(name, max_titles)

        if not urls:
            self._logger.info(f"No titles found for '{name}'")
            return []

        semaphore = asyncio.Semaphore(MAX_CONCURRENT)

        async def fetch_limited(url: str) -> Title:
            async with semaphore:
                return await self._repo.fetch_title(url)

        titles = await asyncio.gather(
            *(fetch_limited(u) for u in urls),
            return_exceptions=True,
        )

        # Фильтруем ошибки
        valid_titles = [t for t in titles if isinstance(t, Title)]
        errors = [t for t in titles if isinstance(t, Exception)]

        if errors:
            self._logger.warning(f"Failed to fetch {len(errors)} titles: {errors}")

        self._logger.info(f"Found {len(valid_titles)} titles for '{name}'")
        return valid_titles

    # ══════════════════════════════════════════════════════════
    # Schedule (new titles)
    # ══════════════════════════════════════════════════════════

    async def get_schedule(self, max_titles: int = 60) -> list[dict[str, Any]]:
        """
        Получить расписание (новые серии + анонсы).
        Policy: cache-first, pagination with early exit.
        """
        # 1. Cache check
        cached = self._repo.load_schedule_cache()
        if cached:
            self._logger.info("Schedule loaded from cache")
            return cached

        # 2. Get total pages
        total_pages = await self._repo.get_total_ajax_pages()
        self._logger.info(f"Schedule has {total_pages} pages")

        results: list[dict[str, Any]] = []
        collected = 0

        # 3. First page: announcements (page 0 = main page)
        first_html = await self._repo.fetch_first_page()
        announce = await self._repo.parse_announce_titles(first_html, max_titles)
        if announce:
            results.append({"page": 0, "titles": announce})
            collected += len(announce)
            self._logger.debug(f"Collected {len(announce)} announcements")

        # 4. Early exit check
        if collected >= max_titles:
            return self._finalize_schedule(results)

        # 5. Remaining pages with concurrency
        semaphore = asyncio.Semaphore(MAX_CONCURRENT)

        async def fetch_page(page: int) -> tuple[int, list[str]]:
            async with semaphore:
                remaining = max_titles - collected
                if remaining <= 0:
                    return page, []
                html = await self._repo.fetch_schedule_page(page)
                titles = await self._repo.parse_new_titles(html, remaining)
                return page, titles

        tasks = [fetch_page(p) for p in range(1, total_pages + 1)]

        for coro in asyncio.as_completed(tasks):
            page, titles = await coro
            if titles:
                results.append({"page": page, "titles": titles})
                collected += len(titles)
                self._logger.debug(f"Page {page}: collected {len(titles)} titles")
                if collected >= max_titles:
                    break

        return self._finalize_schedule(results)

    def _finalize_schedule(self, results: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Dedupe, sort, cache."""
        for entry in results:
            entry["titles"] = self._unique_preserve_order(entry["titles"])
        results.sort(key=lambda x: x["page"])

        self._repo.save_schedule_cache(results)
        self._logger.info(f"Schedule finalized: {sum(len(e['titles']) for e in results)} titles")
        return results

    # ══════════════════════════════════════════════════════════
    # All titles (catalog)
    # ══════════════════════════════════════════════════════════

    async def get_all_titles(
            self,
            max_titles: int = 60,
            pages_per_request: int = 5,
    ) -> list[dict[str, Any]]:
        """
        Получить каталог всех тайтлов.
        Policy: incremental loading with cache, resume from last page.
        """
        # 1. Load cached data
        cached = self._repo.load_all_titles_cache() or []
        collected, last_cached_page = self._repo.get_cached_all_titles_stats()

        if collected >= max_titles:
            self._logger.info("All titles loaded from cache")
            return cached

        # 2. Calculate pagination
        total_pages = await self._repo.get_total_catalog_pages()
        titles_per_page = max_titles // pages_per_request if pages_per_request else 12

        start_page = (collected // titles_per_page) + 1 if titles_per_page else 1
        end_page = min(start_page + pages_per_request - 1, total_pages)

        self._logger.info(
            f"Fetching catalog pages {start_page}-{end_page} "
            f"(cached: {collected}, target: {max_titles})"
        )

        # 3. Fetch pages concurrently
        semaphore = asyncio.Semaphore(MAX_CONCURRENT)

        async def fetch_page(page: int) -> dict[str, Any]:
            async with semaphore:
                html = await self._repo.fetch_catalog_page(page)
                remaining = max_titles - collected
                titles = await self._repo.parse_catalog_titles(html, remaining)
                return {"page": page, "titles": titles}

        tasks = [fetch_page(p) for p in range(start_page, end_page + 1)]
        new_results = await asyncio.gather(*tasks)

        # 4. Merge with cache
        all_results = cached + [r for r in new_results if r["titles"]]

        # 5. Dedupe and sort
        for entry in all_results:
            entry["titles"] = self._unique_preserve_order(entry["titles"])
        all_results.sort(key=lambda x: x["page"])

        # 6. Save to cache
        self._repo.save_all_titles_cache(all_results)

        total_collected = sum(len(e["titles"]) for e in all_results)
        self._logger.info(f"All titles finalized: {total_collected} titles")
        return all_results

    # ══════════════════════════════════════════════════════════
    # Utilities
    # ══════════════════════════════════════════════════════════

    @staticmethod
    def _unique_preserve_order(seq: list[str]) -> list[str]:
        """Remove duplicates preserving order."""
        seen: set[str] = set()
        result: list[str] = []
        for item in seq:
            if item not in seen:
                seen.add(item)
                result.append(item)
        return result