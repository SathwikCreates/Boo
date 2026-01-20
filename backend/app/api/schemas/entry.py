from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List


class EntryCreate(BaseModel):
    """Schema for creating a new entry"""
    raw_text: str = Field(..., min_length=1, description="Raw journal text")
    enhanced_text: Optional[str] = Field(None, description="Enhanced version of the text")
    structured_summary: Optional[str] = Field(None, description="Structured summary of the text")
    mode: str = Field(default="raw", description="Processing mode")
    custom_timestamp: Optional[datetime] = Field(None, description="Custom timestamp for the entry (for backfilling)")
    processing_metadata: Optional[dict] = Field(None, description="Processing metadata from AI processing")
    
    class Config:
        json_schema_extra = {
            "example": {
                "raw_text": "Today was a great day. I learned something new.",
                "enhanced_text": "Today was an excellent day. I learned something fascinating.",
                "structured_summary": "• Had a positive day\n• Learned something new",
                "mode": "raw"
            }
        }


class EntryUpdate(BaseModel):
    """Schema for updating an entry"""
    raw_text: Optional[str] = Field(None, min_length=1)
    enhanced_text: Optional[str] = None
    structured_summary: Optional[str] = None
    mode: Optional[str] = None
    mood_tags: Optional[List[str]] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "enhanced_text": "Today was an excellent day. I learned something fascinating.",
                "mode": "enhanced"
            }
        }


class EntryResponse(BaseModel):
    """Schema for entry response"""
    id: int
    raw_text: str
    enhanced_text: Optional[str] = None
    structured_summary: Optional[str] = None
    mode: str
    embeddings: Optional[List[float]] = None
    timestamp: datetime
    mood_tags: Optional[List[str]] = None
    word_count: int
    processing_metadata: Optional[dict] = None
    smart_tags: Optional[List[str]] = None
    
    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": 1,
                "raw_text": "Today was a great day.",
                "enhanced_text": "Today was an excellent day.",
                "structured_summary": "Had a positive day with learning.",
                "mode": "structured",
                "timestamp": "2024-01-01T12:00:00",
                "mood_tags": ["positive", "learning"],
                "word_count": 6,
                "processing_metadata": {"model": "llama2", "processing_time": 1.5}
            }
        }


class EntryListResponse(BaseModel):
    """Schema for paginated entry list response"""
    entries: List[EntryResponse]
    total: int
    page: int
    page_size: int
    has_next: bool
    has_prev: bool


class EntrySearchRequest(BaseModel):
    """Schema for entry search request"""
    query: str = Field(..., min_length=1, description="Search query")
    limit: int = Field(default=50, ge=1, le=100, description="Maximum results")
    
    class Config:
        json_schema_extra = {
            "example": {
                "query": "learning",
                "limit": 20
            }
        }


class MoodAnalysisRequest(BaseModel):
    """Schema for mood analysis request"""
    text: str = Field(..., min_length=1, description="Text to analyze for mood")
    
    class Config:
        json_schema_extra = {
            "example": {
                "text": "I had a wonderful day today. Felt really happy and accomplished after finishing my project."
            }
        }


class MoodAnalysisResponse(BaseModel):
    """Schema for mood analysis response"""
    mood_tags: List[str] = Field(..., description="Extracted mood tags")
    
    class Config:
        json_schema_extra = {
            "example": {
                "mood_tags": ["happy", "accomplished", "content"]
            }
        }