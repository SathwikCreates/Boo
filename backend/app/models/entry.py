from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List
import json


@dataclass
class Entry:
    """Journal entry model"""
    id: Optional[int] = None
    raw_text: str = ""
    enhanced_text: Optional[str] = None
    structured_summary: Optional[str] = None
    mode: str = "raw"  # raw, enhanced, structured
    embeddings: Optional[List[float]] = None
    timestamp: datetime = None
    mood_tags: Optional[List[str]] = None
    word_count: int = 0
    processing_metadata: Optional[dict] = None
    smart_tags: Optional[List[str]] = None
    memory_extracted: int = 0
    memory_extracted_llm: int = 0
    memory_extracted_at: Optional[datetime] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()
        if self.mood_tags is None:
            self.mood_tags = []
        if self.smart_tags is None:
            self.smart_tags = []
        # Don't automatically set processing_metadata to {} - keep it as None if not provided
        if self.word_count == 0 and self.raw_text:
            self.word_count = len(self.raw_text.split())
    
    def to_dict(self):
        """Convert to dictionary for database storage"""
        return {
            "id": self.id,
            "raw_text": self.raw_text,
            "enhanced_text": self.enhanced_text,
            "structured_summary": self.structured_summary,
            "mode": self.mode,
            "embeddings": json.dumps(self.embeddings) if self.embeddings else None,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "mood_tags": json.dumps(self.mood_tags) if self.mood_tags else None,
            "word_count": self.word_count,
            "processing_metadata": json.dumps(self.processing_metadata) if self.processing_metadata else None,
            "smart_tags": json.dumps(self.smart_tags) if self.smart_tags else None,
            "memory_extracted": self.memory_extracted,
            "memory_extracted_llm": self.memory_extracted_llm,
            "memory_extracted_at": self.memory_extracted_at.isoformat() if self.memory_extracted_at else None
        }
    
    def update_processing_metadata(self, new_metadata: dict):
        """Update processing metadata while preserving existing data"""
        if self.processing_metadata is None:
            self.processing_metadata = new_metadata.copy()
        else:
            self.processing_metadata.update(new_metadata)
    
    @classmethod
    def from_dict(cls, data: dict):
        """Create Entry from database row"""
        # Parse JSON fields
        if data.get("embeddings"):
            data["embeddings"] = json.loads(data["embeddings"])
        if data.get("mood_tags"):
            data["mood_tags"] = json.loads(data["mood_tags"])
        if data.get("processing_metadata"):
            data["processing_metadata"] = json.loads(data["processing_metadata"])
        if data.get("smart_tags"):
            data["smart_tags"] = json.loads(data["smart_tags"])
        if data.get("timestamp"):
            data["timestamp"] = datetime.fromisoformat(data["timestamp"])
        if data.get("memory_extracted_at"):
            data["memory_extracted_at"] = datetime.fromisoformat(data["memory_extracted_at"])
        
        return cls(**data)