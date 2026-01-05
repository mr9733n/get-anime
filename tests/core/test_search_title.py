# tests/core/test_search_title.py
"""
Тесты для SearchTitleUseCase.
Полностью изолированы от Qt.
"""
import pytest
from app.core.use_cases.search_title import (
    SearchTitleUseCase,
    SearchResult,
    SearchSource,
)
from app.core.ports.providers import ISearchResult


# === Fakes ===

class FakeTitleRepository:
    """Fake репозиторий для тестов."""

    def __init__(
            self,
            search_results: tuple[list[int], list[str]] | None = None,
    ):
        self._search_results = search_results or ([], [])
        self._saved: list[dict] = []

    def search_by_keywords(self, keywords: str) -> tuple[list[int], list[str]]:
        return self._search_results

    def save(self, title_data: dict) -> tuple[bool, int | None]:
        self._saved.append(title_data)
        return True, len(self._saved)

    @property
    def saved_count(self) -> int:
        return len(self._saved)


class FakeAnimeProvider:
    """Fake провайдер для тестов."""

    def __init__(
            self,
            search_results: list[ISearchResult] | None = None,
            raise_on_search: Exception | None = None,
    ):
        self._results = search_results or []
        self._raise = raise_on_search
        self.search_calls: list[str] = []

    @property
    def provider_name(self) -> str:
        return "fake_provider"

    def search(self, query: str, *, max_results: int = 10) -> list[ISearchResult]:
        self.search_calls.append(query)
        if self._raise:
            raise self._raise
        return self._results[:max_results]


def make_search_result(external_id: int, name: str) -> ISearchResult:
    """Хелпер для создания ISearchResult."""
    return ISearchResult(
        external_id=external_id,
        name_ru=name,
        name_en=name,
        poster_url=None,
        raw={"external_id": external_id, "name": name},
    )


# === Tests ===

class TestSearchTitleUseCase:
    """Тесты SearchTitleUseCase."""

    def test_empty_query_returns_error(self):
        """Пустой запрос возвращает ошибку."""
        repo = FakeTitleRepository()
        uc = SearchTitleUseCase(repo)

        result = uc.execute("   ")

        assert not result.is_success
        assert result.error == "Empty search query"

    def test_finds_in_local_db(self):
        """Находит в локальной БД."""
        repo = FakeTitleRepository(
            search_results=([1, 2, 3], ["aniliberty", "aniliberty", "aniliberty"])
        )
        uc = SearchTitleUseCase(repo)

        result = uc.execute("naruto")

        assert result.is_success
        assert result.title_ids == [1, 2, 3]
        assert result.source == SearchSource.LOCAL

    def test_falls_back_to_aniliberty_when_local_empty(self):
        """Fallback на AniLiberty когда локально пусто."""
        repo = FakeTitleRepository()
        provider = FakeAnimeProvider([
            make_search_result(100, "Naruto"),
            make_search_result(101, "Naruto Shippuden"),
        ])
        uc = SearchTitleUseCase(repo, aniliberty=provider)

        result = uc.execute("naruto")

        assert result.is_success
        assert result.source == SearchSource.ANILIBERTY
        assert len(result.title_ids) == 2
        assert provider.search_calls == ["naruto"]

    def test_provider_filter_skips_non_matching_local(self):
        """Фильтр провайдера пропускает несовпадающие локальные результаты."""
        repo = FakeTitleRepository(
            search_results=([1, 2], ["aniliberty", "aniliberty"])
        )
        uc = SearchTitleUseCase(repo)

        result = uc.execute("test", provider_filter="animedia")

        # Локальные результаты от aniliberty, но фильтр animedia
        assert not result.is_success
        assert result.source == SearchSource.LOCAL

    def test_returns_animedia_pending_when_others_fail(self):
        """Возвращает animedia_pending когда другие провайдеры не нашли."""
        repo = FakeTitleRepository()
        aniliberty = FakeAnimeProvider([])  # пустой результат
        animedia = FakeAnimeProvider()  # просто наличие

        uc = SearchTitleUseCase(repo, aniliberty=aniliberty, animedia=animedia)

        result = uc.execute("test")

        assert result.is_pending
        assert result.source == SearchSource.ANIMEDIA_PENDING

    def test_aniliberty_error_does_not_crash(self):
        """Ошибка AniLiberty не ломает поиск."""
        repo = FakeTitleRepository()
        provider = FakeAnimeProvider(raise_on_search=RuntimeError("API Error"))

        uc = SearchTitleUseCase(repo, aniliberty=provider)

        # Не должен выбросить исключение
        result = uc.execute("test")

        assert not result.is_success

    def test_persistence_callback_used_when_provided(self):
        """Используется persistence_callback если передан."""
        repo = FakeTitleRepository()
        provider = FakeAnimeProvider([make_search_result(100, "Test")])

        saved_data = []

        def persist(data_list):
            saved_data.extend(data_list)
            return [999]  # возвращаем "сохранённые" ID

        uc = SearchTitleUseCase(
            repo,
            aniliberty=provider,
            persistence_callback=persist,
        )

        result = uc.execute("test")

        assert result.is_success
        assert result.title_ids == [999]
        assert len(saved_data) == 1

    def test_no_aniliberty_skips_to_animedia(self):
        """Без AniLiberty сразу переходит к AniMedia."""
        repo = FakeTitleRepository()
        animedia = FakeAnimeProvider()

        uc = SearchTitleUseCase(repo, animedia=animedia)  # без aniliberty

        result = uc.execute("test")

        assert result.is_pending


class TestSearchResult:
    """Тесты для SearchResult dataclass."""

    def test_is_success_with_results(self):
        result = SearchResult(title_ids=[1, 2])
        assert result.is_success

    def test_is_success_when_pending(self):
        result = SearchResult(source=SearchSource.ANIMEDIA_PENDING)
        assert result.is_success

    def test_not_success_when_empty(self):
        result = SearchResult()
        assert not result.is_success

    def test_count_property(self):
        result = SearchResult(title_ids=[1, 2, 3])
        assert result.count == 3