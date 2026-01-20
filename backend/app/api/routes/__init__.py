from .entries import router as entries_router
from .preferences import router as preferences_router  
from .health import router as health_router
from .stt import router as stt_router
from .hotkey import router as hotkey_router
from .websocket import router as websocket_router
from .ollama import router as ollama_router
from .drafts import router as drafts_router
from .embeddings import router as embeddings_router
from .patterns import router as patterns_router
from .tts import router as tts_router
from .conversations import router as conversations_router
from .diary_chat import router as diary_chat_router
from .audio import router as audio_router
from .memories import router as memories_router
from .auth import router as auth_router

__all__ = [
    "entries_router",
    "preferences_router",
    "health_router",
    "stt_router",
    "hotkey_router",
    "websocket_router",
    "ollama_router",
    "drafts_router",
    "embeddings_router",
    "patterns_router",
    "tts_router",
    "conversations_router",
    "diary_chat_router",
    "audio_router",
    "memories_router",
    "auth_router"
]