from pydantic_settings import BaseSettings
from typing import Optional
import os


class Settings(BaseSettings):
    # Application settings
    APP_NAME: str = "Boo Journal"
    VERSION: str = "0.1.0"
    DEBUG: bool = True
    
    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./boo.db"
    
    # API settings
    API_V1_STR: str = "/api/v1"
    
    # CORS settings
    BACKEND_CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:8000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:8000"
    ]
    
    # Ollama settings
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_DEFAULT_MODEL: str = "mistral:latest"
    OLLAMA_TIMEOUT: int = 30
    
    # STT settings
    WHISPER_MODEL: str = "base"
    WHISPER_DEVICE: str = "cpu"
    WHISPER_LANGUAGE: Optional[str] = "english"
    
    # Embedding settings
    EMBEDDING_MODEL: str = "BAAI/bge-small-en-v1.5"
    EMBEDDING_DIMENSION: int = 384
    
    # File paths
    DATA_DIR: str = "./data"
    AUDIO_DIR: str = "./data/audio"
    EMBEDDING_CACHE_DIR: str = "./data/embeddings"
    
    # Hotkey settings
    DEFAULT_HOTKEY: str = "F8"
    
    # Pattern detection settings
    MIN_ENTRIES_FOR_PATTERNS: int = 30
    PATTERN_CONFIDENCE_THRESHOLD: float = 0.7
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


settings = Settings()

# Create necessary directories
os.makedirs(settings.DATA_DIR, exist_ok=True)
os.makedirs(settings.AUDIO_DIR, exist_ok=True)
os.makedirs(settings.EMBEDDING_CACHE_DIR, exist_ok=True)