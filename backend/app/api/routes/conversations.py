"""
Conversation API endpoints for Talk to Your Diary feature.

This module provides endpoints for:
- Creating and managing conversation sessions
- Retrieving conversation history and transcriptions
- Conversation statistics and analytics
"""

import logging
from typing import Optional, List
from datetime import datetime
from fastapi import APIRouter, HTTPException, Query, BackgroundTasks
from pydantic import BaseModel, Field

from app.api.schemas import SuccessResponse, ErrorResponse
from app.db.repositories.conversation_repository import ConversationRepository
from app.models.conversation import Conversation
from app.services.embedding_service import get_embedding_service
from app.services.ollama import get_ollama_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/conversations", tags=["conversations"])


# Request Models
class ConversationCreateRequest(BaseModel):
    """Request model for creating a new conversation."""
    conversation_type: str = Field(..., pattern="^(call|chat)$", description="Type of conversation: 'call' or 'chat'")
    transcription: str = Field(..., min_length=1, max_length=50000, description="Complete conversation transcription")
    duration: int = Field(0, ge=0, description="Conversation duration in seconds")
    message_count: int = Field(0, ge=0, description="Number of messages in the conversation")
    search_queries_used: Optional[List[str]] = Field(None, description="Search queries used during conversation")


class ConversationUpdateRequest(BaseModel):
    """Request model for updating a conversation."""
    transcription: Optional[str] = Field(None, min_length=1, max_length=50000, description="Updated transcription")
    duration: Optional[int] = Field(None, ge=0, description="Updated duration in seconds")
    message_count: Optional[int] = Field(None, ge=0, description="Updated message count")
    search_queries_used: Optional[List[str]] = Field(None, description="Updated search queries")


# Response Models
class ConversationResponse(BaseModel):
    """Response model for conversation data."""
    id: int = Field(..., description="Conversation ID")
    timestamp: str = Field(..., description="Conversation timestamp")
    duration: int = Field(..., description="Duration in seconds")
    transcription: str = Field(..., description="Complete transcription")
    conversation_type: str = Field(..., description="Type: 'call' or 'chat'")
    message_count: int = Field(..., description="Number of messages")
    search_queries_used: Optional[List[str]] = Field(None, description="Search queries used")
    created_at: str = Field(..., description="Creation timestamp")
    updated_at: Optional[str] = Field(None, description="Last update timestamp")
    embedding: Optional[str] = Field(None, description="Conversation embedding for semantic search")
    summary: Optional[str] = Field(None, description="AI-generated conversation summary")
    key_topics: Optional[List[str]] = Field(None, description="Key topics extracted from conversation")


class ConversationListResponse(BaseModel):
    """Response model for conversation list."""
    conversations: List[ConversationResponse] = Field(..., description="List of conversations")
    total: int = Field(..., description="Total number of conversations")


class ConversationStatsResponse(BaseModel):
    """Response model for conversation statistics."""
    total_conversations: int = Field(..., description="Total number of conversations")
    call_conversations: int = Field(..., description="Number of call conversations")
    chat_conversations: int = Field(..., description="Number of chat conversations")
    total_duration: int = Field(..., description="Total duration in seconds")
    total_messages: int = Field(..., description="Total message count")
    average_duration: float = Field(..., description="Average conversation duration")
    average_messages: float = Field(..., description="Average messages per conversation")
    most_recent: Optional[str] = Field(None, description="Most recent conversation timestamp")


