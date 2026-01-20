"""
Diary Chat Service for Talk to Your Diary feature using LangChain.

This service handles:
- LangChain ChatOllama integration with tool calling
- Date-aware diary search tool execution  
- Conversation context management
- System date awareness for the LLM
- Direct database queries for real-time accuracy
"""

import asyncio
import json
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta, date
import re
from contextvars import ContextVar

from langchain_ollama import ChatOllama
from app.db.database import get_db
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage

from app.db.repositories.entry_repository import EntryRepository
from app.db.repositories.preferences_repository import PreferencesRepository
from app.services.embedding_service import get_embedding_service
from app.services.hybrid_search import HybridSearchService
from app.services.memory_service import MemoryService
from app.core.config import settings

logger = logging.getLogger(__name__)

# Context variable for passing FastAPI BackgroundTasks to tools
_background_tasks_ctx: ContextVar = ContextVar('background_tasks', default=None)


def strip_thinking_block(response_text: str) -> str:
    """Strip thinking blocks from LLM response to get clean text."""
    if not response_text:
        return response_text
    
    # Find the end of the thinking block
    think_end = response_text.find('</think>')
    if think_end != -1:
        # Return everything after </think> tag, stripped of leading whitespace
        clean_text = response_text[think_end + len('</think>'):].strip()
        return clean_text
    
    # If no thinking block found, return original text
    return response_text



@tool
async def search_diary_entries(query: str, limit: int = 50) -> Dict[str, Any]:
    """Search user's diary entries by content using semantic search.
    
    Use this tool when the user asks about:
    - Specific topics: "hiking", "work", "friends", "family", "vacation"
    - Emotions or feelings: "happy", "sad", "anxious", "excited"
    - Activities: "meeting", "dinner", "exercise", "movie"
    - People mentioned: "mom", "John", "boss", "girlfriend"
    - Any content-based query without specific dates
    
    IMPORTANT: Use this tool for ALL non-date queries. Search broadly to find context.
    
    args:
        query: Text query to search for (1-1000 characters)
        limit: Maximum number of results to return (100)
        
    Returns:
        Search results with entries and metadata
    """
    try:
        logger.info(f"Searching diary entries: query='{query}', limit={limit}")
        
        # Validate inputs
        if not query or len(query.strip()) == 0:
            return {"success": False, "error": "Query cannot be empty"}
        
        if limit < 1 or limit > 100:
            limit = 50
            
        query = query.strip()[:1000]  # Limit query length
        
        # Generate query embedding
        embedding_service = get_embedding_service()
        query_embedding = await embedding_service.generate_embedding(
            text=query,
            normalize=True,
            is_query=True  # Mark as query for BGE formatting
        )
        
        # Get all entries with embeddings directly from database
        logger.info("Fetching entries with embeddings from database...")
        entries_with_embeddings = await EntryRepository.get_entries_with_embeddings(limit=None)
        
        if not entries_with_embeddings:
            return {
                "success": True,
                "results": [],
                "count": 0,
                "query": query,
                "message": "No entries with embeddings found"
            }
        
        # Extract embeddings and metadata
        candidate_embeddings = []
        entry_metadata = []
        
        for entry in entries_with_embeddings:
            if entry.embeddings and len(entry.embeddings) > 0:
                candidate_embeddings.append(entry.embeddings)
                entry_metadata.append(entry)
        
        if not candidate_embeddings:
            return {
                "success": True,
                "results": [],
                "count": 0,
                "query": query,
                "message": "No valid embeddings found"
            }
        
        # Perform similarity search with more candidates for hybrid reranking
        embedding_service = get_embedding_service()
        similar_indices = embedding_service.search_similar_embeddings(
            query_embedding=query_embedding,
            candidate_embeddings=candidate_embeddings,
            top_k=min(limit * 2, 200),  # Get 2x candidates for reranking
            similarity_threshold=0.3
        )
        
        # Prepare results for hybrid reranking (same as API endpoint)
        initial_results = []
        for index, similarity in similar_indices:
            entry = entry_metadata[index]
            entry_dict = {
                "id": entry.id,
                "raw_text": entry.raw_text,
                "enhanced_text": entry.enhanced_text,
                "structured_summary": entry.structured_summary,
                "mode": entry.mode,
                "timestamp": entry.timestamp,
                "mood_tags": entry.mood_tags,
                "word_count": entry.word_count
            }
            initial_results.append((index, similarity, entry_dict))
        
        # Apply hybrid reranking with keyword boosting
        reranked_results = HybridSearchService.rerank_search_results(
            results=initial_results,
            query=query,
            text_field="raw_text",
            exact_match_boost=0.2,  # Same as API endpoint
            partial_match_boost=0.1  # Same as API endpoint
        )
        
        # Format final results (take only requested limit)
        results = []
        for _, hybrid_score, entry_dict in reranked_results[:limit]:
            # Extract search context around matches
            content = HybridSearchService.extract_search_context(
                text=entry_dict["raw_text"] or "",
                query=query,
                context_length=200
            )
            
            # Include full entry data with mood_tags for LLM analysis
            result = {
                "entry_id": entry_dict["id"],
                "content": content,  # Use context-aware snippet
                "enhanced_text": entry_dict["enhanced_text"] or "",
                "structured_summary": entry_dict["structured_summary"] or "",
                "timestamp": entry_dict["timestamp"].isoformat(),
                "mood_tags": entry_dict["mood_tags"] or [],
                "mode": entry_dict["mode"],
                "similarity": hybrid_score,  # Use hybrid score
                "word_count": entry_dict["word_count"]
            }
            results.append(result)
        
        # Prepare response
        response = {
            "success": True,
            "results": results,
            "count": len(results),
            "query": query,
            "total_searchable_entries": len(candidate_embeddings)
        }
        
        return response
        
    except Exception as e:
        logger.error(f"Error in search_diary_entries: {e}")
        return {"success": False, "error": str(e)}


