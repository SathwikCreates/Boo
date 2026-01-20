"""
Drafts API endpoints for auto-save functionality
"""

from fastapi import APIRouter, HTTPException
from typing import Optional, Dict, Any
from pydantic import BaseModel
from datetime import datetime

from app.api.schemas import SuccessResponse, ErrorResponse
from app.db.repositories.draft_repository import DraftRepository
from app.models.draft import Draft

router = APIRouter(prefix="/drafts", tags=["drafts"])


class DraftSaveRequest(BaseModel):
    content: str
    timestamp: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class DraftResponse(BaseModel):
    id: int
    content: str
    metadata: Optional[Dict[str, Any]] = None
    created_at: str
    updated_at: Optional[str] = None


@router.post("/save", response_model=SuccessResponse)
async def save_draft(request: DraftSaveRequest):
    """Save or update a draft for auto-save functionality"""
    try:
        if not request.content.strip():
            raise HTTPException(
                status_code=400,
                detail="Draft content cannot be empty"
            )
        
        # Use the smart save_or_update method that handles recent drafts
        draft = await DraftRepository.save_or_update(
            content=request.content.strip(),
            metadata=request.metadata
        )
        
        return SuccessResponse(
            message="Draft saved successfully",
            data={
                "id": draft.id,
                "content": draft.content,
                "created_at": draft.created_at.isoformat() if draft.created_at else None,
                "updated_at": draft.updated_at.isoformat() if draft.updated_at else None,
                "is_update": draft.updated_at is not None
            }
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to save draft: {str(e)}"
        )


@router.get("/latest", response_model=DraftResponse)
async def get_latest_draft():
    """Get the most recent draft"""
    try:
        draft = await DraftRepository.get_latest()
        
        if not draft:
            raise HTTPException(
                status_code=404,
                detail="No drafts found"
            )
        
        return DraftResponse(
            id=draft.id,
            content=draft.content,
            metadata=draft.metadata,
            created_at=draft.created_at.isoformat() if draft.created_at else "",
            updated_at=draft.updated_at.isoformat() if draft.updated_at else None
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get latest draft: {str(e)}"
        )


@router.get("/{draft_id}", response_model=DraftResponse)
async def get_draft(draft_id: int):
    """Get a specific draft by ID"""
    try:
        draft = await DraftRepository.get_by_id(draft_id)
        
        if not draft:
            raise HTTPException(
                status_code=404,
                detail="Draft not found"
            )
        
        return DraftResponse(
            id=draft.id,
            content=draft.content,
            metadata=draft.metadata,
            created_at=draft.created_at.isoformat() if draft.created_at else "",
            updated_at=draft.updated_at.isoformat() if draft.updated_at else None
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get draft: {str(e)}"
        )


@router.delete("/{draft_id}", response_model=SuccessResponse)
async def delete_draft(draft_id: int):
    """Delete a specific draft"""
    try:
        # Check if draft exists
        draft = await DraftRepository.get_by_id(draft_id)
        if not draft:
            raise HTTPException(
                status_code=404,
                detail="Draft not found"
            )
        
        # Delete the draft
        await DraftRepository.delete(draft_id)
        
        return SuccessResponse(
            message="Draft deleted successfully",
            data={"id": draft_id}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete draft: {str(e)}"
        )


@router.delete("/cleanup/old", response_model=SuccessResponse)
async def cleanup_old_drafts(days: int = 7):
    """Delete drafts older than specified days (default: 7 days)"""
    try:
        if days < 1:
            raise HTTPException(
                status_code=400,
                detail="Days must be at least 1"
            )
        
        deleted_count = await DraftRepository.delete_old_drafts(days)
        
        return SuccessResponse(
            message=f"Cleanup completed - {deleted_count} old drafts deleted",
            data={
                "deleted_count": deleted_count,
                "days_threshold": days
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to cleanup old drafts: {str(e)}"
        )


@router.get("/", response_model=SuccessResponse)
async def get_drafts_status():
    """Get drafts system status and recent draft info"""
    try:
        latest_draft = await DraftRepository.get_latest()
        
        return SuccessResponse(
            message="Drafts system is operational",
            data={
                "has_recent_draft": latest_draft is not None,
                "latest_draft": {
                    "id": latest_draft.id,
                    "content_preview": latest_draft.content[:100] + "..." if len(latest_draft.content) > 100 else latest_draft.content,
                    "created_at": latest_draft.created_at.isoformat() if latest_draft.created_at else None,
                    "updated_at": latest_draft.updated_at.isoformat() if latest_draft.updated_at else None
                } if latest_draft else None
            }
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get drafts status: {str(e)}"
        )