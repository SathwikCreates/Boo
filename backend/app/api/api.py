from fastapi import APIRouter

from app.api.routes import (
    entries_router,
    preferences_router,
    health_router,
    stt_router,
    hotkey_router,
    websocket_router,
    ollama_router,
    drafts_router,
    embeddings_router,
    patterns_router,
    tts_router,
    conversations_router,
    diary_chat_router,
    audio_router,
    memories_router,
    auth_router
)
from app.core.config import settings

# Create main API router
api_router = APIRouter(prefix=settings.API_V1_STR)

# Include all route modules
api_router.include_router(entries_router)
api_router.include_router(preferences_router)
api_router.include_router(health_router)
api_router.include_router(stt_router)
api_router.include_router(hotkey_router)
api_router.include_router(websocket_router)
api_router.include_router(ollama_router)
api_router.include_router(drafts_router)
api_router.include_router(embeddings_router)
api_router.include_router(patterns_router)
api_router.include_router(tts_router)
api_router.include_router(conversations_router)
api_router.include_router(diary_chat_router)
api_router.include_router(audio_router)
api_router.include_router(memories_router)
api_router.include_router(auth_router)