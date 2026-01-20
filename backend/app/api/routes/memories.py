"""
Memory management API routes
"""
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query, Body
from pydantic import BaseModel, Field
import logging

from app.services.memory_service import MemoryService
from app.services.background_tasks import background_manager, get_background_task_status
from app.db.database import get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/memories", tags=["memories"])

# Initialize memory service
memory_service = MemoryService()


class MemoryRatingRequest(BaseModel):
    """Request model for rating a memory"""
    memory_id: int = Field(..., description="ID of the memory to rate")
    adjustment: int = Field(..., ge=-3, le=3, description="Rating adjustment from -3 to +3")


class MemoryResponse(BaseModel):
    """Response model for memory data"""
    id: int
    content: str
    memory_type: str
    base_importance_score: float
    llm_importance_score: Optional[float]
    user_score_adjustment: float
    final_importance_score: float
    user_rated: int
    score_source: str
    effective_score: Optional[dict] = None
    created_at: str
    last_accessed_at: Optional[str]
    access_count: int


class MemoryStatsResponse(BaseModel):
    """Response model for memory statistics"""
    total_memories: int
    rated_memories: int
    unrated_memories: int
    llm_processed: int
    pending_deletion: int
    archived: int
    average_score: float


@router.get("/", response_model=dict)
async def get_paginated_memories(
    page: int = Query(1, ge=1, description="Page number (1-based)"),
    limit: int = Query(6, ge=1, le=50, description="Number of memories per page"),
    filter: str = Query("all", description="Filter type: all, rated, unrated")
):
    """
    Get paginated memories with filtering support.
    Returns memories with pagination metadata.
    """
    try:
        db = get_db()
        # Build query based on filter
        base_query = "FROM agent_memories WHERE (is_active = 1 OR archived = 1)"
        
        if filter == "rated":
            base_query += " AND user_rated = 1"
        elif filter == "unrated":
            base_query += " AND user_rated = 0"
        
        # Get total count
        count_query = f"SELECT COUNT(*) as total {base_query}"
        count_result = await db.fetch_one(count_query)
        total = count_result['total'] if count_result else 0
        
        # Calculate pagination
        total_pages = max(1, (total + limit - 1) // limit)  # Ceiling division
        page = min(page, total_pages)  # Ensure page doesn't exceed total
        offset = (page - 1) * limit
        
        # Get paginated memories
        data_query = f"""
            SELECT * {base_query}
            ORDER BY 
                CASE WHEN user_rated = 0 AND llm_processed = 1 THEN 0 ELSE 1 END,
                created_at DESC
            LIMIT ? OFFSET ?
        """
        
        memories = await db.fetch_all(data_query, (limit, offset))
        
        # Calculate effective scores for each memory
        result_memories = []
        for memory in memories:
            memory_dict = dict(memory)
            memory_dict['effective_score'] = memory_service.calculate_effective_score(memory_dict)
            result_memories.append(memory_dict)
        
        return {
            "memories": result_memories,
            "total": total,
            "page": page,
            "totalPages": total_pages,
            "hasNext": page < total_pages,
            "hasPrev": page > 1,
            "filter": filter
        }
    except Exception as e:
        logger.error(f"Failed to get paginated memories: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/unrated", response_model=List[dict])
async def get_unrated_memories(
    limit: int = Query(10, ge=1, le=50, description="Number of memories to retrieve")
):
    """
    Get unrated memories for user review.
    Shows LLM-processed memories first, then newest.
    """
    try:
        db = get_db()
        memories = await memory_service.get_unrated_memories(limit)
        return memories
    except Exception as e:
        logger.error(f"Failed to get unrated memories: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/rate")
async def rate_memory(request: MemoryRatingRequest):
    """
    Apply user rating to a memory.
    Adjustment range: -3 (irrelevant) to +3 (very important)
    """
    try:
        db = get_db()
        success = await memory_service.rate_memory(
            memory_id=request.memory_id,
            adjustment=request.adjustment
        )
        
        if not success:
            raise HTTPException(status_code=404, detail="Memory not found")
        
        return {"success": True, "message": "Memory rated successfully"}
    except Exception as e:
        logger.error(f"Failed to rate memory: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats", response_model=MemoryStatsResponse)
async def get_memory_statistics():
    """
    Get statistics about stored memories.
    """
    try:
        db = get_db()
        # Get various statistics
        stats_result = await db.fetch_one("""
            SELECT 
                COUNT(*) as total_memories,
                SUM(CASE WHEN user_rated = 1 THEN 1 ELSE 0 END) as rated_memories,
                SUM(CASE WHEN user_rated = 0 THEN 1 ELSE 0 END) as unrated_memories,
                SUM(CASE WHEN llm_processed = 1 THEN 1 ELSE 0 END) as llm_processed,
                SUM(CASE WHEN marked_for_deletion = 1 THEN 1 ELSE 0 END) as pending_deletion,
                SUM(CASE WHEN archived = 1 THEN 1 ELSE 0 END) as archived,
                AVG(final_importance_score) as average_score
            FROM agent_memories
            WHERE is_active = 1 OR archived = 1
        """)
        
        return MemoryStatsResponse(
            total_memories=stats_result['total_memories'] or 0,
            rated_memories=stats_result['rated_memories'] or 0,
            unrated_memories=stats_result['unrated_memories'] or 0,
            llm_processed=stats_result['llm_processed'] or 0,
            pending_deletion=stats_result['pending_deletion'] or 0,
            archived=stats_result['archived'] or 0,
            average_score=round(stats_result['average_score'] or 0, 2)
        )
    except Exception as e:
        logger.error(f"Failed to get memory statistics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/search")
async def search_memories(
    query: str = Query(..., description="Search query"),
    memory_type: Optional[str] = Query(None, description="Filter by memory type"),
    limit: int = Query(10, ge=1, le=50, description="Number of results")
):
    """
    Search memories with optional type filter.
    """
    try:
        db = get_db()
        # Build query
        sql_query = """
            SELECT * FROM agent_memories 
            WHERE is_active = 1
            AND content LIKE ?
        """
        params = [f"%{query}%"]
        
        if memory_type:
            sql_query += " AND memory_type = ?"
            params.append(memory_type)
        
        sql_query += " ORDER BY final_importance_score DESC LIMIT ?"
        params.append(limit)
        
        memories = await db.fetch_all(sql_query, tuple(params))
        
        # Calculate effective scores
        result = []
        for memory in memories:
            memory_dict = dict(memory)
            memory_dict['effective_score'] = memory_service.calculate_effective_score(memory_dict)
            result.append(memory_dict)
        
        return result
    except Exception as e:
        logger.error(f"Failed to search memories: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/process-llm-batch")
async def trigger_llm_processing(
    batch_size: int = Body(5, ge=1, le=20, description="Number of memories to process")
):
    """
    Trigger batch processing of memories with LLM.
    This should typically be called by a background scheduler.
    """
    try:
        db = get_db()
        processed_count = await memory_service.process_memories_with_llm_batch(batch_size)
        return {
            "success": True,
            "processed_count": processed_count,
            "message": f"Processed {processed_count} memories with LLM"
        }
    except Exception as e:
        logger.error(f"Failed to process memories with LLM: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/rescue/{memory_id}")
async def rescue_memory(memory_id: int):
    """
    Rescue a memory from deletion queue.
    """
    try:
        db = get_db()
        success = await memory_service.rescue_memory(memory_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="Memory not found")
        
        return {"success": True, "message": "Memory rescued from deletion"}
    except Exception as e:
        logger.error(f"Failed to rescue memory: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/pending-deletion")
async def get_pending_deletion_memories():
    """
    Get memories marked for deletion.
    """
    try:
        db = get_db()
        memories = await db.fetch_all("""
            SELECT id, content, deletion_reason, marked_for_deletion_at,
                   DATE(marked_for_deletion_at, '+14 days') as scheduled_deletion_date
            FROM agent_memories 
            WHERE marked_for_deletion = 1
            AND archived = 0
            ORDER BY marked_for_deletion_at DESC
        """)
        
        return memories
    except Exception as e:
        logger.error(f"Failed to get pending deletion memories: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/maintenance/mark-deletion")
async def mark_memories_for_deletion():
    """
    Mark memories for deletion based on criteria.
    Should be run monthly (1st of month).
    """
    try:
        db = get_db()
        marked_ids = await memory_service.mark_memories_for_deletion()
        return {
            "success": True,
            "marked_count": len(marked_ids),
            "marked_ids": marked_ids,
            "message": f"Marked {len(marked_ids)} memories for deletion"
        }
    except Exception as e:
        logger.error(f"Failed to mark memories for deletion: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/maintenance/archive")
async def archive_marked_memories():
    """
    Archive memories marked for deletion (soft delete).
    Should be run 2 weeks after marking.
    """
    try:
        db = get_db()
        archived_count = await memory_service.archive_marked_memories()
        return {
            "success": True,
            "archived_count": archived_count,
            "message": f"Archived {archived_count} memories"
        }
    except Exception as e:
        logger.error(f"Failed to archive memories: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/maintenance/cleanup")
async def cleanup_archived_memories():
    """
    Permanently delete long-archived memories.
    Should be run monthly.
    """
    try:
        db = get_db()
        deleted_count = await memory_service.permanently_delete_archived()
        return {
            "success": True,
            "deleted_count": deleted_count,
            "message": f"Permanently deleted {deleted_count} memories"
        }
    except Exception as e:
        logger.error(f"Failed to cleanup memories: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/background-tasks/status")
async def get_background_tasks_status():
    """
    Get status of background processing tasks.
    """
    try:
        db = get_db()
        status = await get_background_task_status()
        return status
    except Exception as e:
        logger.error(f"Failed to get background task status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/background-tasks/trigger-llm")
async def trigger_background_llm_processing(
    batch_size: int = Body(10, ge=1, le=50, description="Number of memories to process")
):
    """
    Manually trigger LLM processing of memories.
    """
    try:
        db = get_db()
        processed_count = await background_manager.trigger_llm_processing(batch_size)
        return {
            "success": True,
            "processed_count": processed_count,
            "message": f"Triggered LLM processing for {processed_count} memories"
        }
    except Exception as e:
        logger.error(f"Failed to trigger LLM processing: {e}")
        raise HTTPException(status_code=500, detail=str(e))