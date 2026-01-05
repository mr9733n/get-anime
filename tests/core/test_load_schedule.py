# tests/core/test_load_schedule.py
"""Тесты для LoadScheduleUseCase."""
import pytest
from app.core.use_cases.load_schedule import (
    LoadScheduleUseCase,
    ScheduleResult,
)
from app.core.ports.providers import IScheduleItem, ITitleDetails


class FakeTitleRepository:
    def __init__(self):
        self._saved = []

    def save(self, data: dict) -> tuple[bool, int | None]:
        self._saved.append(data)
        return True, len(self._saved)


class FakeScheduleRepository:
    def __init__(self):
        self.saved_schedules = []

    def save_schedule(self, day, title_id, last_updated) -> bool:
        self.saved_schedules.append((day, title_id))
        return True


class FakeScheduleProvider:
    def __init__(
            self,
            schedule: list[IScheduleItem] | None = None,
            details: list[ITitleDetails] | None = None,
    ):
        self._schedule = schedule or []
        self._details = details or []

    @property
    def provider_name(self) -> str:
        return "fake"

    def get_schedule(self, day: int | None = None) -> list[IScheduleItem]:
        return self._schedule

    def get_details_batch(self, external_ids: list) -> list[ITitleDetails]:
        return self._details


class TestLoadScheduleUseCase:

    def test_invalid_day_returns_error(self):
        """Неверный день возвращает ошибку."""
        uc = LoadScheduleUseCase(
            FakeTitleRepository(),
            FakeScheduleRepository(),
            FakeScheduleProvider(),
        )

        result = uc.execute(0)
        assert not result.success
        assert "Invalid day" in result.error

        result = uc.execute(8)
        assert not result.success

    def test_empty_schedule_returns_error(self):
        """Пустое расписание возвращает ошибку."""
        uc = LoadScheduleUseCase(
            FakeTitleRepository(),
            FakeScheduleRepository(),
            FakeScheduleProvider(schedule=[]),
        )

        result = uc.execute(1)

        assert not result.success
        assert "No schedule data" in result.error

    def test_successful_schedule_load(self):
        """Успешная загрузка расписания."""
        schedule = [
            IScheduleItem(day=1, external_id=100, name_ru="Test1", name_en="Test1", raw=None),
            IScheduleItem(day=1, external_id=101, name_ru="Test2", name_en="Test2", raw=None),
        ]
        details = [
            ITitleDetails(
                external_id=100, name_ru="Test1", name_en="Test1",
                code="t1", description=None, poster_url=None,
                status_code=1, status_string="ongoing", year=2024,
                type_string="TV", episodes=[], torrents=[],
                host_for_player=None, raw={"external_id": 100},
            ),
            ITitleDetails(
                external_id=101, name_ru="Test2", name_en="Test2",
                code="t2", description=None, poster_url=None,
                status_code=1, status_string="ongoing", year=2024,
                type_string="TV", episodes=[], torrents=[],
                host_for_player=None, raw={"external_id": 101},
            ),
        ]

        schedule_repo = FakeScheduleRepository()
        uc = LoadScheduleUseCase(
            FakeTitleRepository(),
            schedule_repo,
            FakeScheduleProvider(schedule=schedule, details=details),
        )

        result = uc.execute(1)

        assert result.success
        assert result.count == 2
        assert len(schedule_repo.saved_schedules) == 2