@tool
async def add_entry_to_diary(content: str, entry_type: str = "note") -> Dict[str, Any]:
    """CRITICAL: ONLY use this tool when user EXPLICITLY requests to save/add content to diary.
    
    MANDATORY CONDITIONS - User must use these EXACT phrases:
    - "Add this to my diary" / "Add to diary"
    - "Save this" / "Save this entry" 
    - "Add this to my journal" / "Add to journal"
    - "Add entry" / "Create entry"
    - "Save this as an entry"
    
    DO NOT USE if user is:
    - Just sharing information without asking to save
    - Asking questions about existing entries
    - Having casual conversation
    - Expressing thoughts without explicit save request
    
    WRONG: User says "I had a good day" -> DO NOT save automatically
    CORRECT: User says "Save this: I had a good day" -> Use this tool
    
    args:
        content: The text content to save as an entry
        entry_type: Type of entry - "note", "idea", "thought", "todo" (optional)
        
    Returns:
        Success status and created entry details
    """
    try:
        logger.info(f"Adding new entry via chat: type={entry_type}, length={len(content)}")
        
        if not content or len(content.strip()) == 0:
            return {"success": False, "error": "Content cannot be empty"}
        
        # Follow the same pipeline as regular entry creation
        from app.models.entry import Entry
        from datetime import datetime
        from app.services.smart_tagging_service import get_smart_tagging_service
        from app.services.processing_queue import get_processing_queue
        from app.schemas.entry import ProcessingMode
        import asyncio
        
        # Generate smart tags for the entry (same as regular entry creation)
        smart_tagging_service = get_smart_tagging_service()
        smart_tags_result = smart_tagging_service.generate_smart_tags(content.strip())
        
        # Extract just the tags array for the smart_tags column
        smart_tags_list = smart_tags_result["tags"]
        
        # Create raw entry first (same as regular pipeline)
        # processing_metadata should be None for raw entries - will be set during processing
        entry = Entry(
            raw_text=content.strip(),
            enhanced_text=None,
            structured_summary=None,
            mode="raw",
            timestamp=datetime.now(),
            word_count=len(content.split()),
            processing_metadata=None,  # Will be set by processing pipeline
            smart_tags=smart_tags_list  # Store smart tags in dedicated column
        )
        
        # Save to database
        created_entry = await EntryRepository.create(entry)
        
        # Generate embedding asynchronously (same as regular pipeline)
        async def _generate_embedding_background():
            try:
                embedding_service = get_embedding_service()
                embedding = await embedding_service.generate_embedding(
                    text=content.strip(),
                    normalize=True,
                    is_query=False
                )
                await EntryRepository.update_embedding(created_entry.id, embedding)
                logger.info(f"Generated embedding for chat entry {created_entry.id}")
            except Exception as e:
                logger.error(f"Failed to generate embedding for chat entry {created_entry.id}: {e}")
        
        # Queue for processing pipeline: enhanced and structured modes
        async def _queue_processing_pipeline():
            try:
                processing_queue = await get_processing_queue()
                
                # Queue for enhanced processing
                enhanced_job_id = await processing_queue.add_job(
                    entry_id=created_entry.id,
                    mode=ProcessingMode.ENHANCED,
                    raw_text=content.strip()
                )
                logger.info(f"Queued enhanced processing for chat entry {created_entry.id}: {enhanced_job_id}")
                
                # Queue for structured processing
                structured_job_id = await processing_queue.add_job(
                    entry_id=created_entry.id,
                    mode=ProcessingMode.STRUCTURED,
                    raw_text=content.strip()
                )
                logger.info(f"Queued structured processing for chat entry {created_entry.id}: {structured_job_id}")
                
            except Exception as e:
                logger.error(f"Failed to queue processing for chat entry {created_entry.id}: {e}")
        
        # This function is replaced by _trigger_mood_analysis_via_api below
        
        # Get background_tasks from context
        background_tasks = _background_tasks_ctx.get()
        
        if background_tasks:
            # Use FastAPI BackgroundTasks (same as regular entry creation)
            logger.info(f"Using FastAPI BackgroundTasks for chat entry {created_entry.id}")
            
            # Generate embedding in background (same as regular pipeline)
            background_tasks.add_task(
                _generate_embedding_for_entry_chat,
                created_entry.id,
                content.strip()
            )
            
            # Queue for processing pipeline: enhanced and structured modes
            background_tasks.add_task(
                _queue_processing_pipeline_chat,
                created_entry.id,
                content.strip()
            )
            
            # Register callback to trigger mood analysis when enhanced processing completes
            # (This matches NewEntryPage behavior: mood analysis AFTER enhanced text is available)
            background_tasks.add_task(
                _register_mood_analysis_callback,
                created_entry.id
            )
            
            # Send WebSocket notification about processing start
            background_tasks.add_task(
                _send_processing_notification,
                created_entry.id,
                "started"
            )
            
            logger.info(f"✅ Chat entry {created_entry.id} queued for background processing with FastAPI BackgroundTasks")
        else:
            # Fallback to asyncio.create_task (for backwards compatibility)
            logger.warning(f"No FastAPI BackgroundTasks available, falling back to asyncio.create_task for chat entry {created_entry.id}")
            
            async def _run_all_background_tasks():
                try:
                    await _generate_embedding_background()
                    await _queue_processing_pipeline()
                    await _register_mood_analysis_callback(created_entry.id)
                    logger.info(f"✅ Chat entry {created_entry.id} processed via asyncio fallback")
                except Exception as e:
                    logger.error(f"Background processing failed for chat entry {created_entry.id}: {e}")
            
            asyncio.create_task(_run_all_background_tasks())
        
        return {
            "success": True,
            "message": f"Entry saved successfully and queued for processing",
            "entry_id": created_entry.id,
            "timestamp": created_entry.timestamp.isoformat(),
            "word_count": created_entry.word_count,
            "entry_type": entry_type,
            "processing_status": "Entry will be processed through enhanced and structured modes in background"
        }
        
    except Exception as e:
        logger.error(f"Error adding entry to diary: {e}")
        return {"success": False, "error": str(e)}


# Background task functions for chat entries using FastAPI BackgroundTasks
async def _generate_embedding_for_entry_chat(entry_id: int, text: str):
    """Background task to generate embedding for a chat entry (same as regular entries)"""
    try:
        logger.info(f"Generating embedding for chat entry {entry_id}")
        embedding_service = get_embedding_service()
        
        # Generate embedding with BGE document formatting
        embedding = await embedding_service.generate_embedding(
            text.strip(), 
            normalize=True, 
            is_query=False
        )
        
        # Update entry with embedding
        await EntryRepository.update_embedding(entry_id, embedding)
        
        logger.info(f"Successfully generated embedding for chat entry {entry_id}")
        
        # Send completion notification for embedding  
        try:
            from app.services.websocket import get_websocket_manager
            websocket_manager = await get_websocket_manager()
            await websocket_manager.broadcast_processing_status({
                "type": "chat_entry_embedding_completed",
                "entry_id": entry_id,
                "message": f"Embedding generated for chat entry {entry_id}"
            })
        except Exception as ws_e:
            logger.warning(f"Failed to send embedding completion notification: {ws_e}")
        
    except Exception as e:
        logger.error(f"Failed to generate embedding for chat entry {entry_id}: {e}")


async def _queue_processing_pipeline_chat(entry_id: int, raw_text: str):
    """Background task to queue processing pipeline for a chat entry"""
    try:
        from app.services.processing_queue import get_processing_queue
        from app.schemas.entry import ProcessingMode
        
        processing_queue = await get_processing_queue()
        
        # Queue for enhanced processing
        enhanced_job_id = await processing_queue.add_job(
            entry_id=entry_id,
            mode=ProcessingMode.ENHANCED,
            raw_text=raw_text
        )
        logger.info(f"Queued enhanced processing for chat entry {entry_id}: {enhanced_job_id}")
        
        # Queue for structured processing
        structured_job_id = await processing_queue.add_job(
            entry_id=entry_id,
            mode=ProcessingMode.STRUCTURED,
            raw_text=raw_text
        )
        logger.info(f"Queued structured processing for chat entry {entry_id}: {structured_job_id}")
        
        # Send notification for processing pipeline queuing
        try:
            from app.services.websocket import get_websocket_manager
            websocket_manager = await get_websocket_manager()
            await websocket_manager.broadcast_processing_status({
                "type": "chat_entry_processing_queued",
                "entry_id": entry_id,
                "message": f"Chat entry {entry_id} queued for enhanced and structured processing"
            })
        except Exception as ws_e:
            logger.warning(f"Failed to send processing queue notification: {ws_e}")
        
    except Exception as e:
        logger.error(f"Failed to queue processing for chat entry {entry_id}: {e}")


async def _trigger_mood_analysis_chat(entry_id: int):
    """Background task to trigger mood analysis for a chat entry (same as regular entries)"""
    try:
        # Get the entry
        entry = await EntryRepository.get_by_id(entry_id)
        if not entry:
            logger.error(f"Chat entry {entry_id} not found for mood analysis")
            return
        
        # Use enhanced text if available, otherwise fall back to raw text (same as regular entries)
        text_to_analyze = entry.enhanced_text or entry.raw_text
        if not text_to_analyze:
            logger.warning(f"Chat entry {entry_id} has no text to analyze for mood")
            return
        
        # Analyze mood and update entry (same pattern as regular entries)
        from app.services.mood_analysis import get_mood_analysis_service
        mood_service = await get_mood_analysis_service()
        mood_tags = await mood_service.analyze_mood(text_to_analyze)
        
        if mood_tags:
            # Update the entry with extracted moods
            entry.mood_tags = mood_tags
            await EntryRepository.update(entry)
            logger.info(f"Updated chat entry {entry_id} with moods: {mood_tags}")
            
            # Send completion notification for mood analysis
            try:
                from app.services.websocket import get_websocket_manager
                websocket_manager = await get_websocket_manager()
                await websocket_manager.broadcast_processing_status({
                    "type": "chat_entry_mood_completed",
                    "entry_id": entry_id,
                    "message": f"Mood analysis completed for chat entry {entry_id}: {mood_tags}"
                })
            except Exception as ws_e:
                logger.warning(f"Failed to send mood completion notification: {ws_e}")
        else:
            logger.info(f"No mood tags generated for chat entry {entry_id}")
        
    except Exception as e:
        logger.error(f"Failed to analyze mood for chat entry {entry_id}: {e}")


