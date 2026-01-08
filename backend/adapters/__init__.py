# backend/adapters/__init__.py
"""
Адаптеры — связывают порты (интерфейсы) с реальными реализациями.
"""

from backend.adapters.title_repository import DBTitleRepository
from backend.adapters.aniliberty_provider import AniLibertyProviderAdapter

__all__ = [
    "DBTitleRepository",
    "AniLibertyProviderAdapter",
]