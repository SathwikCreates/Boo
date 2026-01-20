from dataclasses import dataclass
from datetime import datetime
from typing import Optional
import json


@dataclass
class Draft:
    """Draft model for auto-save functionality"""
    id: Optional[int] = None
    content: str = ""
    metadata: Optional[dict] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.metadata is None:
            self.metadata = {}
    
    def to_dict(self):
        """Convert to dictionary for database storage"""
        return {
            "id": self.id,
            "content": self.content,
            "metadata": json.dumps(self.metadata) if self.metadata else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
    
    @classmethod
    def from_dict(cls, data: dict):
        """Create Draft from database row"""
        # Parse JSON fields
        if data.get("metadata"):
            data["metadata"] = json.loads(data["metadata"])
        if data.get("created_at"):
            data["created_at"] = datetime.fromisoformat(data["created_at"])
        if data.get("updated_at"):
            data["updated_at"] = datetime.fromisoformat(data["updated_at"])
        
        return cls(**data)