async def _register_mood_analysis_callback(entry_id: int):
    """Register callback to trigger mood analysis when enhanced processing completes"""
    try:
        logger.info(f"Registering mood analysis callback for chat entry {entry_id}")
        
        from app.services.processing_queue import get_processing_queue
        from app.schemas.entry import ProcessingMode
        
        processing_queue = await get_processing_queue()
        
        # Define callback that triggers mood analysis when enhanced processing completes
        async def mood_analysis_callback(job):
            try:
                # Only trigger mood analysis for enhanced processing completion of our entry
                if (job.entry_id == entry_id and 
                    job.mode == ProcessingMode.ENHANCED and 
                    job.status.value == "completed"):
                    
                    logger.info(f"Enhanced processing completed for chat entry {entry_id}, triggering mood analysis")
                    await _trigger_mood_analysis_via_api(entry_id)
                    
                    # Remove this callback to avoid memory leaks
                    if mood_analysis_callback in processing_queue._status_callbacks:
                        processing_queue._status_callbacks.remove(mood_analysis_callback)
                        logger.info(f"Removed mood analysis callback for chat entry {entry_id}")
                        
            except Exception as e:
                logger.error(f"Error in mood analysis callback for chat entry {entry_id}: {e}")
        
        # Register the callback
        processing_queue.add_status_callback(mood_analysis_callback)
        logger.info(f"Successfully registered mood analysis callback for chat entry {entry_id}")
        
    except Exception as e:
        logger.error(f"Failed to register mood analysis callback for chat entry {entry_id}: {e}")


async def _trigger_mood_analysis_via_api(entry_id: int):
    """Background task to trigger mood analysis using the same API pattern as NewEntryPage"""
    try:
        logger.info(f"Triggering mood analysis via API pattern for chat entry {entry_id}")
        
        # Get the entry (same as API endpoint)
        entry = await EntryRepository.get_by_id(entry_id)
        if not entry:
            logger.error(f"Chat entry {entry_id} not found for mood analysis")
            return
        
        # Use enhanced text if available, otherwise fall back to raw text (same as API)
        text_to_analyze = entry.enhanced_text or entry.raw_text
        if not text_to_analyze:
            logger.warning(f"Chat entry {entry_id} has no text to analyze for mood")
            return
        
        # Use the same background task function as the API endpoint
        from app.api.routes.entries import _analyze_and_update_entry_mood
        await _analyze_and_update_entry_mood(entry_id, text_to_analyze)
        
        # Send WebSocket notification for chat entries (since API doesn't do this)
        try:
            from app.services.websocket import get_websocket_manager
            websocket_manager = await get_websocket_manager()
            await websocket_manager.broadcast_processing_status({
                "type": "chat_entry_mood_completed",
                "entry_id": entry_id,
                "message": f"Mood analysis completed for chat entry {entry_id}"
            })
        except Exception as ws_e:
            logger.warning(f"Failed to send mood completion notification: {ws_e}")
        
        logger.info(f"Successfully triggered mood analysis for chat entry {entry_id}")
        
    except Exception as e:
        logger.error(f"Failed to trigger mood analysis via API for chat entry {entry_id}: {e}")


async def _send_processing_notification(entry_id: int, status: str):
    """Send WebSocket notification about chat entry processing status"""
    try:
        from app.services.websocket import get_websocket_manager
        websocket_manager = await get_websocket_manager()
        
        if status == "started":
            await websocket_manager.broadcast_processing_status({
                "type": "chat_entry_processing_started",
                "entry_id": entry_id,
                "message": f"Processing chat entry: embeddings, enhanced text, structured summary, and mood analysis"
            })
        elif status == "completed":
            await websocket_manager.broadcast_processing_status({
                "type": "chat_entry_processing_completed", 
                "entry_id": entry_id,
                "message": f"Chat entry {entry_id} fully processed! Entry saved with embeddings, enhanced text, structured summary, and mood analysis."
            })
        elif status == "failed":
            await websocket_manager.broadcast_processing_status({
                "type": "chat_entry_processing_failed",
                "entry_id": entry_id, 
                "message": f"Failed to process chat entry {entry_id}"
            })
            
        logger.info(f"Sent WebSocket notification for chat entry {entry_id}: {status}")
        
    except Exception as e:
        logger.error(f"Failed to send WebSocket notification for chat entry {entry_id}: {e}")


@tool
async def get_context_before_after(entry_id: int, num_before: int = 2, num_after: int = 2) -> Dict[str, Any]:
    """Get entries before and after a specific entry for context.
    
    Use this tool when the user asks about:
    - "What led up to this entry?"
    - "What happened before/after this?"
    - "Show me the context around this"
    - "What was I thinking before/after that?"
    
    args:
        entry_id: The ID of the entry to get context for
        num_before: Number of entries before to retrieve (max 5)
        num_after: Number of entries after to retrieve (max 5)
        
    Returns:
        Context entries with the target entry highlighted
    """
    try:
        logger.info(f"Getting context for entry {entry_id}: {num_before} before, {num_after} after")
        
        # Validate inputs
        if num_before < 0 or num_before > 5:
            num_before = 2
        if num_after < 0 or num_after > 5:
            num_after = 2
        
        # Get the target entry first
        target_entry = await EntryRepository.get_by_id(entry_id)
        if not target_entry:
            return {"success": False, "error": f"Entry {entry_id} not found"}
        
        # Get entries before (older)
        entries_before = []
        if num_before > 0:
            before_results = await EntryRepository.get_entries_before_timestamp(
                timestamp=target_entry.timestamp,
                limit=num_before
            )
            entries_before = before_results
        
        # Get entries after (newer)  
        entries_after = []
        if num_after > 0:
            after_results = await EntryRepository.get_entries_after_timestamp(
                timestamp=target_entry.timestamp,
                limit=num_after
            )
            entries_after = after_results
        
        # Format all entries
        def format_entry(entry, is_target=False):
            return {
                "entry_id": entry.id,
                "content": entry.raw_text or "",
                "enhanced_text": entry.enhanced_text or "",
                "structured_summary": entry.structured_summary or "",
                "timestamp": entry.timestamp.isoformat(),
                "mood_tags": entry.mood_tags or [],
                "mode": entry.mode,
                "word_count": entry.word_count,
                "is_target": is_target
            }
        
        # Build the context
        context = {
            "entries_before": [format_entry(e) for e in reversed(entries_before)],  # Chronological order
            "target_entry": format_entry(target_entry, is_target=True),
            "entries_after": [format_entry(e) for e in entries_after]
        }
        
        return {
            "success": True,
            "context": context,
            "total_entries": len(entries_before) + 1 + len(entries_after),
            "target_entry_id": entry_id,
            "message": f"Found context: {len(entries_before)} before, {len(entries_after)} after"
        }
        
    except Exception as e:
        logger.error(f"Error getting context for entry {entry_id}: {e}")
        return {"success": False, "error": str(e)}


