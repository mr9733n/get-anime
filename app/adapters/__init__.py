# app/adapters/__init__.py
"""
Адаптеры — связывают порты (интерфейсы) с реальными реализациями.
"""

from app.adapters.title_repository import DBTitleRepository
from app.adapters.aniliberty_provider import AniLibertyProviderAdapter

__all__ = [
    "DBTitleRepository",
    "AniLibertyProviderAdapter",
]