@router.post("", response_model=SuccessResponse[ConversationResponse])
async def create_conversation(
    request: ConversationCreateRequest,
    background_tasks: BackgroundTasks
):
    """
    Create a new conversation record with automatic processing.
    
    This endpoint:
    1. Saves the conversation to database
    2. Generates embeddings for semantic search
    3. Creates AI summary using ollama_model preferences
    4. Extracts key topics
    5. Extracts memories for the memory system
    
    Args:
        request: Conversation creation data
        background_tasks: FastAPI background tasks for async processing
        
    Returns:
        Created conversation with assigned ID
        
    Raises:
        HTTPException: If creation fails
    """
    try:
        # Create conversation object
        conversation = Conversation(
            timestamp=datetime.now(),
            duration=request.duration,
            transcription=request.transcription,
            conversation_type=request.conversation_type,
            message_count=request.message_count,
            search_queries_used=request.search_queries_used or [],
            created_at=datetime.now()
        )
        
        # Save to database
        created_conversation = await ConversationRepository.create(conversation)
        
        # Queue background processing - separate tasks for each operation
        background_tasks.add_task(
            _generate_conversation_embedding,
            created_conversation.id,
            created_conversation.transcription
        )
        background_tasks.add_task(
            _generate_conversation_summary,
            created_conversation.id,
            created_conversation.transcription
        )
        background_tasks.add_task(
            _extract_conversation_memories,
            created_conversation.id,
            created_conversation.transcription
        )
        logger.info(f"Queued background processing for conversation {created_conversation.id}")
        
        # Convert to response format
        response_data = ConversationResponse(
            id=created_conversation.id,
            timestamp=created_conversation.timestamp.isoformat(),
            duration=created_conversation.duration,
            transcription=created_conversation.transcription,
            conversation_type=created_conversation.conversation_type,
            message_count=created_conversation.message_count,
            search_queries_used=created_conversation.search_queries_used,
            created_at=created_conversation.created_at.isoformat(),
            updated_at=created_conversation.updated_at.isoformat() if created_conversation.updated_at else None,
            embedding=getattr(created_conversation, 'embedding', None),
            summary=getattr(created_conversation, 'summary', None),
            key_topics=getattr(created_conversation, 'key_topics', None)
        )
        
        return SuccessResponse(
            success=True,
            message=f"Conversation created and queued for processing",
            data=response_data
        )
        
    except ValueError as e:
        logger.error(f"Invalid conversation data: {e}")
        raise HTTPException(
            status_code=400,
            detail=f"Invalid conversation data: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Failed to create conversation: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create conversation: {str(e)}"
        )


@router.get("", response_model=SuccessResponse[ConversationListResponse])
async def get_conversations(
    limit: int = Query(50, ge=1, le=200, description="Maximum number of conversations to return"),
    offset: int = Query(0, ge=0, description="Number of conversations to skip"),
    conversation_type: Optional[str] = Query(None, regex="^(call|chat)$", description="Filter by conversation type")
):
    """
    Retrieve conversations with pagination and filtering.
    
    Args:
        limit: Maximum number of results
        offset: Number of results to skip
        conversation_type: Optional filter by type
        
    Returns:
        List of conversations matching criteria
        
    Raises:
        HTTPException: If retrieval fails
    """
    try:
        # Retrieve conversations from database
        conversations = await ConversationRepository.get_all(
            limit=limit,
            offset=offset,
            conversation_type=conversation_type
        )
        
        # Convert to response format
        response_data = []
        for conv in conversations:
            try:
                response_data.append(ConversationResponse(
                    id=conv.id,
                    timestamp=conv.timestamp.isoformat() if conv.timestamp else datetime.now().isoformat(),
                    duration=conv.duration or 0,
                    transcription=conv.transcription or "",
                    conversation_type=conv.conversation_type or "chat",
                    message_count=conv.message_count or 0,
                    search_queries_used=conv.search_queries_used or [],
                    created_at=conv.created_at.isoformat() if conv.created_at else datetime.now().isoformat(),
                    updated_at=conv.updated_at.isoformat() if conv.updated_at else None,
                    embedding=conv.embedding,
                    summary=conv.summary,
                    key_topics=conv.key_topics
                ))
            except Exception:
                # Skip problematic conversations silently
                continue
        
        return SuccessResponse(
            success=True,
            message=f"Retrieved {len(response_data)} conversations",
            data=ConversationListResponse(
                conversations=response_data,
                total=len(response_data)
            )
        )
        
    except Exception as e:
        logger.error(f"Failed to retrieve conversations: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve conversations: {str(e)}"
        )


