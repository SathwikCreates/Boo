from pydantic import BaseModel, Field
from typing import Optional, Any, List


class PreferenceUpdate(BaseModel):
    """Schema for updating a preference"""
    key: str = Field(..., description="Preference key")
    value: Any = Field(..., description="Preference value")
    value_type: str = Field(default="string", description="Value type (string, int, float, bool, json)")
    description: Optional[str] = Field(None, description="Preference description")
    
    class Config:
        json_schema_extra = {
            "example": {
                "key": "hotkey",
                "value": "F9",
                "value_type": "string",
                "description": "Global hotkey for voice recording"
            }
        }


class PreferenceResponse(BaseModel):
    """Schema for preference response"""
    id: int
    key: str
    value: str
    value_type: str
    description: Optional[str] = None
    typed_value: Any = Field(..., description="Value with proper type conversion")
    
    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": 1,
                "key": "hotkey",
                "value": "F8",
                "value_type": "string",
                "description": "Global hotkey for voice recording",
                "typed_value": "F8"
            }
        }


class PreferencesListResponse(BaseModel):
    """Schema for preferences list response"""
    preferences: List[PreferenceResponse]


class PreferencesBulkUpdate(BaseModel):
    """Schema for bulk preference updates"""
    preferences: List[PreferenceUpdate]
    
    class Config:
        json_schema_extra = {
            "example": {
                "preferences": [
                    {
                        "key": "hotkey",
                        "value": "F9",
                        "value_type": "string"
                    },
                    {
                        "key": "ollama_port",
                        "value": 11434,
                        "value_type": "int"
                    }
                ]
            }
        }