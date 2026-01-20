from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List
import json


@dataclass
class Conversation:
    """Conversation model for Talk to Your Diary feature"""
    id: Optional[int] = None
    timestamp: datetime = None
    duration: int = 0  # in seconds
    transcription: str = ""
    conversation_type: str = "chat"  # 'call' or 'chat'
    message_count: int = 0
    search_queries_used: Optional[List[str]] = None
    created_at: datetime = None
    updated_at: Optional[datetime] = None
    # Memory system fields
    embedding: Optional[str] = None
    summary: Optional[str] = None
    key_topics: Optional[List[str]] = None
    memory_extracted: int = 0
    memory_extracted_llm: int = 0
    memory_extracted_at: Optional[datetime] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.search_queries_used is None:
            self.search_queries_used = []
    
    def to_dict(self):
        """Convert to dictionary for database storage"""
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "duration": self.duration,
            "transcription": self.transcription,
            "conversation_type": self.conversation_type,
            "message_count": self.message_count,
            "search_queries_used": json.dumps(self.search_queries_used) if self.search_queries_used else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "embedding": self.embedding,
            "summary": self.summary,
            "key_topics": json.dumps(self.key_topics) if self.key_topics else None,
            "memory_extracted": self.memory_extracted,
            "memory_extracted_llm": self.memory_extracted_llm,
            "memory_extracted_at": self.memory_extracted_at.isoformat() if self.memory_extracted_at else None
        }
    
    def add_search_query(self, query: str):
        """Add a search query to the list"""
        if self.search_queries_used is None:
            self.search_queries_used = []
        if query not in self.search_queries_used:
            self.search_queries_used.append(query)
    
    def update_duration(self, duration_seconds: int):
        """Update conversation duration"""
        self.duration = duration_seconds
        self.updated_at = datetime.now()
    
    def increment_message_count(self):
        """Increment message count and update timestamp"""
        self.message_count += 1
        self.updated_at = datetime.now()
    
    @classmethod
    def from_dict(cls, data: dict):
        """Create Conversation from database row"""
        try:
            # Parse JSON fields
            if data.get("search_queries_used"):
                try:
                    data["search_queries_used"] = json.loads(data["search_queries_used"])
                except (json.JSONDecodeError, TypeError):
                    data["search_queries_used"] = []
            else:
                data["search_queries_used"] = []
            
            # Parse key_topics JSON field
            if data.get("key_topics"):
                try:
                    data["key_topics"] = json.loads(data["key_topics"])
                except (json.JSONDecodeError, TypeError):
                    data["key_topics"] = None
            else:
                data["key_topics"] = None
            
            # Parse datetime fields
            if data.get("timestamp"):
                try:
                    data["timestamp"] = datetime.fromisoformat(data["timestamp"])
                except (ValueError, TypeError):
                    data["timestamp"] = datetime.now()
            
            if data.get("created_at"):
                try:
                    data["created_at"] = datetime.fromisoformat(data["created_at"])
                except (ValueError, TypeError):
                    data["created_at"] = datetime.now()
            
            if data.get("updated_at"):
                try:
                    data["updated_at"] = datetime.fromisoformat(data["updated_at"])
                except (ValueError, TypeError):
                    data["updated_at"] = None
                    
            if data.get("memory_extracted_at"):
                try:
                    data["memory_extracted_at"] = datetime.fromisoformat(data["memory_extracted_at"])
                except (ValueError, TypeError):
                    data["memory_extracted_at"] = None
            
            return cls(**data)
        except Exception:
            # Return a default conversation if parsing fails
            return cls(
                id=data.get("id"),
                transcription=data.get("transcription", ""),
                conversation_type=data.get("conversation_type", "chat"),
                duration=data.get("duration", 0),
                message_count=data.get("message_count", 0),
                embedding=data.get("embedding"),
                summary=data.get("summary"),
                key_topics=data.get("key_topics"),
                memory_extracted=data.get("memory_extracted", 0),
                memory_extracted_llm=data.get("memory_extracted_llm", 0),
                memory_extracted_at=None
            )