@tool
async def summarize_time_period(start_date: str, end_date: str, focus: Optional[str] = None, max_entries: int = 50) -> Dict[str, Any]:
    """Generate an AI summary of entries from a specific time period.
    
    Use this tool when the user asks for:
    - "Summarize this week/month/period"
    - "What were the highlights of January?"
    - "Give me a recap of my vacation"
    - "Summarize my notes from last week"
    - "What have I been working on lately?"
    
    args:
        start_date: Start date in natural language (e.g., "last monday", "2024-01-01") 
        end_date: End date in natural language (e.g., "today", "2024-01-31")
        focus: Optional focus area (e.g., "work", "ideas", "learning")
        max_entries: Maximum number of entries to analyze (default 50)
        
    Returns:
        AI-generated summary of the time period with key themes and insights
    """
    try:
        logger.info(f"Summarizing period: {start_date} to {end_date}, focus: {focus}")
        
        # Parse date strings using the same logic as get_entries_by_date
        from datetime import datetime, timedelta, date as date_type
        import re
        
        def parse_date_string(date_str: str) -> datetime:
            """Parse natural language date string to datetime"""
            today = date_type.today()
            date_str_lower = date_str.lower().strip()
            
            if date_str_lower in ["today"]:
                return datetime.combine(today, datetime.min.time())
            elif date_str_lower in ["yesterday"]:
                return datetime.combine(today - timedelta(days=1), datetime.min.time())
            elif "days ago" in date_str_lower:
                match = re.search(r'(\d+)\s+days?\s+ago', date_str_lower)
                if match:
                    days_ago = int(match.group(1))
                    return datetime.combine(today - timedelta(days=days_ago), datetime.min.time())
            elif date_str_lower in ["last week"]:
                days_since_monday = today.weekday()
                start_last_week = today - timedelta(days=days_since_monday + 7)
                return datetime.combine(start_last_week, datetime.min.time())
            elif date_str_lower in ["this week"]:
                days_since_monday = today.weekday()
                start_this_week = today - timedelta(days=days_since_monday)
                return datetime.combine(start_this_week, datetime.min.time())
            elif date_str_lower in ["last month"]:
                first_this_month = today.replace(day=1)
                end_last_month = first_this_month - timedelta(days=1)
                start_last_month = end_last_month.replace(day=1)
                return datetime.combine(start_last_month, datetime.min.time())
            elif date_str_lower in ["this month"]:
                return datetime.combine(today.replace(day=1), datetime.min.time())
            else:
                # Try to parse as ISO date
                try:
                    return datetime.fromisoformat(date_str)
                except:
                    # Fallback - treat as relative to today
                    return datetime.combine(today - timedelta(days=7), datetime.min.time())
        
        # Parse dates
        start_datetime = parse_date_string(start_date)
        
        # Handle end date
        if end_date.lower() in ["today", "now"]:
            end_datetime = datetime.combine(date_type.today(), datetime.max.time())
        else:
            end_datetime = parse_date_string(end_date)
            if end_datetime == start_datetime:
                end_datetime = datetime.combine(end_datetime.date(), datetime.max.time())
        
        logger.info(f"Parsed dates: {start_datetime} to {end_datetime}")
        
        # Get entries from the time period
        entries = await EntryRepository.get_entries_with_embeddings(
            limit=max_entries,
            start_date=start_datetime.isoformat(),
            end_date=end_datetime.isoformat()
        )
        
        if not entries:
            return {
                "success": True,
                "summary": "No entries found for the specified time period.",
                "period": f"{start_date} to {end_date}",
                "entries_count": 0
            }
        
        # Prepare content for summarization
        entries_text = []
        for entry in entries:
            # Use the best available text
            text = entry.structured_summary or entry.enhanced_text or entry.raw_text
            if text and text.strip():
                timestamp = entry.timestamp.strftime("%Y-%m-%d")
                entries_text.append(f"[{timestamp}] {text.strip()}")
        
        if not entries_text:
            return {
                "success": True,
                "summary": "No meaningful content found in entries for this period.",
                "period": f"{start_date} to {end_date}",
                "entries_count": len(entries)
            }
        
        # Create summarization prompt
        combined_text = "\n\n".join(entries_text)
        
        focus_instruction = f" Focus particularly on: {focus}." if focus else ""
        
        summary_prompt = f"""Please provide a thoughtful summary of these journal/note entries from {start_date} to {end_date}.{focus_instruction}

Identify key themes, important events, insights, decisions, and patterns. Be concise but capture the essence of this period.

Entries:
{combined_text}

Summary:"""
        
        # Generate summary using the LLM (we'll use the same LLM as the chat service)
        try:
            # Get the LLM instance (ensure it's initialized)
            chat_service = get_diary_chat_service()
            await chat_service._ensure_initialized()
            
            # Use the base LLM without tools for summarization
            from langchain_core.messages import SystemMessage, HumanMessage
            
            messages = [
                SystemMessage(content="You are a thoughtful assistant helping summarize personal journal entries and notes. Provide clear, insightful summaries that help the user understand patterns and themes in their thoughts and activities."),
                HumanMessage(content=summary_prompt)
            ]
            
            response = await chat_service.llm.ainvoke(messages)
            summary = strip_thinking_block(response.content)
            
        except Exception as e:
            logger.error(f"Failed to generate AI summary: {e}")
            # Fallback to simple text summary
            summary = f"Found {len(entries)} entries from {start_date} to {end_date}. Topics mentioned include various personal notes and thoughts."
        
        return {
            "success": True,
            "summary": summary,
            "period": f"{start_date} to {end_date}",
            "entries_count": len(entries),
            "date_range": {
                "start_date": start_datetime.isoformat(),
                "end_date": end_datetime.isoformat()
            }
        }
        
    except Exception as e:
        logger.error(f"Error summarizing time period: {e}")
        return {"success": False, "error": str(e)}


@tool
async def extract_ideas_and_concepts(topic: Optional[str] = None, time_period: Optional[str] = "all_time", limit: int = 30) -> Dict[str, Any]:
    """Extract ideas and concepts from diary entries using AI analysis.
    
    Use this tool when the user asks about:
    - "What ideas have I had about X?"
    - "Show me my thoughts on Y"
    - "Extract my concepts about Z"
    - "What have I been thinking about?"
    - "Find my insights on this topic"
    
    args:
        topic: Optional topic to focus on (e.g., "machine learning", "startup", "work")
        time_period: Time range to search ("last_week", "last_month", "all_time")
        limit: Maximum number of entries to analyze (default 30)
        
    Returns:
        AI-extracted ideas and concepts with context
    """
    try:
        logger.info(f"Extracting ideas and concepts: topic={topic}, period={time_period}")
        
        # Get entries from specified time period
        if time_period == "all_time":
            # Fetch entries directly from database
            entries = await EntryRepository.get_entries_with_embeddings(limit=limit)
            if len(entries) > limit:
                entries = entries[:limit]  # Take most recent
        else:
            # Use date filtering for specific periods
            from datetime import datetime, timedelta, date as date_type
            
            today = date_type.today()
            if time_period == "last_week":
                start_date = today - timedelta(days=7)
                end_date = today
            elif time_period == "last_month":
                start_date = today - timedelta(days=30)
                end_date = today
            else:
                start_date = today - timedelta(days=7)  # Default to last week
                end_date = today
            
            start_datetime = datetime.combine(start_date, datetime.min.time())
            end_datetime = datetime.combine(end_date, datetime.max.time())
            
            entries = await EntryRepository.get_entries_with_embeddings(
                limit=limit,
                start_date=start_datetime.isoformat(),
                end_date=end_datetime.isoformat()
            )
        
        if not entries:
            return {
                "success": True,
                "ideas": [],
                "concepts": [],
                "count": 0,
                "message": "No entries found for analysis"
            }
        
        # Filter entries that contain ideas (using smart tags if available)
        idea_entries = []
        for entry in entries:
            # Check if entry has smart tags indicating ideas
            if (entry.smart_tags and 
                isinstance(entry.smart_tags, list) and
                "idea" in entry.smart_tags):
                idea_entries.append(entry)
            else:
                # Fallback: check content for idea keywords
                text = entry.raw_text or ""
                if any(keyword in text.lower() for keyword in 
                       ["idea", "thought", "concept", "insight", "innovation", "approach"]):
                    idea_entries.append(entry)
        
        # If we have too few "idea" entries, include all entries
        if len(idea_entries) < 5:
            idea_entries = entries
        
        # Prepare content for AI analysis
        entries_text = []
        for entry in idea_entries[:15]:  # Limit for AI processing
            text = entry.structured_summary or entry.enhanced_text or entry.raw_text
            if text and text.strip():
                timestamp = entry.timestamp.strftime("%Y-%m-%d")
                entries_text.append(f"[{timestamp}] {text.strip()}")
        
        if not entries_text:
            return {
                "success": True,
                "ideas": [],
                "concepts": [],
                "count": 0,
                "message": "No meaningful content found for idea extraction"
            }
        
        # Create AI prompt for idea extraction
        combined_text = "\n\n".join(entries_text)
        
        topic_filter = f" related to '{topic}'" if topic else ""
        
        extraction_prompt = f"""Please analyze these journal/note entries and extract key ideas and concepts{topic_filter}.

For each idea or concept you find, provide:
1. The main idea/concept (brief title)
2. A short description 
3. The date it was mentioned
4. Why it's significant

Focus on:
- Novel ideas and insights
- Creative concepts
- Problem-solving approaches  
- Strategic thoughts
- Innovation ideas
- Potential solutions

Entries to analyze:
{combined_text}

Please format your response as a structured list of ideas and concepts."""
        
        # Generate analysis using LLM
        try:
            chat_service = get_diary_chat_service()
            await chat_service._ensure_initialized()
            
            from langchain_core.messages import SystemMessage, HumanMessage
            
            messages = [
                SystemMessage(content="You are an AI assistant that helps extract and organize ideas and concepts from personal notes and journal entries. Be insightful and identify valuable thoughts and innovations."),
                HumanMessage(content=extraction_prompt)
            ]
            
            response = await chat_service.llm.ainvoke(messages)
            analysis = strip_thinking_block(response.content)
            
        except Exception as e:
            logger.error(f"Failed to generate AI analysis: {e}")
            # Fallback response
            analysis = f"Found {len(idea_entries)} entries with potential ideas and concepts. Manual review recommended for detailed analysis."
        
        return {
            "success": True,
            "analysis": analysis,
            "entries_analyzed": len(entries_text),
            "topic_filter": topic,
            "time_period": time_period,
            "total_entries": len(entries)
        }
        
    except Exception as e:
        logger.error(f"Error extracting ideas and concepts: {e}")
        return {"success": False, "error": str(e)}


