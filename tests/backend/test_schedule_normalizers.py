"""Unit tests for schedule normalizer helpers."""
from datetime import datetime

from backend.infra.providers.animedia_schedule_source import _parse_animedia_meta


_REF = datetime(2026, 1, 7, 12, 0)  # Wednesday


def test_parse_today():
    dt = _parse_animedia_meta("Сегодня, 16:00", now=_REF)
    assert dt is not None
    assert dt.date() == _REF.date()
    assert dt.hour == 16
    assert dt.minute == 0


def test_parse_yesterday():
    dt = _parse_animedia_meta("Вчера, 09:30", now=_REF)
    assert dt is not None
    assert dt.day == _REF.day - 1
    assert dt.hour == 9
    assert dt.minute == 30


def test_parse_explicit_date():
    dt = _parse_animedia_meta("7-01-2026, 16:00", now=_REF)
    assert dt is not None
    assert dt.year == 2026
    assert dt.month == 1
    assert dt.day == 7
    assert dt.hour == 16


def test_parse_empty_returns_none():
    assert _parse_animedia_meta("") is None
    assert _parse_animedia_meta("   ") is None


def test_parse_unknown_returns_none():
    assert _parse_animedia_meta("Неизвестно, 10:00", now=_REF) is None


def test_parse_no_time_defaults_to_midnight():
    dt = _parse_animedia_meta("Сегодня", now=_REF)
    assert dt is not None
    assert dt.date() == _REF.date()
    assert dt.hour == 0
    assert dt.minute == 0


def test_day_of_week_derived_from_air_dt():
    """air_dt.isoweekday() must match the expected weekday."""
    # 7-01-2026 is a Wednesday (isoweekday=3)
    dt = _parse_animedia_meta("7-01-2026, 16:00")
    assert dt is not None
    assert dt.isoweekday() == 3  # Wednesday