@router.get("/{conversation_id}", response_model=SuccessResponse[ConversationResponse])
async def get_conversation(conversation_id: int):
    """
    Retrieve a specific conversation by ID.
    
    Args:
        conversation_id: Conversation ID to retrieve
        
    Returns:
        Conversation data
        
    Raises:
        HTTPException: If conversation not found or retrieval fails
    """
    try:
        conversation = await ConversationRepository.get_by_id(conversation_id)
        
        if not conversation:
            raise HTTPException(
                status_code=404,
                detail=f"Conversation with ID {conversation_id} not found"
            )
        
        response_data = ConversationResponse(
            id=conversation.id,
            timestamp=conversation.timestamp.isoformat(),
            duration=conversation.duration,
            transcription=conversation.transcription,
            conversation_type=conversation.conversation_type,
            message_count=conversation.message_count,
            search_queries_used=conversation.search_queries_used,
            created_at=conversation.created_at.isoformat(),
            updated_at=conversation.updated_at.isoformat() if conversation.updated_at else None,
            embedding=conversation.embedding,
            summary=conversation.summary,
            key_topics=conversation.key_topics
        )
        
        return SuccessResponse(
            success=True,
            message="Conversation retrieved successfully",
            data=response_data
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to retrieve conversation {conversation_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve conversation: {str(e)}"
        )


@router.put("/{conversation_id}", response_model=SuccessResponse[ConversationResponse])
async def update_conversation(conversation_id: int, request: ConversationUpdateRequest):
    """
    Update a conversation's details.
    
    Args:
        conversation_id: Conversation ID to update
        request: Updated conversation data
        
    Returns:
        Updated conversation data
        
    Raises:
        HTTPException: If conversation not found or update fails
    """
    try:
        # Check if conversation exists
        existing_conversation = await ConversationRepository.get_by_id(conversation_id)
        if not existing_conversation:
            raise HTTPException(
                status_code=404,
                detail=f"Conversation with ID {conversation_id} not found"
            )
        
        # Update conversation
        updated_conversation = await ConversationRepository.update(
            conversation_id=conversation_id,
            transcription=request.transcription,
            duration=request.duration,
            message_count=request.message_count,
            search_queries_used=request.search_queries_used
        )
        
        response_data = ConversationResponse(
            id=updated_conversation.id,
            timestamp=updated_conversation.timestamp.isoformat(),
            duration=updated_conversation.duration,
            transcription=updated_conversation.transcription,
            conversation_type=updated_conversation.conversation_type,
            message_count=updated_conversation.message_count,
            search_queries_used=updated_conversation.search_queries_used,
            created_at=updated_conversation.created_at.isoformat(),
            updated_at=updated_conversation.updated_at.isoformat() if updated_conversation.updated_at else None,
            embedding=updated_conversation.embedding,
            summary=updated_conversation.summary,
            key_topics=updated_conversation.key_topics
        )
        
        return SuccessResponse(
            success=True,
            message="Conversation updated successfully",
            data=response_data
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update conversation {conversation_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update conversation: {str(e)}"
        )


@router.delete("/{conversation_id}", response_model=SuccessResponse[dict])
async def delete_conversation(conversation_id: int):
    """
    Delete a conversation.
    
    Args:
        conversation_id: Conversation ID to delete
        
    Returns:
        Success confirmation
        
    Raises:
        HTTPException: If conversation not found or deletion fails
    """
    try:
        # Check if conversation exists
        existing_conversation = await ConversationRepository.get_by_id(conversation_id)
        if not existing_conversation:
            raise HTTPException(
                status_code=404,
                detail=f"Conversation with ID {conversation_id} not found"
            )
        
        # Delete conversation
        success = await ConversationRepository.delete(conversation_id)
        
        if not success:
            raise HTTPException(
                status_code=500,
                detail="Failed to delete conversation"
            )
        
        return SuccessResponse(
            success=True,
            message=f"Conversation {conversation_id} deleted successfully",
            data={
                "conversation_id": conversation_id,
                "deleted": True
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete conversation {conversation_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete conversation: {str(e)}"
        )


@router.get("/stats/summary", response_model=SuccessResponse[ConversationStatsResponse])
async def get_conversation_statistics():
    """
    Get conversation statistics and analytics.
    
    Returns:
        Comprehensive conversation statistics
        
    Raises:
        HTTPException: If statistics retrieval fails
    """
    try:
        stats = await ConversationRepository.get_statistics()
        
        response_data = ConversationStatsResponse(
            total_conversations=stats.get("total_conversations", 0),
            call_conversations=stats.get("call_conversations", 0),
            chat_conversations=stats.get("chat_conversations", 0),
            total_duration=stats.get("total_duration", 0),
            total_messages=stats.get("total_messages", 0),
            average_duration=stats.get("average_duration", 0.0),
            average_messages=stats.get("average_messages", 0.0),
            most_recent=stats.get("most_recent")
        )
        
        return SuccessResponse(
            success=True,
            message="Conversation statistics retrieved successfully",
            data=response_data
        )
        
    except Exception as e:
        logger.error(f"Failed to retrieve conversation statistics: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve statistics: {str(e)}"
        )


async def _generate_conversation_embedding(conversation_id: int, transcription: str):
    """Background task to generate embedding for a conversation"""
    try:
        import json
        
        logger.info(f"Generating embedding for conversation {conversation_id}")
        
        # Use the same embedding service as entries for consistency and performance
        embedding_service = get_embedding_service()
        embedding_vector = await embedding_service.generate_embedding(
            transcription.strip(), 
            normalize=True, 
            is_query=False
        )
        
        # Convert embedding to JSON exactly like entries do
        embedding_json = json.dumps(embedding_vector)
        
        # Update conversation with embedding
        await ConversationRepository.update_conversation_metadata(
            conversation_id,
            embedding=embedding_json
        )
        
        logger.info(f"Successfully generated embedding for conversation {conversation_id}")
        
    except Exception as e:
        logger.error(f"Failed to generate embedding for conversation {conversation_id}: {e}")


async def _generate_conversation_summary(conversation_id: int, transcription: str):
    """Background task to generate AI summary for a conversation"""
    try:
        from app.db.repositories.preferences_repository import PreferencesRepository
        from app.core.config import settings
        
        logger.info(f"Generating AI summary for conversation {conversation_id}")
        
        # Get same model preferences as entry processing
        model = await PreferencesRepository.get_value('ollama_model', settings.OLLAMA_DEFAULT_MODEL)
        temperature = await PreferencesRepository.get_value('ollama_temperature', 0.2)
        context_window = await PreferencesRepository.get_value('ollama_context_window', 4096)
        
        # Summary generation prompt
        system_prompt = """You are a conversation summarizer. Create a concise summary of this conversation between the user and Boo (their journal assistant). 

INSTRUCTIONS:
1. Summarize the key points discussed
2. Capture the main topics and insights
3. Keep it under 300 words
4. Focus on what was meaningful or important
5. Use a warm, personal tone as if speaking to the user

Do not include timestamps or speaker labels in your summary."""
        
        # Use async OllamaService instead of blocking requests
        ollama_service = await get_ollama_service()
        response = await ollama_service.generate(
            model=model,
            prompt=transcription,
            system=system_prompt,
            stream=False,
            temperature=float(temperature),
            num_ctx=int(context_window)
        )
        
        summary = None
        if response and hasattr(response, 'response'):
            summary = response.response.strip()
            
            # Fallback if summary is empty or too short
            if not summary or len(summary) < 20:
                logger.warning("AI generated summary too short, using fallback")
                summary = f"Conversation with {transcription.count('You:')} messages"
            else:
                logger.info(f"Generated AI summary for conversation {conversation_id} using model {model}")
        else:
            logger.error(f"Ollama API error for conversation {conversation_id}")
            summary = f"Conversation with {transcription.count('You:')} messages"
        
        # Extract key topics (simple keyword extraction)  
        important_words = ['work', 'family', 'health', 'stress', 'happy', 'sad', 
                         'anxious', 'project', 'relationship', 'goal', 'problem',
                         'success', 'failure', 'love', 'fear', 'hope', 'dream']
        
        topics = []
        text_lower = transcription.lower()
        
        for word in important_words:
            if word in text_lower:
                topics.append(word)
        
        key_topics = topics[:5]  # Limit to top 5
        
        # Update conversation with summary and key topics
        await ConversationRepository.update_conversation_metadata(
            conversation_id,
            summary=summary,
            key_topics=key_topics
        )
        
        logger.info(f"Generated summary and key topics for conversation {conversation_id}")
        
    except Exception as e:
        logger.error(f"Failed to generate summary for conversation {conversation_id}: {e}")


async def _extract_conversation_memories(conversation_id: int, transcription: str):
    """Background task to extract memories from a conversation"""
    try:
        from app.services.memory_service import MemoryService
        
        logger.info(f"Extracting memories from conversation {conversation_id}")
        
        memory_service = MemoryService()
        memory_count = await memory_service.process_conversation_for_memories(
            conversation_id,
            transcription
        )
        
        logger.info(f"Extracted {memory_count} memories from conversation {conversation_id}")
        
    except Exception as e:
        logger.error(f"Failed to extract memories from conversation {conversation_id}: {e}")