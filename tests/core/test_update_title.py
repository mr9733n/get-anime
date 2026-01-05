# tests/core/test_update_title.py
"""Тесты для UpdateTitleUseCase."""
import pytest
from app.core.use_cases.update_title import (
    UpdateTitleUseCase,
    UpdateResult,
    UpdateSource,
    TitleRef,
)
from app.core.ports.providers import ITitleDetails


class FakeTitleRepository:
    """Fake репозиторий — сохраняет данные и возвращает ID."""

    def __init__(self):
        self._saved: list[dict] = []
        self._next_id = 1

    def save(self, data: dict) -> tuple[bool, int | None]:
        self._saved.append(data)
        title_id = self._next_id
        self._next_id += 1
        return True, title_id

    @property
    def saved_count(self) -> int:
        return len(self._saved)


class FakeAnimeProvider:
    """Fake провайдер — возвращает заданные детали."""

    def __init__(
            self,
            details: ITitleDetails | None = None,
            raise_error: Exception | None = None,
    ):
        self._details = details
        self._raise = raise_error
        self.get_details_calls: list[str] = []

    @property
    def provider_name(self) -> str:
        return "fake"

    def get_details(self, external_id) -> ITitleDetails | None:
        self.get_details_calls.append(str(external_id))
        if self._raise:
            raise self._raise
        return self._details


def make_details(external_id: int) -> ITitleDetails:
    """Хелпер для создания ITitleDetails."""
    return ITitleDetails(
        external_id=external_id,
        name_ru="Test Title",
        name_en="Test Title",
        code="test-title",
        description="Test description",
        poster_url=None,
        status_code=1,
        status_string="ongoing",
        year=2024,
        type_string="TV",
        episodes=[],
        torrents=[],
        host_for_player=None,
        raw={"external_id": external_id, "name": "Test Title"},  # важно: raw не None
    )