@tool
async def search_conversations(query: str, limit: int = 10) -> Dict[str, Any]:
    """Search through past conversations with Boo using semantic search.
    
    Use this tool when user asks about:
    - Previous chats or conversations with Boo
    - What they discussed with Boo before
    - Past topics they talked about in conversations
    - Their name or personal details mentioned in conversations
    
    args:
        query: Search term for conversations (1-1000 characters)
        limit: Maximum number of results to return (default 10)
        
    Returns:
        Relevant conversation snippets with similarity scores
    """
    try:
        logger.info(f"Searching conversations: query='{query}', limit={limit}")
        
        # Validate inputs
        if not query or len(query.strip()) == 0:
            return {"success": False, "error": "Query cannot be empty"}
        
        if limit < 1 or limit > 50:
            limit = 10
            
        query = query.strip()[:1000]  # Limit query length
        
        # Generate query embedding using the same service as entries
        embedding_service = get_embedding_service()
        query_embedding = await embedding_service.generate_embedding(
            text=query,
            normalize=True,
            is_query=True  # Mark as query for BGE formatting
        )
        
        # Get database instance
        db = get_db()
        import json
        
        # Get conversations with embeddings - same pattern as entries
        rows = await db.fetch_all("""
            SELECT id, summary, transcription, timestamp, embedding, key_topics, conversation_type, duration
            FROM conversations 
            WHERE embedding IS NOT NULL AND embedding != ''
            ORDER BY timestamp DESC
            LIMIT 100
        """)
        
        if not rows:
            return {
                "success": True,
                "conversations": [],
                "count": 0,
                "query": query,
                "message": "No past conversations with embeddings found"
            }
        
        # Extract embeddings and calculate similarities - same pattern as entries
        candidate_embeddings = []
        conversation_metadata = []
        
        for row in rows:
            if row['embedding']:
                try:
                    # Parse embedding JSON
                    embedding_data = json.loads(row['embedding'])
                    if isinstance(embedding_data, list) and len(embedding_data) > 0:
                        candidate_embeddings.append(embedding_data)
                        conversation_metadata.append(row)
                except (json.JSONDecodeError, TypeError):
                    continue
        
        if not candidate_embeddings:
            return {
                "success": True,
                "conversations": [],
                "count": 0,
                "query": query,
                "message": "No valid conversation embeddings found"
            }
        
        # Use the same semantic search as entries
        similar_conversations = embedding_service.search_similar_embeddings(
            query_embedding=query_embedding,
            candidate_embeddings=candidate_embeddings,
            top_k=min(limit * 2, 50),  # Get 2x candidates for reranking
            similarity_threshold=0.3  # Lower threshold than the old 0.5
        )
        
        # Format results - same pattern as entries
        results = []
        for i, (candidate_idx, similarity) in enumerate(similar_conversations[:limit]):
            conv_row = conversation_metadata[candidate_idx]
            
            # Get conversation snippet - prefer summary, fall back to transcription
            snippet = conv_row['summary'] if conv_row['summary'] else conv_row['transcription'][:500]
            if len(conv_row['transcription']) > 500:
                snippet += "..."
            
            results.append({
                'score': float(similarity),
                'id': conv_row['id'],
                'snippet': snippet,
                'full_transcription': conv_row['transcription'],  # Include full text
                'timestamp': conv_row['timestamp'],
                'conversation_type': conv_row['conversation_type'],
                'duration': conv_row['duration'],
                'topics': json.loads(conv_row['key_topics']) if conv_row['key_topics'] else []
            })
        
        return {
            "success": True,
            "conversations": results,
            "count": len(results),
            "query": query,
            "message": f"Found {len(results)} relevant conversations"
        }
        
    except Exception as e:
        logger.error(f"Error searching conversations: {e}")
        return {"success": False, "error": str(e)}

@tool
async def extract_action_items(status: Optional[str] = None, time_period: Optional[str] = "all_time", limit: int = 30) -> Dict[str, Any]:
    """Extract action items and TODOs from diary entries using AI analysis.
    
    Use this tool when the user asks about:
    - "What tasks do I need to do?"
    - "Show me my action items"
    - "What TODOs have I mentioned?"
    - "Find my pending tasks"
    - "What do I need to follow up on?"
    
    args:
        status: Filter by status ("pending", "completed", "all")
        time_period: Time range to search ("last_week", "last_month", "all_time") 
        limit: Maximum number of entries to analyze (default 30)
        
    Returns:
        AI-extracted action items and TODOs with context and status
    """
    try:
        logger.info(f"Extracting action items: status={status}, period={time_period}")
        
        # Get entries from specified time period
        if time_period == "all_time":
            entries = await EntryRepository.get_entries_with_embeddings(limit=limit)
            if len(entries) > limit:
                entries = entries[:limit]
        else:
            from datetime import datetime, timedelta, date as date_type
            
            today = date_type.today()
            if time_period == "last_week":
                start_date = today - timedelta(days=7)
                end_date = today
            elif time_period == "last_month":
                start_date = today - timedelta(days=30)
                end_date = today
            else:
                start_date = today - timedelta(days=7)
                end_date = today
            
            start_datetime = datetime.combine(start_date, datetime.min.time())
            end_datetime = datetime.combine(end_date, datetime.max.time())
            
            entries = await EntryRepository.get_entries_with_embeddings(
                limit=limit,
                start_date=start_datetime.isoformat(),
                end_date=end_datetime.isoformat()
            )
        
        if not entries:
            return {
                "success": True,
                "action_items": [],
                "count": 0,
                "message": "No entries found for analysis"
            }
        
        # Filter entries that contain action items (using smart tags if available)
        action_entries = []
        for entry in entries:
            # Check smart tags for TODO items
            if (entry.smart_tags and 
                isinstance(entry.smart_tags, list) and
                "todo" in entry.smart_tags):
                action_entries.append(entry)
            else:
                # Fallback: check content for action keywords
                text = entry.raw_text or ""
                if any(keyword in text.lower() for keyword in 
                       ["todo", "need to", "should", "must", "task", "action", "follow up", "remember to"]):
                    action_entries.append(entry)
        
        # If we have too few action entries, include all entries for broader analysis
        if len(action_entries) < 3:
            action_entries = entries[:10]  # Limit to recent entries for performance
        
        # Prepare content for AI analysis
        entries_text = []
        for entry in action_entries[:15]:  # Limit for AI processing
            text = entry.structured_summary or entry.enhanced_text or entry.raw_text
            if text and text.strip():
                timestamp = entry.timestamp.strftime("%Y-%m-%d")
                entries_text.append(f"[{timestamp}] {text.strip()}")
        
        if not entries_text:
            return {
                "success": True,
                "action_items": [],
                "count": 0,
                "message": "No meaningful content found for action item extraction"
            }
        
        # Create AI prompt for action item extraction
        combined_text = "\n\n".join(entries_text)
        
        status_filter = f" Focus on {status} items." if status and status != "all" else ""
        
        extraction_prompt = f"""Please analyze these journal/note entries and extract all action items, tasks, and TODOs.{status_filter}

For each action item you find, provide:
1. The task/action item (clear, concise description)
2. Priority level (High/Medium/Low) based on urgency indicators
3. The date it was mentioned
4. Current status (if determinable: Pending/In Progress/Completed)
5. Any deadline or time sensitivity mentioned

Look for:
- Explicit TODOs and tasks
- "Need to", "should", "must" statements  
- Follow-up items
- Deadlines and commitments
- Action-oriented language
- Unfinished items mentioned

Entries to analyze:
{combined_text}

Please format your response as a structured list of action items with the details above."""
        
        # Generate analysis using LLM
        try:
            chat_service = get_diary_chat_service()
            await chat_service._ensure_initialized()
            
            from langchain_core.messages import SystemMessage, HumanMessage
            
            messages = [
                SystemMessage(content="You are an AI assistant that helps extract and organize action items, tasks, and TODOs from personal notes. Be thorough in identifying actionable items and commitments."),
                HumanMessage(content=extraction_prompt)
            ]
            
            response = await chat_service.llm.ainvoke(messages)
            analysis = strip_thinking_block(response.content)
            
        except Exception as e:
            logger.error(f"Failed to generate AI analysis: {e}")
            # Fallback response
            analysis = f"Found {len(action_entries)} entries with potential action items. Manual review recommended for detailed task extraction."
        
        return {
            "success": True,
            "analysis": analysis,
            "entries_analyzed": len(entries_text),
            "status_filter": status,
            "time_period": time_period,
            "total_entries": len(entries)
        }
        
    except Exception as e:
        logger.error(f"Error extracting action items: {e}")
        return {"success": False, "error": str(e)}


