"""
Entry-related schemas and models for the API.
"""

from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime


class ProcessingMode(str, Enum):
    """Available processing modes for journal entries."""
    RAW = "raw"
    ENHANCED = "enhanced"  
    STRUCTURED = "structured"


class EntryProcessRequest(BaseModel):
    """Request schema for processing an entry."""
    mode: ProcessingMode = Field(..., description="Processing mode to apply")


class EntryCreateAndProcessRequest(BaseModel):
    """Request schema for creating and processing an entry."""
    raw_text: str = Field(..., min_length=1, description="Raw transcription text")
    modes: List[ProcessingMode] = Field(..., description="Processing modes to apply")


class EntryProcessOnlyRequest(BaseModel):
    """Request schema for processing text without database operations."""
    raw_text: str = Field(..., min_length=1, description="Raw transcription text")
    modes: List[ProcessingMode] = Field(..., description="Processing modes to apply")


class EntryCreateRequest(BaseModel):
    """Request schema for creating a new entry."""
    raw_text: str = Field(..., min_length=1, description="Raw transcription text")
    mode: ProcessingMode = Field(default=ProcessingMode.RAW, description="Initial processing mode")


class EntryUpdateRequest(BaseModel):
    """Request schema for updating an entry."""
    raw_text: Optional[str] = Field(None, description="Updated raw text")
    enhanced_text: Optional[str] = Field(None, description="Updated enhanced text")
    structured_summary: Optional[str] = Field(None, description="Updated structured summary")
    mode: Optional[ProcessingMode] = Field(None, description="Updated processing mode")
    mood_tags: Optional[List[str]] = Field(None, description="Updated mood tags")


class EntryResponse(BaseModel):
    """Response schema for entry data."""
    id: int
    raw_text: str
    enhanced_text: Optional[str] = None
    structured_summary: Optional[str] = None
    mode: str
    embeddings: Optional[List[float]] = None
    timestamp: datetime
    mood_tags: Optional[List[str]] = None
    word_count: Optional[int] = None
    processing_metadata: Optional[Dict[str, Any]] = None
    
    class Config:
        from_attributes = True


class EntryListResponse(BaseModel):
    """Response schema for paginated entry lists."""
    entries: List[EntryResponse]
    total: int
    page: int
    page_size: int
    has_next: bool
    has_prev: bool


class EntrySearchRequest(BaseModel):
    """Request schema for searching entries."""
    query: str = Field(..., min_length=1, description="Search query")
    limit: int = Field(default=20, ge=1, le=100, description="Maximum results to return")


class ProcessingStatistics(BaseModel):
    """Statistics about entry processing."""
    total_entries: int
    raw_entries: int
    enhanced_entries: int
    structured_entries: int
    avg_processing_time_ms: Optional[float] = None
    avg_word_count: Optional[float] = None