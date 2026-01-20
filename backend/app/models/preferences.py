from dataclasses import dataclass
from typing import Optional
import json


@dataclass
class Preferences:
    """User preferences model"""
    id: Optional[int] = None
    key: str = ""
    value: str = ""
    value_type: str = "string"  # string, int, float, bool, json
    description: Optional[str] = None
    
    def to_dict(self):
        """Convert to dictionary for database storage"""
        return {
            "id": self.id,
            "key": self.key,
            "value": self.value,
            "value_type": self.value_type,
            "description": self.description
        }
    
    def get_typed_value(self):
        """Get value with proper type conversion"""
        if self.value_type == "int":
            return int(self.value)
        elif self.value_type == "float":
            return float(self.value)
        elif self.value_type == "bool":
            return self.value.lower() in ("true", "1", "yes")
        elif self.value_type == "json":
            return json.loads(self.value)
        else:
            return self.value
    
    @classmethod
    def from_dict(cls, data: dict):
        """Create Preferences from database row"""
        return cls(**data)