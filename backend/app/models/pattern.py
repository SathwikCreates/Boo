from dataclasses import dataclass
from datetime import date
from typing import Optional, List
import json


@dataclass
class Pattern:
    """Pattern model for detected patterns in journal entries"""
    id: Optional[int] = None
    pattern_type: str = ""  # 'mood', 'topic', 'behavior', 'temporal'
    description: str = ""
    frequency: int = 0
    confidence: float = 0.0  # 0.0 to 1.0
    first_seen: Optional[date] = None
    last_seen: Optional[date] = None
    related_entries: Optional[List[int]] = None 
    keywords: Optional[List[str]] = None  # Keywords associated with this pattern
    
    def __post_init__(self):
        if self.related_entries is None:
            self.related_entries = []
        if self.keywords is None:
            self.keywords = []
    
    def to_dict(self):
        """Convert to dictionary for database storage"""
        return {
            "id": self.id,
            "pattern_type": self.pattern_type,
            "description": self.description,
            "frequency": self.frequency,
            "confidence": self.confidence,
            "first_seen": self.first_seen.isoformat() if self.first_seen else None,
            "last_seen": self.last_seen.isoformat() if self.last_seen else None,
            "related_entries": json.dumps(self.related_entries) if self.related_entries else None,
            "keywords": json.dumps(self.keywords) if self.keywords else None
        }
    
    @classmethod
    def from_dict(cls, data: dict):
        """Create Pattern from database row"""
        # Parse JSON fields
        if data.get("related_entries"):
            data["related_entries"] = json.loads(data["related_entries"])
        if data.get("keywords"):
            data["keywords"] = json.loads(data["keywords"])
        if data.get("first_seen"):
            data["first_seen"] = date.fromisoformat(data["first_seen"])
        if data.get("last_seen"):
            data["last_seen"] = date.fromisoformat(data["last_seen"])
        
        return cls(**data)