from fastapi import APIRouter, HTTPException
from datetime import datetime

from app.api.schemas import HealthResponse, SuccessResponse
from app.db.database import get_db
from app.core.config import settings

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    try:
        db = get_db()
        # Test database connection
        await db.fetch_one("SELECT 1")
        database_status = "connected"
    except Exception:
        database_status = "disconnected"
    
    return HealthResponse(
        status="healthy" if database_status == "connected" else "unhealthy",
        service="boo-journal-api",
        version=settings.VERSION,
        timestamp=datetime.now().isoformat(),
        database=database_status
    )


@router.get("/database", response_model=SuccessResponse)
async def database_health():
    """Detailed database health check"""
    try:
        db = get_db()
        # Test basic query
        result = await db.fetch_one("SELECT COUNT(*) as count FROM entries")
        entry_count = result["count"] if result else 0
        
        # Test preferences
        prefs_result = await db.fetch_one("SELECT COUNT(*) as count FROM preferences")
        prefs_count = prefs_result["count"] if prefs_result else 0
        
        return SuccessResponse(
            message="Database is healthy",
            data={
                "status": "connected",
                "entry_count": entry_count,
                "preferences_count": prefs_count,
                "database_path": settings.DATABASE_URL
            }
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Database health check failed: {str(e)}"
        )


@router.get("/version", response_model=dict)
async def get_version():
    """Get API version information"""
    return {
        "service": "boo-journal-api",
        "version": settings.VERSION,
        "app_name": settings.APP_NAME,
        "debug": settings.DEBUG
    }