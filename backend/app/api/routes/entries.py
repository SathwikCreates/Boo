from fastapi import APIRouter, HTTPException, Query, Path, BackgroundTasks, Depends
from typing import Optional, List, Dict, Any
from datetime import datetime
import logging

from app.api.schemas import (
    EntryCreate,
    EntryUpdate,
    EntryResponse,
    EntryListResponse,
    EntrySearchRequest,
    MoodAnalysisRequest,
    MoodAnalysisResponse,
    SuccessResponse,
    ErrorResponse
)
from app.db import EntryRepository
from app.models.entry import Entry
from app.schemas.entry import ProcessingMode, EntryProcessRequest, EntryCreateAndProcessRequest, EntryProcessOnlyRequest
# Note: Using our newer schema definitions that include ProcessingMode enum
from app.services.entry_processing import get_entry_processing_service
from app.services.processing_queue import get_processing_queue
from app.services.embedding_service import get_embedding_service
from app.services.mood_analysis import get_mood_analysis_service
from app.services.diary_chat_service import invalidate_diary_cache
from app.services.smart_tagging_service import get_smart_tagging_service
from app.auth.dependencies import get_current_user
from app.db.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/entries", tags=["entries"])


async def _generate_embedding_for_entry(entry_id: int, text: str = None):
    """Background task to generate embedding for an entry"""
    try:
        logger.info(f"BACKGROUND TASK STARTED: Generating embedding for entry {entry_id}")
        logger.info(f"Generating embedding for entry {entry_id}")
        embedding_service = get_embedding_service()
        
        # If no text provided, get the entry and determine best text to use
        if text is None:
            entry = await EntryRepository.get_by_id(entry_id)
            if not entry:
                logger.error(f"Entry {entry_id} not found for embedding generation")
                return
            text = _select_best_text_for_embedding(entry)
        
        if not text or not text.strip():
            logger.warning(f"No suitable text found for embedding generation for entry {entry_id}")
            return
        
        # Generate embedding with BGE document formatting
        embedding = await embedding_service.generate_embedding(text.strip(), normalize=True, is_query=False)
        
        # Update entry with embedding
        await EntryRepository.update_embedding(entry_id, embedding)
        
        logger.info(f"Successfully generated embedding for entry {entry_id} using text: '{text[:50]}...'")
        
        # CRITICAL: Invalidate cache AFTER embedding is stored in database
        invalidate_diary_cache()
        logger.info(f"CACHE INVALIDATED for entry {entry_id} AFTER embedding stored")
        
    except Exception as e:
        logger.error(f"Failed to generate embedding for entry {entry_id}: {e}")


