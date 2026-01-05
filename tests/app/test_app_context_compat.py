# tests/test_app_context_compat.py
"""Тест обратной совместимости AppContext."""
import pytest


def test_business_state_standalone():
    """BusinessState работает без Qt."""
    from app.core.state import BusinessState

    state = BusinessState()
    state.current_title_id = 123
    state.current_offset = 10

    assert state.current_title_id == 123
    assert state.current_offset == 10


def test_business_state_serialization():
    """BusinessState сериализуется в dict."""
    from app.core.state import BusinessState

    state = BusinessState()
    state.current_title_id = 456
    state.current_show_mode = "system"

    data = state.to_dict()
    assert data["current_title_id"] == 456
    assert data["show_mode"] == "system"

    restored = BusinessState.from_dict(data)
    assert restored.current_title_id == 456
    assert restored.current_show_mode == "system"


def test_app_context_backward_compat():
    """AppContext сохраняет обратную совместимость."""
    from app.qt.app_context import AppContext

    ctx = AppContext()

    # Старый способ — напрямую
    ctx.current_title_id = 789
    ctx.current_offset = 20
    ctx.app_version = "1.0.0"

    # Проверяем что данные попали в business
    assert ctx.business.current_title_id == 789
    assert ctx.business.current_offset == 20
    assert ctx.business.app_version == "1.0.0"

    # Проверяем что чтение тоже работает
    assert ctx.current_title_id == 789
    assert ctx.current_offset == 20


def test_app_context_ui_state():
    """UIState изолирован от BusinessState."""
    from app.qt.app_context import AppContext, UIState

    ctx = AppContext()

    # UI поля не должны быть в business
    assert not hasattr(ctx.business, 'title_search_entry')
    assert not hasattr(ctx.business, 'posters_layout')

    # Но доступны через ctx напрямую
    ctx.title_search_entry = None  # без Qt виджета
    assert ctx.ui.title_search_entry is None