@tool 
async def get_entries_by_date(date_filter: str, limit: int = 100) -> Dict[str, Any]:
    """Get diary entries filtered by specific dates or date ranges.
    
    Use this tool when the user asks about entries from specific dates like:
    - "yesterday", "today", "last week"
    - "last Saturday", "this Monday", "two days ago"
    - "January 15th", "last month", "this year"
    - "my last entry", "most recent entries", "latest journal"
    - "latest diary entry", "my recent diary", "last diary note"
    
    args:
        date_filter: Natural language date filter (e.g., "yesterday", "last Saturday", "this week", "latest entry")
        limit: Maximum number of results to return (100)
        
    Returns:
        Entries matching the date filter with full content and mood_tags
    """
    try:
        logger.info(f"Getting entries by date: filter='{date_filter}', limit={limit}")
        
        # Get current date for calculations
        today = date.today()
        now = datetime.now()
        
        # Parse date filter and calculate date range
        start_date = None
        end_date = None
        
        date_filter_lower = date_filter.lower().strip()
        
        if date_filter_lower in ["today"]:
            start_date = today
            end_date = today
        elif date_filter_lower in ["yesterday"]:
            yesterday = today - timedelta(days=1)
            start_date = yesterday
            end_date = yesterday
        elif date_filter_lower in ["last week", "this week"]:
            # Get start of current week (Monday)
            days_since_monday = today.weekday()
            if date_filter_lower == "this week":
                start_date = today - timedelta(days=days_since_monday)
                end_date = today
            else:  # last week
                start_date = today - timedelta(days=days_since_monday + 7)
                end_date = today - timedelta(days=days_since_monday + 1)
        elif date_filter_lower in ["last month", "this month"]:
            if date_filter_lower == "this month":
                start_date = today.replace(day=1)
                end_date = today
            else:  # last month
                first_this_month = today.replace(day=1)
                end_date = first_this_month - timedelta(days=1)
                start_date = end_date.replace(day=1)
        elif "days ago" in date_filter_lower:
            # Parse "X days ago"
            match = re.search(r'(\d+)\s+days?\s+ago', date_filter_lower)
            if match:
                days_ago = int(match.group(1))
                target_date = today - timedelta(days=days_ago)
                start_date = target_date
                end_date = target_date
        elif any(day in date_filter_lower for day in ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]):
            # Parse "last Saturday", "this Monday", etc.
            days_of_week = {
                "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
                "friday": 4, "saturday": 5, "sunday": 6
            }
            
            for day_name, day_num in days_of_week.items():
                if day_name in date_filter_lower:
                    current_weekday = today.weekday()
                    
                    if "last" in date_filter_lower:
                        # Get last occurrence of this weekday
                        days_back = (current_weekday - day_num) % 7
                        if days_back == 0:  # If it's the same day, go back a week
                            days_back = 7
                        target_date = today - timedelta(days=days_back)
                    else:  # "this" or no qualifier
                        # Get this week's occurrence
                        days_forward = (day_num - current_weekday) % 7
                        target_date = today + timedelta(days=days_forward)
                        
                        # If it's in the future, get last week's occurrence
                        if target_date > today:
                            target_date = target_date - timedelta(days=7)
                    
                    start_date = target_date
                    end_date = target_date
                    break
        
        # Handle "latest", "last entry", "most recent" queries
        elif any(keyword in date_filter_lower for keyword in ["latest", "last entry", "most recent", "last saved"]):
            logger.info(f"Handling latest entry query: '{date_filter}'")
            start_date = today - timedelta(days=7)  # Last 7 days for latest queries
            end_date = today
        
        # If we couldn't parse the date filter, return last 7 days as fallback
        if start_date is None:
            logger.warning(f"Could not parse date filter '{date_filter}', using last 7 days")
            start_date = today - timedelta(days=7)
            end_date = today
        
        # Convert to datetime for database query
        start_datetime = datetime.combine(start_date, datetime.min.time())
        end_datetime = datetime.combine(end_date, datetime.max.time())
        
        logger.info(f"Date range: {start_datetime} to {end_datetime}")
        
        # Fetch entries directly from database with date filtering
        logger.info("Fetching entries from database for date range")
        entries = await EntryRepository.get_entries_with_embeddings(
            limit=limit,
            start_date=start_datetime.isoformat(),
            end_date=end_datetime.isoformat()
        )
        
        # Format results with full content and mood_tags
        results = []
        for entry in entries:
            result = {
                "entry_id": entry.id,
                "content": entry.raw_text or "",
                "enhanced_text": entry.enhanced_text or "",
                "structured_summary": entry.structured_summary or "",
                "timestamp": entry.timestamp.isoformat(),
                "mood_tags": entry.mood_tags or [],
                "mode": entry.mode,
                "word_count": entry.word_count
            }
            results.append(result)
        
        return {
            "success": True,
            "results": results,
            "count": len(results),
            "date_filter": date_filter,
            "date_range": {
                "start_date": start_datetime.isoformat(),
                "end_date": end_datetime.isoformat()
            },
            "message": f"Found {len(results)} entries for {date_filter}"
        }
        
    except Exception as e:
        logger.error(f"Error in get_entries_by_date: {e}")
        return {"success": False, "error": str(e)}