async def _extract_entry_memories(entry_id: int):
    """Background task to extract memories from an entry using LLM"""
    try:
        db = get_db()
        from app.services.memory_service import MemoryService
        
        logger.info(f"Starting LLM memory extraction for entry {entry_id}")
        
        # Get the entry
        entry = await EntryRepository.get_by_id(entry_id)
        if not entry:
            logger.error(f"Entry {entry_id} not found for memory extraction")
            return
        
        # Use enhanced text for memory extraction (better quality than raw)
        text = entry.enhanced_text or entry.raw_text
        if not text or not text.strip():
            logger.warning(f"No suitable text found for memory extraction for entry {entry_id}")
            return
        
        # Initialize memory service
        memory_service = MemoryService()
        
        # Extract memories using LLM
        memories = await memory_service.extract_memories_with_llm(
            text=text,
            source_id=entry_id,
            source_type='entry'
            # model, temperature, num_ctx will be loaded from preferences
        )
        
        # Store each memory
        stored_count = 0
        for memory in memories:
            try:
                await memory_service.store_memory(memory)
                stored_count += 1
            except Exception as e:
                logger.error(f"Failed to store memory: {e}")
        
        logger.info(f"LLM extracted and stored {stored_count} memories from entry {entry_id}")
        
        # Mark entry as processed for memory extraction
        await db.execute("""
            UPDATE entries 
            SET memory_extracted = 1,
                memory_extracted_llm = 1,
                memory_extracted_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (entry_id,))
        await db.commit()
        logger.info(f"Marked entry {entry_id} as memory_extracted")
        
        # Fallback to rule-based if no memories extracted
        if stored_count == 0:
            logger.info("No memories from LLM, trying rule-based extraction as fallback")
            fallback_count = await memory_service.process_entry_for_memories(entry_id, text)
            logger.info(f"Rule-based fallback extracted {fallback_count} memories")
        
    except Exception as e:
        logger.error(f"LLM memory extraction failed for entry {entry_id}: {e}")
        # Try rule-based as final fallback
        try:
            from app.services.memory_service import MemoryService
            memory_service = MemoryService()
            entry = await EntryRepository.get_by_id(entry_id)
            if entry:
                text = entry.enhanced_text or entry.raw_text
                if text:
                    fallback_count = await memory_service.process_entry_for_memories(entry_id, text)
                    logger.info(f"Rule-based fallback after error extracted {fallback_count} memories")
        except Exception as fallback_error:
            logger.error(f"Even rule-based fallback failed: {fallback_error}")


def _select_best_text_for_embedding(entry) -> str:
    """
    Select the best text content for embedding generation.
    ALWAYS use raw_text for reliable semantic search - no LLM processing can alter the original content
    """
    # ALWAYS use raw text - it's the user's original words and most reliable for search
    if entry.raw_text and entry.raw_text.strip():
        logger.debug(f"Using raw_text for embedding (entry {entry.id})")
        return entry.raw_text.strip()
    
    # No raw text found (should not happen)
    logger.warning(f"No raw text found for embedding in entry {entry.id}")
    return ""


@router.post("/", response_model=EntryResponse, status_code=201)
async def create_entry(entry_data: EntryCreate, background_tasks: BackgroundTasks):
    """Create a new journal entry"""
    try:
        # Create entry model with all provided data
        # Handle mode as string (from API schema) 
        mode_str = entry_data.mode if isinstance(entry_data.mode, str) else entry_data.mode.value
        
        # Generate smart tags for the entry
        smart_tagging_service = get_smart_tagging_service()
        smart_tags_result = smart_tagging_service.generate_smart_tags(entry_data.raw_text)
        
        # Extract just the tags array for the smart_tags column
        smart_tags_list = smart_tags_result["tags"]
        
        entry = Entry(
            raw_text=entry_data.raw_text,
            enhanced_text=entry_data.enhanced_text,
            structured_summary=entry_data.structured_summary,
            mode=mode_str,
            timestamp=entry_data.custom_timestamp if entry_data.custom_timestamp else datetime.now(),
            word_count=len(entry_data.raw_text.split()),
            processing_metadata=entry_data.processing_metadata,  # Keep original processing metadata
            smart_tags=smart_tags_list  # Store smart tags in dedicated column
        )
        
        # Save to database first
        created_entry = await EntryRepository.create(entry)
        
        # Generate embedding in background - will use best available text
        background_tasks.add_task(
            _generate_embedding_for_entry,
            created_entry.id
        )
        
        # Extract memories in background - will use enhanced text if available
        background_tasks.add_task(
            _extract_entry_memories,
            created_entry.id
        )
        
        logger.info(f"Queued embedding generation and memory extraction for entry {created_entry.id}")
        
        # Convert to response format
        return EntryResponse(
            id=created_entry.id,
            raw_text=created_entry.raw_text,
            enhanced_text=created_entry.enhanced_text,
            structured_summary=created_entry.structured_summary,
            mode=created_entry.mode,
            embeddings=created_entry.embeddings,
            timestamp=created_entry.timestamp,
            mood_tags=created_entry.mood_tags,
            word_count=created_entry.word_count,
            processing_metadata=created_entry.processing_metadata,
            smart_tags=created_entry.smart_tags
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create entry: {str(e)}")


@router.get("/", response_model=EntryListResponse)
async def list_entries(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    mode: Optional[str] = Query(None, description="Filter by processing mode")
):
    """List journal entries with pagination"""
    try:
        # Calculate offset
        offset = (page - 1) * page_size
        
        # Get entries
        entries = await EntryRepository.get_all(
            limit=page_size,
            offset=offset,
            mode=mode
        )
        
        # Get total count for pagination
        total = await EntryRepository.count()
        
        # Convert to response format
        entry_responses = [
            EntryResponse(
                id=entry.id,
                raw_text=entry.raw_text,
                enhanced_text=entry.enhanced_text,
                structured_summary=entry.structured_summary,
                mode=entry.mode,
                embeddings=entry.embeddings,
                timestamp=entry.timestamp,
                mood_tags=entry.mood_tags,
                word_count=entry.word_count,
                processing_metadata=entry.processing_metadata,
                smart_tags=entry.smart_tags
            )
            for entry in entries
        ]
        
        return EntryListResponse(
            entries=entry_responses,
            total=total,
            page=page,
            page_size=page_size,
            has_next=offset + page_size < total,
            has_prev=page > 1
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list entries: {str(e)}")


@router.get("/{entry_id}", response_model=EntryResponse)
async def get_entry(entry_id: int = Path(..., description="Entry ID")):
    """Get a specific journal entry by ID"""
    try:
        entry = await EntryRepository.get_by_id(entry_id)
        
        if not entry:
            raise HTTPException(status_code=404, detail="Entry not found")
        
        return EntryResponse(
            id=entry.id,
            raw_text=entry.raw_text,
            enhanced_text=entry.enhanced_text,
            structured_summary=entry.structured_summary,
            mode=entry.mode,
            embeddings=entry.embeddings,
            timestamp=entry.timestamp,
            mood_tags=entry.mood_tags,
            word_count=entry.word_count,
            processing_metadata=entry.processing_metadata,
            smart_tags=entry.smart_tags
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get entry: {str(e)}")


@router.put("/{entry_id}", response_model=EntryResponse)
async def update_entry(
    entry_id: int = Path(..., description="Entry ID"),
    entry_data: EntryUpdate = ...,
    background_tasks: BackgroundTasks = None
):
    """Update a journal entry"""
    try:
        # Get existing entry
        entry = await EntryRepository.get_by_id(entry_id)
        
        if not entry:
            raise HTTPException(status_code=404, detail="Entry not found")
        
        # Track if raw_text was updated (for embedding regeneration)
        text_updated = False
        
        # Update fields that were provided
        if entry_data.raw_text is not None:
            entry.raw_text = entry_data.raw_text
            entry.word_count = len(entry_data.raw_text.split())
            text_updated = True
        
        if entry_data.enhanced_text is not None:
            entry.enhanced_text = entry_data.enhanced_text
            
        if entry_data.structured_summary is not None:
            entry.structured_summary = entry_data.structured_summary
            
        if entry_data.mode is not None:
            entry.mode = entry_data.mode if isinstance(entry_data.mode, str) else entry_data.mode.value
            
        if entry_data.mood_tags is not None:
            entry.mood_tags = entry_data.mood_tags
        
        # Save updates
        updated_entry = await EntryRepository.update(entry)
        
        # Regenerate embedding if any text was updated and we have background tasks
        if (text_updated or 
            entry_data.enhanced_text is not None or 
            entry_data.structured_summary is not None) and background_tasks:
            # DON'T invalidate cache immediately - wait for embedding regeneration
            # invalidate_diary_cache()  # Moved to after embedding generation
            background_tasks.add_task(
                _generate_embedding_for_entry,
                updated_entry.id
            )
            logger.info(f"Queued embedding regeneration for updated entry {updated_entry.id}")
        else:
            # Only invalidate cache immediately if no embedding work is needed
            invalidate_diary_cache()
        
        return EntryResponse(
            id=updated_entry.id,
            raw_text=updated_entry.raw_text,
            enhanced_text=updated_entry.enhanced_text,
            structured_summary=updated_entry.structured_summary,
            mode=updated_entry.mode,
            embeddings=updated_entry.embeddings,
            timestamp=updated_entry.timestamp,
            mood_tags=updated_entry.mood_tags,
            word_count=updated_entry.word_count,
            processing_metadata=updated_entry.processing_metadata,
            smart_tags=updated_entry.smart_tags
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update entry: {str(e)}")


@router.delete("/{entry_id}", response_model=SuccessResponse)
async def delete_entry(entry_id: int = Path(..., description="Entry ID")):
    """Delete a journal entry"""
    try:
        # Check if entry exists
        entry = await EntryRepository.get_by_id(entry_id)
        
        if not entry:
            raise HTTPException(status_code=404, detail="Entry not found")
        
        # Delete entry
        await EntryRepository.delete(entry_id)
        
        return SuccessResponse(
            message="Entry deleted successfully",
            data={"id": entry_id}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete entry: {str(e)}")


@router.post("/search", response_model=List[EntryResponse])
async def search_entries(search_request: EntrySearchRequest):
    """Search journal entries by text content"""
    try:
        entries = await EntryRepository.search(
            query=search_request.query,
            limit=search_request.limit
        )
        
        return [
            EntryResponse(
                id=entry.id,
                raw_text=entry.raw_text,
                enhanced_text=entry.enhanced_text,
                structured_summary=entry.structured_summary,
                mode=entry.mode,
                embeddings=entry.embeddings,
                timestamp=entry.timestamp,
                mood_tags=entry.mood_tags,
                word_count=entry.word_count,
                processing_metadata=entry.processing_metadata,
                smart_tags=entry.smart_tags
            )
            for entry in entries
        ]
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to search entries: {str(e)}")


@router.post("/process/{entry_id}", response_model=dict)
async def process_entry(
    entry_id: int = Path(..., description="Entry ID"),
    process_request: EntryProcessRequest = ...
):
    """Queue an entry for processing with specified mode (enhanced or structured)"""
    try:
        # Get existing entry
        entry = await EntryRepository.get_by_id(entry_id)
        
        if not entry:
            raise HTTPException(status_code=404, detail="Entry not found")
        
        # Add to processing queue
        processing_queue = await get_processing_queue()
        job_id = await processing_queue.add_job(
            entry_id=entry_id,
            mode=process_request.mode,
            raw_text=entry.raw_text
        )
        
        return {
            "message": "Entry queued for processing",
            "job_id": job_id,
            "entry_id": entry_id,
            "mode": process_request.mode.value,
            "status": "pending"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to queue entry for processing: {str(e)}")


@router.post("/create-and-process", response_model=dict)
async def create_and_process_entry(
    request: EntryCreateAndProcessRequest,
    background_tasks: BackgroundTasks
):
    """Create a new entry and queue it for processing in specified modes"""
    try:
        # Generate smart tags for the entry
        smart_tagging_service = get_smart_tagging_service()
        smart_tags_result = smart_tagging_service.generate_smart_tags(request.raw_text)
        
        # Extract just the tags array for the smart_tags column
        smart_tags_list = smart_tags_result["tags"]
        
        # Create raw entry first - processing metadata will be added by processing pipeline
        entry = Entry(
            raw_text=request.raw_text,
            mode="raw",
            timestamp=datetime.now(),
            word_count=len(request.raw_text.split()),
            processing_metadata=None,  # Will be set by processing pipeline
            smart_tags=smart_tags_list  # Store smart tags in dedicated column
        )
        
        created_entry = await EntryRepository.create(entry)
        
        # Generate embedding in background - will use best available text
        background_tasks.add_task(
            _generate_embedding_for_entry,
            created_entry.id
        )
        
        # Extract memories in background - will use enhanced text if available
        background_tasks.add_task(
            _extract_entry_memories,
            created_entry.id
        )
        
        logger.info(f"Queued embedding generation and memory extraction for entry {created_entry.id}")
        
        # Queue for processing in each requested mode
        processing_queue = await get_processing_queue()
        job_ids = []
        
        for mode in request.modes:
            if mode != ProcessingMode.RAW:  # Skip raw mode
                job_id = await processing_queue.add_job(
                    entry_id=created_entry.id,
                    mode=mode,
                    raw_text=request.raw_text
                )
                job_ids.append({"mode": mode.value, "job_id": job_id})
        
        # Create a master job ID that combines all jobs for easier tracking
        master_job_id = f"master_{created_entry.id}_{datetime.now().timestamp()}"
        
        return {
            "message": "Entry created and queued for processing",
            "entry_id": created_entry.id,
            "job_id": master_job_id,  # Add this for frontend compatibility
            "jobs": job_ids,
            "raw_entry": {
                "id": created_entry.id,
                "raw_text": created_entry.raw_text,
                "timestamp": created_entry.timestamp,
                "word_count": created_entry.word_count
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create and process entry: {str(e)}")


@router.post("/process-only", response_model=dict)
async def process_text_only(request: EntryProcessOnlyRequest):
    """Process text without saving to database - for preview purposes"""
    try:
        # Get processing service
        processing_service = await get_entry_processing_service()
        
        results = {}
        
        # Process for each requested mode
        for mode in request.modes:
            if mode == ProcessingMode.RAW:
                # Raw mode just returns the original text
                results[mode.value] = {
                    "processed_text": request.raw_text,
                    "word_count": len(request.raw_text.split()),
                    "processing_metadata": {
                        "mode": mode.value,
                        "processing_time_ms": 0,
                        "model_used": None,
                        "timestamp": datetime.now().isoformat()
                    }
                }
            else:
                # Process with AI
                result = await processing_service.process_entry(
                    raw_text=request.raw_text,
                    mode=mode,
                    existing_entry=None
                )
                results[mode.value] = result
        
        return {
            "message": "Text processed successfully",
            "raw_text": request.raw_text,
            "results": results
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process text: {str(e)}")


@router.get("/processing/job/{job_id}", response_model=dict)
async def get_processing_job_status(job_id: str = Path(..., description="Job ID")):
    """Get the status of a processing job"""
    try:
        processing_queue = await get_processing_queue()
        
        # Handle master job IDs (format: master_{entry_id}_{timestamp})
        if job_id.startswith("master_"):
            parts = job_id.split("_")
            if len(parts) >= 3:
                entry_id = int(parts[1])
                
                # Get the entry to check current state
                entry = await EntryRepository.get_by_id(entry_id)
                if not entry:
                    raise HTTPException(status_code=404, detail="Entry not found")
                
                # Check if both enhanced and structured are complete
                has_enhanced = entry.enhanced_text is not None
                has_structured = entry.structured_summary is not None
                
                if has_enhanced and has_structured:
                    # Both processing modes complete
                    return {
                        "id": job_id,
                        "entry_id": entry_id,
                        "status": "completed",
                        "result": {
                            "entry_id": entry_id,
                            "enhanced": entry.enhanced_text,
                            "structured": entry.structured_summary
                        }
                    }
                else:
                    # Still processing
                    return {
                        "id": job_id,
                        "entry_id": entry_id,
                        "status": "processing",
                        "result": None
                    }
        
        # Handle regular job IDs
        job = processing_queue.get_job(job_id)
        
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        
        return job.to_dict()
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get job status: {str(e)}")


@router.get("/processing/queue/status", response_model=dict)
async def get_queue_status():
    """Get the status of the processing queue"""
    try:
        processing_queue = await get_processing_queue()
        return processing_queue.get_queue_status()
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get queue status: {str(e)}")


@router.get("/stats/count", response_model=dict)
async def get_entry_count():
    """Get total count of entries"""
    try:
        count = await EntryRepository.count()
        return {"total_entries": count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get entry count: {str(e)}")


@router.get("/stats/daily-streak", response_model=dict)
async def get_daily_streak():
    """Calculate the current daily streak of consecutive days with entries"""
    try:
        from datetime import datetime, timedelta
        
        # Get all entries ordered by date descending (no pagination limit)
        all_entries = await EntryRepository.get_all_for_streak()
        
        if not all_entries:
            return {"streak": 0, "last_entry_date": None}
        
        # Sort entries by date descending
        sorted_entries = sorted(all_entries, key=lambda e: e.timestamp, reverse=True)
        
        # Get unique dates with entries
        entry_dates = set()
        for entry in sorted_entries:
            entry_date = entry.timestamp.date()
            entry_dates.add(entry_date)
        
        # Calculate streak
        streak = 0
        today = datetime.now().date()
        
        # Check if there's an entry today
        if today in entry_dates:
            streak = 1
            current_date = today
            
            # Count consecutive days going backwards
            for i in range(1, 365):  # Max 365 day streak
                check_date = current_date - timedelta(days=1)
                if check_date in entry_dates:
                    streak += 1
                    current_date = check_date
                else:
                    break
        else:
            # Check if there's an entry yesterday (streak continues from yesterday)
            yesterday = today - timedelta(days=1)
            if yesterday in entry_dates:
                streak = 1
                current_date = yesterday
                
                # Count consecutive days going backwards from yesterday
                for i in range(1, 365):
                    check_date = current_date - timedelta(days=1)
                    if check_date in entry_dates:
                        streak += 1
                        current_date = check_date
                    else:
                        break
        
        last_entry_date = sorted_entries[0].timestamp.isoformat() if sorted_entries else None
        
        return {
            "streak": streak,
            "last_entry_date": last_entry_date,
            "total_entries": len(all_entries),
            "unique_days": len(entry_dates)
        }
        
    except Exception as e:
        logger.error(f"Failed to calculate daily streak: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to calculate daily streak: {str(e)}")


@router.post("/analyze-mood", response_model=SuccessResponse[MoodAnalysisResponse])
async def analyze_mood(request: MoodAnalysisRequest):
    """Analyze the mood/emotions in journal text"""
    try:
        mood_service = await get_mood_analysis_service()
        mood_tags = await mood_service.analyze_mood(request.text)
        
        return SuccessResponse(
            message=f"Mood analysis complete, found {len(mood_tags)} moods",
            data=MoodAnalysisResponse(mood_tags=mood_tags)
        )
        
    except Exception as e:
        logger.error(f"Failed to analyze mood: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to analyze mood: {str(e)}")


@router.post("/{entry_id}/analyze-mood", response_model=SuccessResponse)
async def analyze_entry_mood(entry_id: int, background_tasks: BackgroundTasks):
    """Analyze mood for a specific entry and update the database"""
    try:
        # Get the entry
        entry = await EntryRepository.get_by_id(entry_id)
        if not entry:
            raise HTTPException(status_code=404, detail="Entry not found")
        
        # Use enhanced text if available, otherwise fall back to raw text
        text_to_analyze = entry.enhanced_text or entry.raw_text
        if not text_to_analyze:
            raise HTTPException(status_code=400, detail="Entry has no text to analyze")
        
        # Add mood analysis as background task
        background_tasks.add_task(_analyze_and_update_entry_mood, entry_id, text_to_analyze)
        
        return SuccessResponse(
            message="Mood analysis started for entry",
            data={"entry_id": entry_id, "status": "processing"}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to start mood analysis for entry {entry_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to start mood analysis: {str(e)}")


async def _analyze_and_update_entry_mood(entry_id: int, text: str):
    """Background task to analyze mood and update entry"""
    try:
        mood_service = await get_mood_analysis_service()
        mood_tags = await mood_service.analyze_mood(text)
        
        if mood_tags:
            # Update the entry with extracted moods
            entry = await EntryRepository.get_by_id(entry_id)
            if entry:
                entry.mood_tags = mood_tags
                await EntryRepository.update(entry)
                logger.info(f"Updated entry {entry_id} with moods: {mood_tags}")
        
    except Exception as e:
        logger.error(f"Failed to analyze and update mood for entry {entry_id}: {str(e)}")


@router.post("/debug/clear-cache", response_model=dict)
async def debug_clear_cache():
    """Debug endpoint to manually clear diary caches"""
    try:
        invalidate_diary_cache()
        return {
            "success": True,
            "message": "Diary caches manually cleared",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to clear cache: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to clear cache: {str(e)}")

@router.get("/debug/recent-timestamps", response_model=dict)
async def debug_recent_timestamps():
    """Debug endpoint to check recent entry timestamps"""
    try:
        entries = await EntryRepository.get_entries_with_embeddings(limit=10)
        
        timestamp_info = []
        for entry in entries:
            timestamp_info.append({
                "id": entry.id,
                "timestamp": entry.timestamp.isoformat(),
                "has_embeddings": bool(entry.embeddings and len(entry.embeddings) > 0),
                "raw_text_preview": entry.raw_text[:50] + "..." if entry.raw_text else "No text"
            })
        
        return {
            "success": True,
            "entries": timestamp_info,
            "count": len(timestamp_info)
        }
    except Exception as e:
        logger.error(f"Failed to get timestamp info: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get timestamp info: {str(e)}")