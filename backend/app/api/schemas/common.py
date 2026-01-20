from pydantic import BaseModel
from typing import Optional, Any, TypeVar, Generic

T = TypeVar('T')


class SuccessResponse(BaseModel, Generic[T]):
    """Standard success response"""
    success: bool = True
    message: str = "Operation completed successfully"
    data: Optional[T] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "message": "Entry created successfully",
                "data": {"id": 1}
            }
        }


class ErrorResponse(BaseModel):
    """Standard error response"""
    success: bool = False
    message: str
    error_code: Optional[str] = None
    details: Optional[dict] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": False,
                "message": "Entry not found",
                "error_code": "ENTRY_NOT_FOUND",
                "details": {"entry_id": 123}
            }
        }


class HealthResponse(BaseModel):
    """Health check response"""
    status: str = "healthy"
    service: str = "boo-journal-api"
    version: str = "0.1.0"
    timestamp: str
    database: str = "connected"
    
    class Config:
        json_schema_extra = {
            "example": {
                "status": "healthy",
                "service": "boo-journal-api",
                "version": "0.1.0",
                "timestamp": "2024-01-01T12:00:00Z",
                "database": "connected"
            }
        }


class PaginationParams(BaseModel):
    """Common pagination parameters"""
    page: int = 1
    page_size: int = 20
    
    class Config:
        json_schema_extra = {
            "example": {
                "page": 1,
                "page_size": 20
            }
        }