class TestUpdateTitleUseCase:
    """Тесты UpdateTitleUseCase."""

    def test_update_via_aniliberty_success(self):
        """Успешное обновление через AniLiberty."""
        repo = FakeTitleRepository()
        provider = FakeAnimeProvider(details=make_details(100))

        uc = UpdateTitleUseCase(repo, aniliberty=provider)

        ref = TitleRef(
            title_id=1,
            external_id=100,
            provider="aniliberty",
            name_en="Test",
            name_ru="Тест",
        )

        result = uc.execute(ref)

        assert result.success, f"Expected success, got error: {result.error}"
        assert result.source == UpdateSource.ANILIBERTY
        assert result.title_id == 1  # первый сохранённый ID
        assert provider.get_details_calls == ["100"]
        assert repo.saved_count == 1

    def test_update_via_aniliberty_with_persistence_callback(self):
        """Обновление с использованием persistence_callback."""
        repo = FakeTitleRepository()
        provider = FakeAnimeProvider(details=make_details(100))

        persisted_data = []

        def persist_callback(data_list: list[dict]) -> list[int]:
            persisted_data.extend(data_list)
            return [999]  # возвращаем "сохранённый" ID

        uc = UpdateTitleUseCase(
            repo,
            aniliberty=provider,
            persistence_callback=persist_callback,
        )

        ref = TitleRef(
            title_id=1,
            external_id=100,
            provider="aniliberty",
            name_en="Test",
            name_ru="Тест",
        )

        result = uc.execute(ref)

        assert result.success
        assert result.title_id == 999  # ID из callback
        assert len(persisted_data) == 1
        assert repo.saved_count == 0  # repo.save НЕ вызывался

    def test_update_animedia_returns_pending(self):
        """Обновление через AniMedia возвращает pending."""
        repo = FakeTitleRepository()
        animedia = FakeAnimeProvider()

        uc = UpdateTitleUseCase(repo, animedia=animedia)

        ref = TitleRef(
            title_id=1,
            external_id="abc",
            provider="animedia",
            name_en=None,
            name_ru=None,
        )

        result = uc.execute(ref)

        assert result.is_pending
        assert result.source == UpdateSource.ANIMEDIA_PENDING

    def test_unknown_provider_returns_error(self):
        """Неизвестный провайдер возвращает ошибку."""
        repo = FakeTitleRepository()
        uc = UpdateTitleUseCase(repo)

        ref = TitleRef(
            title_id=1,
            external_id=100,
            provider="unknown_provider",
            name_en=None,
            name_ru=None,
        )

        result = uc.execute(ref)

        assert not result.success
        assert result.error is not None
        assert "Unknown provider" in result.error

    def test_no_provider_available_returns_error(self):
        """Нет доступного провайдера — ошибка."""
        repo = FakeTitleRepository()
        uc = UpdateTitleUseCase(repo)  # без провайдеров

        ref = TitleRef(
            title_id=1,
            external_id=100,
            provider="aniliberty",
            name_en="Test",
            name_ru="Тест",
        )

        result = uc.execute(ref)

        assert not result.success
        assert "not available" in result.error

    def test_title_not_found_in_provider(self):
        """Тайтл не найден у провайдера."""
        repo = FakeTitleRepository()
        provider = FakeAnimeProvider(details=None)  # возвращает None

        uc = UpdateTitleUseCase(repo, aniliberty=provider)

        ref = TitleRef(
            title_id=1,
            external_id=999,
            provider="aniliberty",
            name_en="Nonexistent",
            name_ru="Несуществующий",
        )

        result = uc.execute(ref)

        assert not result.success
        assert "not found" in result.error

    def test_provider_exception_handled(self):
        """Исключение провайдера обрабатывается."""
        repo = FakeTitleRepository()
        provider = FakeAnimeProvider(raise_error=RuntimeError("API Error"))

        uc = UpdateTitleUseCase(repo, aniliberty=provider)

        ref = TitleRef(
            title_id=1,
            external_id=100,
            provider="aniliberty",
            name_en="Test",
            name_ru="Тест",
        )

        result = uc.execute(ref)

        assert not result.success
        assert "API Error" in result.error

    def test_build_query_uses_external_id_first(self):
        """_build_query приоритет: external_id > name_en > name_ru."""
        repo = FakeTitleRepository()
        provider = FakeAnimeProvider(details=make_details(100))

        uc = UpdateTitleUseCase(repo, aniliberty=provider)

        ref = TitleRef(
            title_id=1,
            external_id=100,
            provider="aniliberty",
            name_en="English Name",
            name_ru="Русское имя",
        )

        uc.execute(ref)

        # Должен искать по external_id, а не по имени
        assert provider.get_details_calls == ["100"]

    def test_build_query_fallback_to_name(self):
        """Fallback на имя если external_id отсутствует."""
        repo = FakeTitleRepository()
        provider = FakeAnimeProvider(details=make_details(100))

        uc = UpdateTitleUseCase(repo, aniliberty=provider)

        ref = TitleRef(
            title_id=1,
            external_id=None,  # нет external_id
            provider="aniliberty",
            name_en="English Name",
            name_ru="Русское имя",
        )

        uc.execute(ref)

        # Должен искать по name_en
        assert provider.get_details_calls == ["English Name"]

    def test_execute_batch(self):
        """Batch обновление нескольких тайтлов."""
        repo = FakeTitleRepository()
        provider = FakeAnimeProvider(details=make_details(100))

        uc = UpdateTitleUseCase(repo, aniliberty=provider)

        refs = [
            TitleRef(1, 100, "aniliberty", "Test1", None),
            TitleRef(2, 101, "aniliberty", "Test2", None),
            TitleRef(3, 102, "aniliberty", "Test3", None),
        ]

        results = uc.execute_batch(refs)

        assert len(results) == 3
        assert all(r.success for r in results)
        assert repo.saved_count == 3