# providers/animedia/v0/__init__.py
"""
AniMedia provider package.
"""

# Публичный API — полные пути
from providers.animedia.v0.adapter import AniMediaAdapter
from providers.animedia.v0.service import AniMediaService
from providers.animedia.v0.repository import AniMediaRepository
from providers.animedia.v0.client import AniMediaHttpClient
from providers.animedia.v0.models import Title, Episode, TitleStatus, ScheduleItem
from providers.animedia.v0.factory import create_animedia_adapter, create_adapter

__all__ = [
    # Public API
    "AniMediaAdapter",
    "create_animedia_adapter",
    "create_adapter",
    # Domain models
    "Title",
    "Episode",
    "TitleStatus",
    "ScheduleItem",
    # Internal (for testing/extension)
    "AniMediaService",
    "AniMediaRepository",
    "AniMediaHttpClient",
]