class DiaryChatService:
    """Service for diary conversations using LangChain ChatOllama with tool calling."""
    
    def __init__(self):
        """Initialize the diary chat service with LangChain ChatOllama."""
        # Will be initialized with preferences in async method
        self.llm = None
        self.llm_with_tools = None
        self._initialized = False
        self.memory_service = MemoryService()
        
        self.search_feedback_messages = [
            "Checking diary...",
            "Reading your thoughts...",
            "Searching your memories...",
            "Looking through your entries...",
            "Finding relevant moments...",
            "Exploring your past entries...",
            "Scanning your journal...",
            "Reviewing your thoughts..."
        ]
        
        # AI greeting variants for modal initialization
        self.greeting_variants = [
            "Hi there! I'm Boo. You can type or speak—whatever feels natural. Want to reflect, revisit, or brainstorm something together?",
            "Hello! Boo here, listening in. Whether you're capturing thoughts or tracking progress, I'm here to help. Ready when you are.",
            "Hey! I'm Boo. If you've got something on your mind—a thought, a memory, an idea—just type or talk it out. Let's explore.",
            "Hi! It's Boo. I can help you make sense of your notes, thoughts, or just keep you company while you think aloud.",
            "Hello there! Boo ready. Whether it's a passing thought or a long reflection, I'm here to connect the dots with you.",
            "Hey! Boo at your side. Journal entries, random ideas, half-finished plans—whatever it is, I can help you navigate it.",
            "Hi! I'm Boo. No pressure, no rush. Just speak or type whenever you're ready. I'm here to help you think things through.",
            "Hello! Boo here. You've got the space, I've got the memory. Share a thought or ask about one—we'll take it from there.",
            "Hey there! I'm Boo. Whether you're capturing moments or mapping out ideas, I've got your back. What's first on your mind?",
            "Hi! It's Boo, your thoughtful assistant. Just type or tap the mic to get started. Ready when you are."
        ]
    
    async def _ensure_initialized(self):
        """Ensure the service is initialized with current preferences."""
        if self._initialized:
            return
        
        try:
            # Load Talk to Your Diary specific preferences from database
            model_name = await PreferencesRepository.get_value('talk_to_diary_model', 'qwen3:8b')
            temperature = await PreferencesRepository.get_value('talk_to_diary_temperature', 0.2)  
            base_url = await PreferencesRepository.get_value('ollama_url', 'http://localhost:11434')
            num_ctx = await PreferencesRepository.get_value('talk_to_diary_context_window', 8192)
            
            logger.info(f"Initializing DiaryChatService with model: {model_name}, temp: {temperature}, ctx: {num_ctx}")
            
            # Initialize ChatOllama with preferences  
            self.llm = ChatOllama(
                model=model_name,
                base_url=base_url,
                temperature=float(temperature),
                num_ctx=int(num_ctx),
                num_gpu=-1  # Use all GPU layers for maximum performance
            )
            
            logger.info(f"Initialized LLM with model: {model_name}")
            
            # Bind tools to the LLM
            self.llm_with_tools = self.llm.bind_tools([
                search_diary_entries, 
                get_entries_by_date,
                add_entry_to_diary,
                get_context_before_after,
                summarize_time_period,
                extract_ideas_and_concepts,
                extract_action_items,
                search_conversations
            ])
            self._initialized = True
            
        except Exception as e:
            logger.error(f"Failed to initialize DiaryChatService: {e}")
            # Fallback - still try to use Talk to Your Diary specific preferences
            try:
                fallback_model = await PreferencesRepository.get_value('talk_to_diary_model', settings.OLLAMA_DEFAULT_MODEL)
                fallback_temp = await PreferencesRepository.get_value('talk_to_diary_temperature', 0.2)
                fallback_ctx = await PreferencesRepository.get_value('talk_to_diary_context_window', 8192)
                fallback_url = await PreferencesRepository.get_value('ollama_url', 'http://localhost:11434')
            except:
                # If even preference lookup fails, use absolute defaults
                fallback_model = settings.OLLAMA_DEFAULT_MODEL
                fallback_temp = 0.2
                fallback_ctx = 8192
                fallback_url = 'http://localhost:11434'
            
            self.llm = ChatOllama(
                model=fallback_model,
                base_url=fallback_url,
                temperature=float(fallback_temp),
                num_ctx=int(fallback_ctx),
                num_gpu=-1  # Use all GPU layers for maximum performance
            )
            self.llm_with_tools = self.llm.bind_tools([
                search_diary_entries, 
                get_entries_by_date,
                add_entry_to_diary,
                get_context_before_after,
                summarize_time_period,
                extract_ideas_and_concepts,
                extract_action_items,
                search_conversations
            ])
            self._initialized = True
    
    async def process_message(
        self, 
        message: str, 
        conversation_history: Optional[List[Dict[str, str]]] = None,
        background_tasks = None,
        memory_enabled: bool = True,
        debug_mode: bool = False,
        user_info: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Process a user message with LangChain tool calling.
        
        Args:
            message: User's message
            conversation_history: Previous conversation messages
            
        Returns:
            Response with message, tool calls used, and search feedback
        """
        try:
            # Ensure service is initialized with current preferences
            await self._ensure_initialized()
            
            # Set background_tasks in context for tools to access
            if background_tasks:
                _background_tasks_ctx.set(background_tasks)
            
            logger.info(f"Processing diary chat message: '{message[:50]}...'")
            
            # Build message history for LangChain with system date awareness
            today = date.today()
            messages = [
                SystemMessage(content=f"""You are Boo, a journaling companion. Today is {today.strftime('%A, %B %d, %Y')}.

CRITICAL: ALWAYS use tools (one or multiple) to search the user's journal entries. NEVER respond without using tools first.

TOOL STRATEGY - Use multiple tools when helpful:
• search_diary_entries + get_entries_by_date: For complex queries combining content and dates
• search_diary_entries + extract_ideas_and_concepts: When asking about thoughts/ideas on topics  
• get_entries_by_date + summarize_time_period: For dated summaries
• Any search + add_entry_to_diary: When user wants to save something after reviewing entries

REQUIRED TOOLS:
- search_diary_entries: Content searches ("work", "hiking", feelings, activities)
- get_entries_by_date: Date searches ("yesterday", "last week", "recent") 
- add_entry_to_diary: ONLY when user EXPLICITLY asks to save ("save this", "add to journal", "add entry")
- summarize_time_period: Time-based summaries
- extract_ideas_and_concepts/extract_action_items: Extract insights/tasks
- get_context_before_after: Context around specific entries
- search_conversations: Search past conversations with Boo

CRITICAL: Never use add_entry_to_diary unless user explicitly requests saving content with clear save commands.

The user has journal entries and past conversations - you must search them using tools to give meaningful responses.""")
            ]
            
            # Add conversation history
            if conversation_history:
                for turn in conversation_history[-10:]:  # Last 10 turns for context
                    role = turn.get("role", "user")
                    content = turn.get("content", "")
                    if role == "user":
                        messages.append(HumanMessage(content=content))
                    elif role == "assistant":
                        messages.append(AIMessage(content=content))
            
            # Add current message
            messages.append(HumanMessage(content=message))
            
            # Check if this is a query that should definitely use tools
            should_force_tools = any(phrase in message.lower() for phrase in [
                "what did i", "show me", "find", "search", "yesterday", "last week", "today", 
                "recent", "latest", "my entry", "my entries", "wrote about", "mentioned", 
                "how do i feel", "mood", "what have i", "when did i", "tell me about",
                "my thoughts on", "ideas about", "remember when", "save this", "add this",
                "add to journal", "add entry", "add to diary"
            ])
            
            # Get response from LLM with tools
            response = await self.llm_with_tools.ainvoke(messages)
            
            # If should force tools but no tools were used, try again with stronger prompt
            if should_force_tools and not response.tool_calls:
                logger.warning(f"Forcing tool usage for message: '{message[:50]}...'")
                
                # Add a stronger directive message
                force_message = HumanMessage(content=f"""The user asked: "{message}"

This requires searching their journal entries. You MUST use the search_diary_entries or get_entries_by_date tool to find relevant entries before responding. Do not give a generic response - search their actual journal content first.""")
                
                force_messages = messages + [force_message]
                response = await self.llm_with_tools.ainvoke(force_messages)
            
            # Debug logging
            logger.info(f"LLM Response type: {type(response)}")
            logger.info(f"Response content: {response.content[:200]}...")
            logger.info(f"Response tool_calls: {response.tool_calls}")
            
            # Process tool calls if any
            tool_calls_made = []
            search_queries_used = []
            
            if response.tool_calls:
                logger.info(f"Tool calls detected: {len(response.tool_calls)}")
                
                # Execute tool calls
                for tool_call in response.tool_calls:
                    tool_name = tool_call["name"]
                    tool_args = tool_call["args"]
                    
                    logger.info(f"Executing {tool_name} with args: {tool_args}")
                    
                    if tool_name == "search_diary_entries":
                        tool_result = await search_diary_entries.ainvoke(tool_args)
                    elif tool_name == "get_entries_by_date":
                        tool_result = await get_entries_by_date.ainvoke(tool_args)
                    elif tool_name == "add_entry_to_diary":
                        tool_result = await add_entry_to_diary.ainvoke(tool_args)
                    elif tool_name == "get_context_before_after":
                        tool_result = await get_context_before_after.ainvoke(tool_args)
                    elif tool_name == "summarize_time_period":
                        tool_result = await summarize_time_period.ainvoke(tool_args)
                    elif tool_name == "extract_ideas_and_concepts":
                        tool_result = await extract_ideas_and_concepts.ainvoke(tool_args)
                    elif tool_name == "extract_action_items":
                        tool_result = await extract_action_items.ainvoke(tool_args)
                    elif tool_name == "search_conversations":
                        tool_result = await search_conversations.ainvoke(tool_args)
                    else:
                        logger.warning(f"Unknown tool: {tool_name}")
                        continue
                    
                    tool_calls_made.append({
                        "tool": tool_name,
                        "arguments": tool_args,
                        "result": tool_result
                    })
                    
                    # Track search queries
                    if tool_name == "search_diary_entries":
                        query = tool_args.get("query", "")
                        if query:
                            search_queries_used.append(query)
                    elif tool_name == "get_entries_by_date":
                        date_filter = tool_args.get("date_filter", "")
                        if date_filter:
                            search_queries_used.append(f"Date: {date_filter}")
            
            # Always add tool results to messages if tools were executed
            if tool_calls_made:
                # Add the tool call message to conversation
                messages.append(response)
                
                # Add tool results as ToolMessages
                for i, tool_call in enumerate(tool_calls_made):
                    tool_call_id = response.tool_calls[i]["id"] if i < len(response.tool_calls) else "unknown"
                    messages.append(ToolMessage(
                        content=str(tool_call["result"]),
                        tool_call_id=tool_call_id
                    ))
            
            # Retrieve relevant memories for context injection (always done)
            relevant_memories = []
            memory_context = ""
            if memory_enabled:
                try:
                    # Get memories relevant to the user's question
                    relevant_memories = await self.memory_service.retrieve_relevant_memories(message, limit=20)
                    if relevant_memories:
                        memory_context = self.memory_service.format_memories_for_context(relevant_memories)
                        logger.info(f"Injecting {len(relevant_memories)} memories into response generation")
                except Exception as e:
                    logger.error(f"Failed to retrieve memories: {e}")
            
            # Check if ToolMessages are present to determine system prompt
            has_tool_results = any(isinstance(msg, ToolMessage) for msg in messages[1:])
            
            # Build dynamic system prompt based on ToolMessage presence
            today = date.today()
            user_name = user_info.get('display_name', '') if user_info else ''
            date_context = f"Today is {today.strftime('%A, %B %d, %Y')}."
            user_context = f" The user's name is \"{user_name}\"." if user_name else ""
            
            if has_tool_results:
                # Tools were used - focus on tool results
                if memory_enabled:
                    system_prompt = f"You are Boo.{date_context}{user_context} Look for tool results containing user's journal entries and conversations. Also check the 'What you remember about the user' section below for relevant memories. Analyze all this information and the user's question. Then thoughtfully reply as if you are talking to the user naturally using 'you' and 'your'. Keep the answers short (3-4 sentences) UNLESS the user asks otherwise or asks to show the whole entry."
                else:
                    system_prompt = f"You are Boo.{date_context}{user_context} Look for tool results containing user's journal entries and conversations. Analyze this information and the user's question. Then thoughtfully reply as if you are talking to the user naturally using 'you' and 'your'. Keep the answers short (3-4 sentences) UNLESS the user asks otherwise or asks to show the whole entry."
            else:
                # No tools used - natural conversation
                if memory_enabled:
                    system_prompt = f"You are Boo, the user's journaling companion.{date_context}{user_context} Respond naturally and warmly. Carefully analyze the user's query and share your response. Also check the 'What you remember about the user' section below for relevant context."
                else:
                    system_prompt = f"You are Boo, the user's journaling companion.{date_context}{user_context} Respond naturally and warmly. Carefully analyze the user's query and share your response."
            
            if memory_context:
                system_prompt += f"\n\n## What you remember about the user:\n{memory_context}"
            
            # Create response messages with dynamic system prompt
            response_messages = [
                SystemMessage(content=system_prompt),
                *messages[1:]  # All messages: user, AI response (if tools used), ToolMessages (if any)
            ]
            
            # Get final response using base LLM (no tools needed)
            final_response_msg = await self.llm.ainvoke(response_messages)
            final_response = strip_thinking_block(final_response_msg.content)
            
            # Collect debug information
            if debug_mode:
                debug_info_here = {
                    "memory_enabled": memory_enabled,
                    "system_prompt_used": system_prompt,
                    "memory_context_injected": bool(memory_context),
                    "memory_count": len(relevant_memories) if relevant_memories else 0,
                    "memory_context": memory_context,
                    "memory_retrieval_attempted": memory_enabled,
                    "tool_calls_count": len(tool_calls_made),
                    "has_tool_calls": bool(tool_calls_made),
                    "has_tool_results": has_tool_results,
                    "conversation_type": "tool_assisted" if has_tool_results else "natural_conversation",
                    "timestamp": str(datetime.now())
                }
                # Store for later use
                globals()['_current_debug_info'] = debug_info_here
            
            # Fallback if response is empty
            if not final_response or final_response.strip() == "":
                final_response = "Hello! I'm Boo, your journal companion. I'm here to help you explore your thoughts and memories. What would you like to talk about today?"
                logger.warning("Used fallback response due to empty model response")
            
            # Generate tool-specific feedback and processing phases
            tool_feedback = None
            processing_phases = []
            
            # Tool name to user-friendly message mapping
            tool_messages = {
                "search_diary_entries": "Searching your diary entries",
                "get_entries_by_date": "Looking up entries by date", 
                "get_context_before_after": "Finding related entries",
                "extract_ideas_and_concepts": "Analyzing ideas and concepts",
                "extract_action_items": "Extracting action items",
                "summarize_time_period": "Summarizing time period",
                "add_entry_to_diary": "Saving entry to diary",
                "search_conversations": "Searching past conversations"
            }
            
            if tool_calls_made:
                tool_names = [tool["tool"] for tool in tool_calls_made]
                
                # Generate tool feedback for summary
                if len(tool_names) == 1:
                    tool_feedback = f"Used {tool_names[0].replace('_', ' ').title()}"
                else:
                    tool_list = ", ".join([name.replace('_', ' ').title() for name in tool_names[:-1]])
                    tool_feedback = f"Used {tool_list} and {tool_names[-1].replace('_', ' ').title()}"
                
                # Create detailed processing phases for tool execution
                processing_phases = [{"phase": "analysis", "message": "Analyzing your question"}]
                
                # Add a phase for each tool used
                for tool_name in tool_names:
                    tool_message = tool_messages.get(tool_name, tool_name.replace('_', ' ').title())
                    processing_phases.append({
                        "phase": f"tool_{tool_name}",
                        "message": tool_message,
                        "tool": tool_name
                    })
                
                # Add final response generation phase
                processing_phases.append({"phase": "generation", "message": "Generating response"})
                
            else:
                # Non-tool response phases
                processing_phases = [
                    {"phase": "analysis", "message": "Analyzing your question"},
                    {"phase": "thinking", "message": "Thinking about your request"},
                    {"phase": "generation", "message": "Generating response"}
                ]
            
            # Collect debug information if requested
            debug_info = None
            if debug_mode:
                # Try to get debug info collected during processing
                debug_info = globals().get('_current_debug_info')
                if not debug_info:
                    # Fallback debug info (for cases where tools weren't used)
                    debug_info = {
                        "memory_enabled": memory_enabled,
                        "system_prompt_used": "No tools used - direct response",
                        "memory_context_injected": False,
                        "memory_count": 0,
                        "memory_context": None,
                        "memory_retrieval_attempted": memory_enabled,
                        "tool_calls_count": len(tool_calls_made),
                        "has_tool_calls": bool(tool_calls_made),
                        "timestamp": str(datetime.now())
                    }
                
                logger.info(f"Debug info collected: {debug_info}")
                
                # Clear the global debug info
                globals().pop('_current_debug_info', None)

            return {
                "response": final_response,
                "tool_calls_made": tool_calls_made,
                "search_queries_used": search_queries_used,
                "tool_feedback": tool_feedback,
                "processing_phases": processing_phases,
                "debug_info": debug_info
            }
            
        except Exception as e:
            logger.error(f"Error processing diary chat message: {e}", exc_info=True)
            return {
                "response": "I'm sorry, I encountered an error while processing your message. Please try again.",
                "tool_calls_made": [],
                "search_queries_used": [],
                "tool_feedback": None,
                "processing_phases": [{"phase": "error", "message": "Error processing message"}],
                "error": str(e)
            }
    
    def get_random_search_feedback(self) -> str:
        """Get a random search feedback message."""
        import random
        return random.choice(self.search_feedback_messages)
    
    def get_random_greeting(self) -> str:
        """Get a random greeting message for modal initialization."""
        import random
        return random.choice(self.greeting_variants)


# Global diary chat service instance
_diary_chat_service: Optional[DiaryChatService] = None


def get_diary_chat_service() -> DiaryChatService:
    """Get the global diary chat service instance."""
    global _diary_chat_service
    if _diary_chat_service is None:
        _diary_chat_service = DiaryChatService()
    return _diary_chat_service


def invalidate_diary_cache():
    """No-op function kept for compatibility with other code that calls it."""
    # Caching has been completely removed for real-time accuracy
    # This function is kept to avoid breaking other code that might call it
    pass