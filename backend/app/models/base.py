from datetime import datetime
from typing import Optional, Dict, Any


class BaseModel:
    """Base model class for database entities"""
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]):
        """Create instance from dictionary"""
        return cls(**data)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert instance to dictionary"""
        return {k: v for k, v in self.__dict__.items() if not k.startswith('_')}


class TimestampMixin:
    """Mixin for adding timestamp fields"""
    created_at: datetime
    updated_at: Optional[datetime] = None