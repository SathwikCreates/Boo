from .entry_repository import EntryRepository
from .pattern_repository import PatternRepository
from .preferences_repository import PreferencesRepository
from .draft_repository import DraftRepository

# Repository instances
_preferences_repo = None

async def get_preferences_repository() -> PreferencesRepository:
    """Get global preferences repository instance"""
    # PreferencesRepository is a static class, just return the class
    return PreferencesRepository

__all__ = [
    "EntryRepository",
    "PatternRepository", 
    "PreferencesRepository",
    "DraftRepository",
    "get_preferences_repository"
]