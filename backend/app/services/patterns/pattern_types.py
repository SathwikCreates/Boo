from enum import Enum
from dataclasses import dataclass
from typing import List, Optional
from datetime import datetime


class PatternType(Enum):
    MOOD = "mood"
    TOPIC = "topic"
    BEHAVIOR = "behavior"
    TEMPORAL = "temporal"


@dataclass
class Pattern:
    """Pattern model for detected patterns in journal entries"""
    id: Optional[int] = None
    pattern_type: PatternType = PatternType.TOPIC
    description: str = ""
    frequency: int = 0
    confidence: float = 0.0
    first_seen: Optional[datetime] = None
    last_seen: Optional[datetime] = None
    related_entries: List[int] = None
    keywords: List[str] = None  # Keywords associated with this pattern
    
    def __post_init__(self):
        if self.related_entries is None:
            self.related_entries = []
        if self.keywords is None:
            self.keywords = []
    
    def to_dict(self):
        """Convert pattern to dictionary for database storage"""
        import json
        return {
            "id": self.id,
            "pattern_type": self.pattern_type.value,
            "description": self.description,
            "frequency": self.frequency,
            "confidence": self.confidence,
            "first_seen": self.first_seen.isoformat() if self.first_seen else None,
            "last_seen": self.last_seen.isoformat() if self.last_seen else None,
            "related_entries": json.dumps(self.related_entries),
            "keywords": json.dumps(self.keywords) if hasattr(self, 'keywords') else "[]"
        }
    
    @classmethod
    def from_dict(cls, data: dict):
        """Create Pattern from database row"""
        import json
        return cls(
            id=data.get("id"),
            pattern_type=PatternType(data["pattern_type"]),
            description=data["description"],
            frequency=data["frequency"],
            confidence=data["confidence"],
            first_seen=datetime.fromisoformat(data["first_seen"]) if data.get("first_seen") else None,
            last_seen=datetime.fromisoformat(data["last_seen"]) if data.get("last_seen") else None,
            related_entries=json.loads(data.get("related_entries", "[]")),
            keywords=json.loads(data.get("keywords", "[]")) if data.get("keywords") else []
        )