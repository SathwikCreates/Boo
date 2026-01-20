from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
import logging

logger = logging.getLogger(__name__)


async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions with structured error response"""
    logger.warning(f"HTTP {exc.status_code}: {exc.detail} - {request.url}")
    
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "message": exc.detail,
            "status_code": exc.status_code,
            "path": str(request.url.path)
        }
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle validation errors with detailed error information"""
    logger.warning(f"Validation error: {exc.errors()} - {request.url}")
    
    return JSONResponse(
        status_code=422,
        content={
            "success": False,
            "message": "Validation error",
            "status_code": 422,
            "errors": exc.errors(),
            "path": str(request.url.path)
        }
    )


async def general_exception_handler(request: Request, exc: Exception):
    """Handle unexpected exceptions"""
    logger.error(f"Unexpected error: {str(exc)} - {request.url}", exc_info=True)
    
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "message": "Internal server error",
            "status_code": 500,
            "path": str(request.url.path)
        }
    )


# Custom exception classes
class EntryNotFoundError(HTTPException):
    def __init__(self, entry_id: int):
        super().__init__(
            status_code=404,
            detail=f"Entry with ID {entry_id} not found"
        )


class PreferenceNotFoundError(HTTPException):
    def __init__(self, key: str):
        super().__init__(
            status_code=404,
            detail=f"Preference with key '{key}' not found"
        )


class DatabaseError(HTTPException):
    def __init__(self, message: str):
        super().__init__(
            status_code=500,
            detail=f"Database error: {message}"
        )