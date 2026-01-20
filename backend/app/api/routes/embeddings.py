"""
API endpoints for embedding generation and management.

This module provides endpoints for:
- Generating embeddings for single text or batch of texts
- Getting embedding model information
- Similarity search functionality
"""

import logging
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field

from app.api.schemas import SuccessResponse, ErrorResponse
from app.services.embedding_service import get_embedding_service, EmbeddingService
from app.services.hybrid_search import HybridSearchService
from app.db.repositories.entry_repository import EntryRepository
from app.db.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/embeddings", tags=["embeddings"])


# Request Models
class EmbeddingGenerateRequest(BaseModel):
    """Request model for generating a single embedding."""
    text: str = Field(..., min_length=1, max_length=10000, description="Text to generate embedding for")
    normalize: bool = Field(True, description="Whether to normalize the embedding vector")


class EmbeddingBatchRequest(BaseModel):
    """Request model for generating multiple embeddings."""
    texts: List[str] = Field(..., min_items=1, max_items=100, description="List of texts to generate embeddings for")
    batch_size: int = Field(32, ge=1, le=128, description="Batch size for processing")
    normalize: bool = Field(True, description="Whether to normalize the embedding vectors")


class SimilaritySearchRequest(BaseModel):
    """Request model for similarity search."""
    query_embedding: List[float] = Field(..., min_items=1, description="Query embedding vector")
    candidate_embeddings: List[List[float]] = Field(..., min_items=1, max_items=1000, description="Candidate embeddings to search")
    top_k: int = Field(5, ge=1, le=50, description="Number of top results to return")
    similarity_threshold: float = Field(0.0, ge=-1.0, le=1.0, description="Minimum similarity threshold")


class CosineSimilarityRequest(BaseModel):
    """Request model for calculating cosine similarity between two embeddings."""
    embedding1: List[float] = Field(..., min_items=1, description="First embedding vector")
    embedding2: List[float] = Field(..., min_items=1, description="Second embedding vector")


# Response Models
class EmbeddingGenerateResponse(BaseModel):
    """Response model for single embedding generation."""
    embedding: List[float] = Field(..., description="Generated embedding vector")
    dimension: int = Field(..., description="Dimension of the embedding")


class EmbeddingBatchResponse(BaseModel):
    """Response model for batch embedding generation."""
    embeddings: List[List[float]] = Field(..., description="Generated embedding vectors")
    count: int = Field(..., description="Number of embeddings generated")
    dimension: int = Field(..., description="Dimension of each embedding")


class SimilaritySearchResponse(BaseModel):
    """Response model for similarity search results."""
    results: List[Dict[str, Any]] = Field(..., description="Similarity search results")
    count: int = Field(..., description="Number of results returned")


class CosineSimilarityResponse(BaseModel):
    """Response model for cosine similarity calculation."""
    similarity: float = Field(..., description="Cosine similarity score")


class ModelInfoResponse(BaseModel):
    """Response model for embedding model information."""
    model_name: str = Field(..., description="Name of the embedding model")
    device: str = Field(..., description="Device the model is running on")
    embedding_dimension: int = Field(..., description="Dimension of embeddings produced")
    max_seq_length: int = Field(..., description="Maximum sequence length supported")


class BatchProcessingRequest(BaseModel):
    """Request model for batch processing existing entries."""
    batch_size: int = Field(50, ge=1, le=100, description="Number of entries to process in each batch")
    max_entries: Optional[int] = Field(None, ge=1, description="Maximum number of entries to process (None for all)")


class BatchProcessingStatusResponse(BaseModel):
    """Response model for batch processing status."""
    total_entries: int = Field(..., description="Total number of entries in database")
    entries_with_embeddings: int = Field(..., description="Number of entries that already have embeddings")
    entries_without_embeddings: int = Field(..., description="Number of entries that need embeddings")
    processing_started: bool = Field(..., description="Whether batch processing has been started")


class SemanticSearchRequest(BaseModel):
    """Request model for semantic search."""
    query: str = Field(..., min_length=1, max_length=1000, description="Text query to search for")
    limit: int = Field(10, ge=1, le=50, description="Maximum number of results to return")
    similarity_threshold: float = Field(0.3, ge=0.0, le=1.0, description="Minimum similarity threshold")
    date_range: Optional[Dict[str, str]] = Field(None, description="Optional date filtering with 'start_date' and 'end_date' in ISO format")
    mood_tags: Optional[List[str]] = Field(None, description="Optional mood tag filtering")


class SimilarEntriesRequest(BaseModel):
    """Request model for finding similar entries to a given entry."""
    entry_id: int = Field(..., description="ID of the entry to find similar entries for")
    limit: int = Field(10, ge=1, le=50, description="Maximum number of results to return")
    similarity_threshold: float = Field(0.3, ge=0.0, le=1.0, description="Minimum similarity threshold")


class EntrySearchResult(BaseModel):
    """Model for entry search result."""
    entry_id: int = Field(..., description="ID of the entry")
    similarity: float = Field(..., description="Similarity score")
    title: str = Field(..., description="Entry title or preview")
    content: str = Field(..., description="Entry content preview")
    timestamp: str = Field(..., description="Entry timestamp")
    mode: str = Field(..., description="Entry processing mode")


class SemanticSearchResponse(BaseModel):
    """Response model for semantic search results."""
    query: str = Field(..., description="Original search query")
    results: List[EntrySearchResult] = Field(..., description="Search results")
    count: int = Field(..., description="Number of results returned")
    total_searchable_entries: int = Field(..., description="Total number of entries with embeddings")
    filters_applied: Optional[Dict[str, Any]] = Field(None, description="Metadata about applied filters")


@router.post("/generate", response_model=SuccessResponse[EmbeddingGenerateResponse])
async def generate_embedding(request: EmbeddingGenerateRequest):
    """
    Generate embedding for a single text.
    
    Args:
        request: Request containing text and options
        
    Returns:
        Generated embedding vector with metadata
        
    Raises:
        HTTPException: If embedding generation fails
    """
    try:
        embedding_service = get_embedding_service()
        
        # Generate embedding
        embedding = await embedding_service.generate_embedding(
            text=request.text,
            normalize=request.normalize
        )
        
        response_data = EmbeddingGenerateResponse(
            embedding=embedding,
            dimension=len(embedding)
        )
        
        return SuccessResponse(
            success=True,
            message="Embedding generated successfully",
            data=response_data
        )
        
    except Exception as e:
        logger.error(f"Error generating embedding: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate embedding: {str(e)}"
        )


@router.post("/batch", response_model=SuccessResponse[EmbeddingBatchResponse])
async def generate_embeddings_batch(request: EmbeddingBatchRequest):
    """
    Generate embeddings for multiple texts efficiently.
    
    Args:
        request: Request containing texts and options
        
    Returns:
        Generated embedding vectors with metadata
        
    Raises:
        HTTPException: If batch processing fails
    """
    try:
        embedding_service = get_embedding_service()
        
        # Generate embeddings in batch
        embeddings = await embedding_service.generate_embeddings_batch(
            texts=request.texts,
            batch_size=request.batch_size,
            normalize=request.normalize
        )
        
        response_data = EmbeddingBatchResponse(
            embeddings=embeddings,
            count=len(embeddings),
            dimension=len(embeddings[0]) if embeddings else 0
        )
        
        return SuccessResponse(
            success=True,
            message=f"Generated {len(embeddings)} embeddings successfully",
            data=response_data
        )
        
    except Exception as e:
        logger.error(f"Error generating batch embeddings: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate batch embeddings: {str(e)}"
        )


@router.post("/similarity", response_model=SuccessResponse[CosineSimilarityResponse])
async def calculate_cosine_similarity(request: CosineSimilarityRequest):
    """
    Calculate cosine similarity between two embeddings.
    
    Args:
        request: Request containing two embedding vectors
        
    Returns:
        Cosine similarity score
        
    Raises:
        HTTPException: If similarity calculation fails
    """
    try:
        # Validate embedding dimensions match
        if len(request.embedding1) != len(request.embedding2):
            raise HTTPException(
                status_code=400,
                detail=f"Embedding dimensions don't match: {len(request.embedding1)} vs {len(request.embedding2)}"
            )
        
        embedding_service = get_embedding_service()
        
        # Calculate cosine similarity
        similarity = embedding_service.cosine_similarity(
            request.embedding1,
            request.embedding2
        )
        
        response_data = CosineSimilarityResponse(similarity=similarity)
        
        return SuccessResponse(
            success=True,
            message="Cosine similarity calculated successfully",
            data=response_data
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error calculating cosine similarity: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to calculate cosine similarity: {str(e)}"
        )


@router.post("/search", response_model=SuccessResponse[SimilaritySearchResponse])
async def similarity_search(request: SimilaritySearchRequest):
    """
    Search for most similar embeddings to a query embedding.
    
    Args:
        request: Request containing query embedding and candidates
        
    Returns:
        List of most similar embeddings with similarity scores
        
    Raises:
        HTTPException: If similarity search fails
    """
    try:
        embedding_service = get_embedding_service()
        
        # Validate embedding dimensions
        query_dim = len(request.query_embedding)
        for i, candidate in enumerate(request.candidate_embeddings):
            if len(candidate) != query_dim:
                raise HTTPException(
                    status_code=400,
                    detail=f"Candidate embedding {i} dimension ({len(candidate)}) doesn't match query dimension ({query_dim})"
                )
        
        # Perform similarity search
        results = embedding_service.search_similar_embeddings(
            query_embedding=request.query_embedding,
            candidate_embeddings=request.candidate_embeddings,
            top_k=request.top_k,
            similarity_threshold=request.similarity_threshold
        )
        
        # Format results
        formatted_results = [
            {
                "index": index,
                "similarity": similarity,
                "embedding": request.candidate_embeddings[index]
            }
            for index, similarity in results
        ]
        
        response_data = SimilaritySearchResponse(
            results=formatted_results,
            count=len(formatted_results)
        )
        
        return SuccessResponse(
            success=True,
            message=f"Found {len(formatted_results)} similar embeddings",
            data=response_data
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error performing similarity search: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to perform similarity search: {str(e)}"
        )


@router.get("/model-info", response_model=SuccessResponse[ModelInfoResponse])
async def get_model_info():
    """
    Get information about the loaded embedding model.
    
    Returns:
        Model information including name, device, and capabilities
        
    Raises:
        HTTPException: If model information retrieval fails
    """
    try:
        embedding_service = get_embedding_service()
        
        # Get model information
        model_info = await embedding_service.get_model_info()
        
        response_data = ModelInfoResponse(**model_info)
        
        return SuccessResponse(
            success=True,
            message="Model information retrieved successfully",
            data=response_data
        )
        
    except Exception as e:
        logger.error(f"Error getting model info: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get model information: {str(e)}"
        )


@router.post("/initialize")
async def initialize_embedding_model(background_tasks: BackgroundTasks):
    """
    Initialize the embedding model in the background.
    
    This endpoint triggers model loading without waiting for completion,
    useful for warming up the service.
    
    Returns:
        Success response indicating initialization started
    """
    try:
        from app.services.embedding_service import initialize_embedding_service
        
        # Add initialization to background tasks
        background_tasks.add_task(initialize_embedding_service)
        
        return SuccessResponse(
            success=True,
            message="Embedding model initialization started",
            data={"status": "initializing"}
        )
        
    except Exception as e:
        logger.error(f"Error starting model initialization: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to start model initialization: {str(e)}"
        )


@router.post("/semantic-search", response_model=SuccessResponse[SemanticSearchResponse])
async def semantic_search(request: SemanticSearchRequest):
    """
    Perform semantic search across journal entries.
    
    This endpoint generates an embedding for the search query and finds
    the most similar entries based on cosine similarity.
    
    Args:
        request: Search query and parameters
        
    Returns:
        List of similar entries with similarity scores
        
    Raises:
        HTTPException: If search fails
    """
    try:
        embedding_service = get_embedding_service()
        
        # Generate embedding for the search query with BGE query formatting
        query_embedding = await embedding_service.generate_embedding(
            text=request.query,
            normalize=True,
            is_query=True  # Mark as query for BGE formatting
        )
        
        # Extract date filtering parameters
        start_date = None
        end_date = None
        if request.date_range:
            start_date = request.date_range.get('start_date')
            end_date = request.date_range.get('end_date')
        
        # Get all entries with embeddings (with optional filtering)
        entries_with_embeddings = await EntryRepository.get_entries_with_embeddings(
            limit=1000,  # Get a large batch for comprehensive search
            start_date=start_date,
            end_date=end_date,
            mood_tags=request.mood_tags
        )
        
        # Prepare filter metadata
        filters_applied = {
            "date_range": request.date_range if request.date_range else None,
            "mood_tags": request.mood_tags if request.mood_tags else None,
            "has_filters": bool(request.date_range or request.mood_tags)
        }
        
        if not entries_with_embeddings:
            return SuccessResponse(
                success=True,
                message="No entries with embeddings found",
                data=SemanticSearchResponse(
                    query=request.query,
                    results=[],
                    count=0,
                    total_searchable_entries=0,
                    filters_applied=filters_applied
                )
            )
        
        # Extract embeddings and metadata
        candidate_embeddings = []
        entry_metadata = []
        
        for entry in entries_with_embeddings:
            if entry.embeddings and len(entry.embeddings) > 0:
                candidate_embeddings.append(entry.embeddings)
                entry_metadata.append(entry)
        
        if not candidate_embeddings:
            return SuccessResponse(
                success=True,
                message="No valid embeddings found",
                data=SemanticSearchResponse(
                    query=request.query,
                    results=[],
                    count=0,
                    total_searchable_entries=0,
                    filters_applied=filters_applied
                )
            )
        
        # Perform similarity search - get more candidates for hybrid reranking
        similar_indices = embedding_service.search_similar_embeddings(
            query_embedding=query_embedding,
            candidate_embeddings=candidate_embeddings,
            top_k=min(request.limit * 2, 100),  # Get 2x candidates for reranking
            similarity_threshold=request.similarity_threshold
        )
        
        # Prepare results for hybrid reranking
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
        
        # Apply hybrid reranking with conservative boost values
        reranked_results = HybridSearchService.rerank_search_results(
            results=initial_results,
            query=request.query,
            text_field="raw_text",
            exact_match_boost=0.2,  # Conservative 20% boost
            partial_match_boost=0.1  # Conservative 10% boost
        )
        
        # Format final results (take only requested limit)
        search_results = []
        for _, hybrid_score, entry_dict in reranked_results[:request.limit]:
            # Get original entry object for title generation
            entry = next(e for e in entry_metadata if e.id == entry_dict["id"])
            title = _generate_entry_title(entry)
            
            # Use hybrid search to extract context around matches
            content = HybridSearchService.extract_search_context(
                text=entry.raw_text or "",
                query=request.query,
                context_length=200
            )
            
            search_results.append(EntrySearchResult(
                entry_id=entry_dict["id"],
                similarity=hybrid_score,  # Report hybrid score (capped at 1.0)
                title=title,
                content=content,
                timestamp=entry_dict["timestamp"].isoformat(),
                mode=entry_dict["mode"]
            ))
        
        response_data = SemanticSearchResponse(
            query=request.query,
            results=search_results,
            count=len(search_results),
            total_searchable_entries=len(candidate_embeddings),
            filters_applied=filters_applied
        )
        
        return SuccessResponse(
            success=True,
            message=f"Found {len(search_results)} similar entries",
            data=response_data
        )
        
    except Exception as e:
        logger.error(f"Error performing semantic search: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to perform semantic search: {str(e)}"
        )




@router.post("/similar-entries", response_model=SuccessResponse[SemanticSearchResponse])
async def find_similar_entries(request: SimilarEntriesRequest):
    """
    Find entries similar to a given entry.
    
    Uses the embedding of the specified entry to find other similar entries.
    
    Args:
        request: Entry ID and search parameters
        
    Returns:
        List of similar entries with similarity scores
        
    Raises:
        HTTPException: If search fails or entry not found
    """
    try:
        # Get the target entry
        target_entry = await EntryRepository.get_by_id(request.entry_id)
        if not target_entry:
            raise HTTPException(
                status_code=404,
                detail=f"Entry with ID {request.entry_id} not found"
            )
        
        # Check if target entry has embeddings
        if not target_entry.embeddings or len(target_entry.embeddings) == 0:
            raise HTTPException(
                status_code=400,
                detail=f"Entry {request.entry_id} does not have embeddings. Process it first."
            )
        
        # Get all other entries with embeddings (exclude the target entry)
        all_entries = await EntryRepository.get_entries_with_embeddings(limit=1000)
        entries_with_embeddings = [e for e in all_entries if e.id != request.entry_id]
        
        if not entries_with_embeddings:
            return SuccessResponse(
                success=True,
                message="No other entries with embeddings found",
                data=SemanticSearchResponse(
                    query=f"Similar to entry {request.entry_id}",
                    results=[],
                    count=0,
                    total_searchable_entries=0
                )
            )
        
        # Extract embeddings and metadata
        candidate_embeddings = []
        entry_metadata = []
        
        for entry in entries_with_embeddings:
            if entry.embeddings and len(entry.embeddings) > 0:
                candidate_embeddings.append(entry.embeddings)
                entry_metadata.append(entry)
        
        if not candidate_embeddings:
            return SuccessResponse(
                success=True,
                message="No valid embeddings found in other entries",
                data=SemanticSearchResponse(
                    query=f"Similar to entry {request.entry_id}",
                    results=[],
                    count=0,
                    total_searchable_entries=0
                )
            )
        
        # Perform similarity search
        embedding_service = get_embedding_service()
        similar_indices = embedding_service.search_similar_embeddings(
            query_embedding=target_entry.embeddings,
            candidate_embeddings=candidate_embeddings,
            top_k=request.limit,
            similarity_threshold=request.similarity_threshold
        )
        
        # Format results
        search_results = []
        for index, similarity in similar_indices:
            entry = entry_metadata[index]
            
            # Generate title and content preview
            title = _generate_entry_title(entry)
            content = _generate_entry_preview(entry)
            
            search_results.append(EntrySearchResult(
                entry_id=entry.id,
                similarity=similarity,
                title=title,
                content=content,
                timestamp=entry.timestamp.isoformat(),
                mode=entry.mode
            ))
        
        response_data = SemanticSearchResponse(
            query=f"Similar to entry {request.entry_id}",
            results=search_results,
            count=len(search_results),
            total_searchable_entries=len(candidate_embeddings)
        )
        
        return SuccessResponse(
            success=True,
            message=f"Found {len(search_results)} similar entries to entry {request.entry_id}",
            data=response_data
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error finding similar entries: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to find similar entries: {str(e)}"
        )


def _generate_entry_title(entry) -> str:
    """Generate a title for an entry (first 50 characters of content)."""
    text = ""
    
    # Try different text sources in order of preference
    if entry.raw_text and entry.raw_text.strip():
        text = entry.raw_text.strip()
    elif entry.enhanced_text and entry.enhanced_text.strip():
        text = entry.enhanced_text.strip()
    elif entry.structured_summary and entry.structured_summary.strip():
        text = entry.structured_summary.strip()
    
    if not text:
        return f"Entry {entry.id}"
    
    # Take first 50 characters and add ellipsis if longer
    if len(text) > 50:
        return text[:47] + "..."
    return text


def _generate_entry_preview(entry, max_length: int = 200) -> str:
    """Generate a content preview for an entry."""
    text = ""
    
    # Try different text sources in order of preference
    if entry.raw_text and entry.raw_text.strip():
        text = entry.raw_text.strip()
    elif entry.enhanced_text and entry.enhanced_text.strip():
        text = entry.enhanced_text.strip()
    elif entry.structured_summary and entry.structured_summary.strip():
        text = entry.structured_summary.strip()
    
    if not text:
        return "No content available"
    
    # Take first max_length characters and add ellipsis if longer
    if len(text) > max_length:
        return text[:max_length-3] + "..."
    return text


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


@router.get("/batch-status", response_model=SuccessResponse[BatchProcessingStatusResponse])
async def get_batch_processing_status():
    """
    Get the status of embeddings in the database.
    
    Returns:
        Statistics about embeddings coverage in the database
        
    Raises:
        HTTPException: If status retrieval fails
    """
    try:
        # Get embedding statistics
        total_entries = await EntryRepository.count()
        entries_with_embeddings = await EntryRepository.count_entries_with_embeddings()
        entries_without_embeddings = await EntryRepository.count_entries_without_embeddings()
        
        response_data = BatchProcessingStatusResponse(
            total_entries=total_entries,
            entries_with_embeddings=entries_with_embeddings,
            entries_without_embeddings=entries_without_embeddings,
            processing_started=False  # This would be True if a background task is running
        )
        
        return SuccessResponse(
            success=True,
            message="Batch processing status retrieved successfully",
            data=response_data
        )
        
    except Exception as e:
        logger.error(f"Error getting batch processing status: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get batch processing status: {str(e)}"
        )


@router.post("/batch-process", response_model=SuccessResponse[Dict[str, Any]])
async def start_batch_processing(
    request: BatchProcessingRequest,
    background_tasks: BackgroundTasks
):
    """
    Start batch processing to generate embeddings for existing entries.
    
    This endpoint processes entries that don't have embeddings yet in batches,
    generating embeddings based on their raw_text content.
    
    Args:
        request: Batch processing configuration
        background_tasks: FastAPI background tasks
        
    Returns:
        Success response indicating batch processing started
        
    Raises:
        HTTPException: If batch processing startup fails
    """
    try:
        # Get count of entries that need processing
        entries_without_embeddings = await EntryRepository.count_entries_without_embeddings()
        
        if entries_without_embeddings == 0:
            return SuccessResponse(
                success=True,
                message="No entries need embedding processing",
                data={
                    "entries_to_process": 0,
                    "status": "completed"
                }
            )
        
        # Determine actual number of entries to process
        max_entries = request.max_entries or entries_without_embeddings
        actual_entries_to_process = min(max_entries, entries_without_embeddings)
        
        # Add batch processing to background tasks
        background_tasks.add_task(
            _process_entries_batch,
            batch_size=request.batch_size,
            max_entries=actual_entries_to_process
        )
        
        return SuccessResponse(
            success=True,
            message=f"Batch processing started for {actual_entries_to_process} entries",
            data={
                "entries_to_process": actual_entries_to_process,
                "batch_size": request.batch_size,
                "status": "processing"
            }
        )
        
    except Exception as e:
        logger.error(f"Error starting batch processing: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to start batch processing: {str(e)}"
        )


@router.post("/regenerate-all", response_model=SuccessResponse[dict])
async def regenerate_all_embeddings(background_tasks: BackgroundTasks):
    """
    Regenerate ALL embeddings with BGE improvements.
    
    This endpoint will:
    1. Clear all existing embeddings
    2. Regenerate embeddings with proper BGE formatting
    3. Use the new text prioritization (structured > enhanced > raw)
    
    Returns:
        Status of regeneration process
    """
    try:
        db = get_db()
        logger.info("Starting complete embedding regeneration with BGE improvements")
        
        # First, synchronously clear all embeddings to ensure it happens
        logger.info("Clearing all embeddings synchronously first...")
        cleared = await EntryRepository.clear_all_embeddings()
        logger.info(f"Cleared {cleared} embeddings")
        
        # Verify they're actually cleared
        remaining = await EntryRepository.count_entries_with_embeddings()
        if remaining > 0:
            logger.warning(f"Still have {remaining} entries with embeddings after clearing!")
            # Force clear with direct database access
            await db.execute("UPDATE entries SET embeddings = NULL")
            await db.commit()
            logger.info("Force cleared all embeddings with direct SQL")
        
        # Add regeneration task to background
        logger.info("Adding regeneration task to background tasks...")
        background_tasks.add_task(_regenerate_all_embeddings_task)
        logger.info("Background task added successfully")
        
        return SuccessResponse(
            success=True,
            message="Embedding regeneration started with BGE improvements",
            data={
                "status": "started",
                "message": "All embeddings will be regenerated with proper BGE formatting",
                "estimated_time": "This may take several minutes depending on entry count",
                "embeddings_cleared": cleared
            }
        )
        
    except Exception as e:
        logger.error(f"Error starting embedding regeneration: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to start embedding regeneration: {str(e)}"
        )


@router.post("/force-clear-embeddings", response_model=SuccessResponse[dict])
async def force_clear_all_embeddings():
    """Force clear ALL embeddings immediately"""
    try:
        db = get_db()
        
        # Force clear with direct SQL
        logger.info("Force clearing ALL embeddings...")
        
        # Get count before
        before = await db.fetch_one("SELECT COUNT(*) as cnt FROM entries WHERE embeddings IS NOT NULL")
        before_count = before["cnt"] if before else 0
        
        # Clear everything
        await db.execute("UPDATE entries SET embeddings = NULL")
        await db.commit()
        
        # Verify
        after = await db.fetch_one("SELECT COUNT(*) as cnt FROM entries WHERE embeddings IS NOT NULL")
        after_count = after["cnt"] if after else 0
        
        logger.info(f"Force clear: before={before_count}, after={after_count}")
        
        return SuccessResponse(
            success=True,
            message=f"Force cleared embeddings: {before_count} -> {after_count}",
            data={
                "before": before_count,
                "after": after_count,
                "cleared": before_count - after_count
            }
        )
        
    except Exception as e:
        logger.error(f"Force clear failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to force clear: {str(e)}"
        )


@router.post("/regenerate-sync", response_model=SuccessResponse[dict])
async def regenerate_embeddings_sync():
    """Synchronous regeneration for testing - processes a few entries"""
    try:
        logger.info("Starting synchronous regeneration...")
        
        # Get entries without embeddings
        entries_without = await EntryRepository.get_entries_without_embeddings(limit=5)
        logger.info(f"Found {len(entries_without)} entries without embeddings")
        
        if not entries_without:
            return SuccessResponse(
                success=True,
                message="No entries need embedding generation",
                data={"processed": 0}
            )
        
        # Generate embeddings
        embedding_service = get_embedding_service()
        processed = 0
        
        for entry in entries_without:
            # Select best text
            text = _select_best_text_for_embedding(entry)
            if not text:
                continue
                
            logger.info(f"Generating embedding for entry {entry.id} using: '{text[:50]}...'")
            
            # Generate with BGE formatting
            embedding = await embedding_service.generate_embedding(
                text=text,
                normalize=True,
                is_query=False
            )
            
            # Update entry
            await EntryRepository.update_embedding(entry.id, embedding)
            processed += 1
            logger.info(f"Updated entry {entry.id} with {len(embedding)}D embedding")
        
        return SuccessResponse(
            success=True,
            message=f"Processed {processed} entries synchronously",
            data={
                "processed": processed,
                "total_found": len(entries_without)
            }
        )
        
    except Exception as e:
        logger.error(f"Sync regeneration failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to regenerate: {str(e)}"
        )


@router.post("/debug-search", response_model=SuccessResponse[dict])
async def debug_semantic_search(request: dict):
    """Debug semantic search - EXACT copy of main semantic search logic"""
    try:
        query = request.get("query", "")
        if not query:
            raise HTTPException(status_code=400, detail="Query is required")
        
        logger.info(f"DEBUG SEARCH for: '{query}' (using main search logic)")
        
        embedding_service = get_embedding_service()
        
        # EXACT COPY of main semantic search - Generate embedding for the search query with BGE query formatting
        query_embedding = await embedding_service.generate_embedding(
            text=query,
            normalize=True,
            is_query=True  # Mark as query for BGE formatting
        )
        
        # EXACT COPY of main semantic search - Get all entries with embeddings
        entries_with_embeddings = await EntryRepository.get_entries_with_embeddings(
            limit=1000  # Get a large batch for comprehensive search
        )
        
        if not entries_with_embeddings:
            return SuccessResponse(
                success=True,
                message="No entries with embeddings found",
                data={
                    "query": query,
                    "results": [],
                    "count": 0,
                    "total_searchable_entries": 0
                }
            )
        
        # EXACT COPY of main semantic search - Extract embeddings and metadata
        candidate_embeddings = []
        entry_metadata = []
        
        for entry in entries_with_embeddings:
            if entry.embeddings and len(entry.embeddings) > 0:
                candidate_embeddings.append(entry.embeddings)
                entry_metadata.append(entry)
        
        if not candidate_embeddings:
            return SuccessResponse(
                success=True,
                message="No valid embeddings found",
                data={
                    "query": query,
                    "results": [],
                    "count": 0,
                    "total_searchable_entries": 0
                }
            )
        
        # EXACT COPY of main semantic search - Perform similarity search with same threshold
        similar_indices = embedding_service.search_similar_embeddings(
            query_embedding=query_embedding,
            candidate_embeddings=candidate_embeddings,
            top_k=20,  # Same as main search
            similarity_threshold=0.3  # Same as main search
        )
        
        # EXACT COPY of main semantic search - Format results exactly the same way
        search_results = []
        for index, similarity in similar_indices:
            entry = entry_metadata[index]
            
            # Generate title and content preview
            title = _generate_entry_title(entry)
            content = _generate_entry_preview(entry)
            
            # Add debug info
            text_used_for_embedding = _select_best_text_for_embedding(entry)
            contains_query = query.lower() in text_used_for_embedding.lower() if text_used_for_embedding else False
            
            search_results.append({
                "entry_id": entry.id,
                "similarity": similarity,
                "title": title,
                "content": content,
                "timestamp": entry.timestamp.isoformat(),
                "mode": entry.mode,
                # Debug additions
                "text_used_for_embedding": text_used_for_embedding[:200] if text_used_for_embedding else "No text",
                "contains_query": contains_query,
                "embedding_length": len(entry.embeddings)
            })
        
        return SuccessResponse(
            success=True,
            message=f"Debug search results for '{query}' (main search logic)",
            data={
                "query": query,
                "query_embedding_dim": len(query_embedding),
                "total_searchable_entries": len(candidate_embeddings),
                "entries_checked": len(candidate_embeddings),
                "results": search_results,
                "count": len(search_results),
                # Debug summary
                "perfect_matches": [r for r in search_results if r["contains_query"]],
                "similarity_range": {
                    "min": min([r["similarity"] for r in search_results]) if search_results else 0,
                    "max": max([r["similarity"] for r in search_results]) if search_results else 0
                }
            }
        )
        
    except Exception as e:
        logger.error(f"Debug search failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Debug search failed: {str(e)}"
        )


@router.post("/fix-hiking-entries", response_model=SuccessResponse[dict])
async def fix_hiking_entries():
    """Fix the hiking entries by re-embedding them with their raw text"""
    try:
        logger.info("Fixing hiking entries...")
        
        # Get all entries
        all_entries = await EntryRepository.get_all(limit=200)
        embedding_service = get_embedding_service()
        
        fixed_entries = []
        for entry in all_entries:
            # Check if raw text has hiking but embedding text doesn't
            raw_has_hiking = entry.raw_text and "hiking" in entry.raw_text.lower()
            if raw_has_hiking:
                # Force use raw text for embedding (ignore structured summary)
                raw_text = entry.raw_text.strip()
                
                logger.info(f"Re-embedding entry {entry.id} using raw text: '{raw_text[:50]}...'")
                
                # Generate embedding using raw text
                embedding = await embedding_service.generate_embedding(
                    text=raw_text,
                    normalize=True,
                    is_query=False
                )
                
                # Update entry with new embedding
                await EntryRepository.update_embedding(entry.id, embedding)
                
                fixed_entries.append({
                    "entry_id": entry.id,
                    "text_used": raw_text[:100]
                })
        
        return SuccessResponse(
            success=True,
            message=f"Fixed {len(fixed_entries)} hiking entries",
            data={
                "fixed_entries": fixed_entries
            }
        )
        
    except Exception as e:
        logger.error(f"Failed to fix hiking entries: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fix hiking entries: {str(e)}"
        )


@router.post("/regenerate-all-raw-text", response_model=SuccessResponse[dict])
async def regenerate_all_embeddings_with_raw_text():
    """
    Regenerate ALL embeddings using ONLY raw text for reliable semantic search.
    This is the definitive fix for semantic search issues.
    """
    try:
        db = get_db()
        logger.info("Starting complete regeneration with RAW TEXT ONLY")
        
        # Step 1: Force clear ALL embeddings
        before = await db.fetch_one("SELECT COUNT(*) as cnt FROM entries WHERE embeddings IS NOT NULL")
        before_count = before["cnt"] if before else 0
        
        logger.info(f"Clearing {before_count} existing embeddings...")
        await db.execute("UPDATE entries SET embeddings = NULL")
        await db.commit()
        
        # Verify clearing worked
        after = await db.fetch_one("SELECT COUNT(*) as cnt FROM entries WHERE embeddings IS NOT NULL")
        after_count = after["cnt"] if after else 0
        logger.info(f"Embeddings cleared: {before_count} -> {after_count}")
        
        # Step 2: Get ALL entries for regeneration
        all_entries = await EntryRepository.get_all_entries_for_embedding_generation()
        logger.info(f"Found {len(all_entries)} entries to process")
        
        if not all_entries:
            return SuccessResponse(
                success=True,
                message="No entries found for regeneration",
                data={"processed": 0, "total": 0}
            )
        
        # Step 3: Regenerate embeddings using ONLY raw text
        embedding_service = get_embedding_service()
        processed = 0
        failed = 0
        
        for entry in all_entries:
            try:
                # Use ONLY raw text - guaranteed to be user's original words
                if not entry.raw_text or not entry.raw_text.strip():
                    logger.warning(f"Entry {entry.id} has no raw text, skipping")
                    failed += 1
                    continue
                
                raw_text = entry.raw_text.strip()
                logger.info(f"Processing entry {entry.id} with raw text: '{raw_text[:50]}...'")
                
                # Generate embedding with BGE document formatting
                embedding = await embedding_service.generate_embedding(
                    text=raw_text,
                    normalize=True,
                    is_query=False  # Document formatting
                )
                
                # Update entry with new embedding
                await EntryRepository.update_embedding(entry.id, embedding)
                processed += 1
                
                logger.info(f"✅ Entry {entry.id} embedded successfully ({len(embedding)}D)")
                
            except Exception as e:
                logger.error(f"❌ Failed to process entry {entry.id}: {e}")
                failed += 1
        
        logger.info(f"🎉 Regeneration complete: {processed} processed, {failed} failed")
        
        return SuccessResponse(
            success=True,
            message=f"Regenerated embeddings for {processed} entries using raw text only",
            data={
                "processed": processed,
                "failed": failed,
                "total": len(all_entries),
                "embeddings_cleared": before_count - after_count,
                "method": "raw_text_only_with_BGE"
            }
        )
        
    except Exception as e:
        logger.error(f"Regeneration failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to regenerate embeddings: {str(e)}"
        )


@router.get("/regeneration-status", response_model=SuccessResponse[dict])
async def get_regeneration_status():
    """
    Get the current status of embedding regeneration.
    
    Returns:
        Current regeneration progress and logs
    """
    global _regeneration_status
    
    return SuccessResponse(
        success=True,
        message="Regeneration status retrieved",
        data={
            "is_running": _regeneration_status["is_running"],
            "progress": _regeneration_status["progress"],
            "total": _regeneration_status["total"],
            "current_step": _regeneration_status["current_step"],
            "logs": _regeneration_status["logs"][-10:],  # Last 10 log entries
            "percentage": round((_regeneration_status["progress"] / max(_regeneration_status["total"], 1)) * 100, 1) if _regeneration_status["total"] > 0 else 0
        }
    )


@router.get("/test-embeddings", response_model=SuccessResponse[dict])
async def test_embeddings():
    """Test endpoint to check embeddings directly"""
    try:
        db = get_db()
        
        # Get raw data from database
        rows = await db.fetch_all("SELECT id, embeddings FROM entries LIMIT 5")
        
        samples = []
        for row in rows:
            embed_str = row.get("embeddings", "")
            samples.append({
                "id": row["id"],
                "embeddings_length": len(embed_str) if embed_str else 0,
                "embeddings_preview": embed_str[:100] if embed_str else "NULL",
                "is_null": embed_str is None,
                "is_empty_string": embed_str == "",
                "is_empty_array": embed_str == "[]"
            })
        
        # Count different states
        total = await db.fetch_one("SELECT COUNT(*) as cnt FROM entries")
        with_embeddings = await db.fetch_one(
            "SELECT COUNT(*) as cnt FROM entries WHERE embeddings IS NOT NULL AND embeddings != '' AND embeddings != '[]'"
        )
        null_embeddings = await db.fetch_one(
            "SELECT COUNT(*) as cnt FROM entries WHERE embeddings IS NULL"
        )
        empty_string = await db.fetch_one(
            "SELECT COUNT(*) as cnt FROM entries WHERE embeddings = ''"
        )
        empty_array = await db.fetch_one(
            "SELECT COUNT(*) as cnt FROM entries WHERE embeddings = '[]'"
        )
        
        return SuccessResponse(
            success=True,
            message="Embedding test results",
            data={
                "samples": samples,
                "counts": {
                    "total": total["cnt"] if total else 0,
                    "with_embeddings": with_embeddings["cnt"] if with_embeddings else 0,
                    "null_embeddings": null_embeddings["cnt"] if null_embeddings else 0,
                    "empty_string": empty_string["cnt"] if empty_string else 0,
                    "empty_array": empty_array["cnt"] if empty_array else 0
                }
            }
        )
        
    except Exception as e:
        logger.error(f"Test embeddings failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to test embeddings: {str(e)}"
        )


@router.get("/debug-database", response_model=SuccessResponse[dict])
async def debug_database_state():
    """
    Debug endpoint to check actual database state and embedding counts.
    """
    try:
        logger.info("Debug database state called")
        
        # Get total entries and embedding counts
        entries_with_embeddings = await EntryRepository.count_entries_with_embeddings()
        entries_without_embeddings = await EntryRepository.count_entries_without_embeddings()
        total_entries = entries_with_embeddings + entries_without_embeddings
        
        # Get a sample of entries to inspect (first 10 entries)
        all_entries = await EntryRepository.get_all_entries_for_embedding_generation()
        sample_entries = all_entries[:10] if all_entries else []
        
        # Look for a specific entry that contains "Raj" for debugging
        raj_entries = []
        for entry in all_entries:
            if entry.raw_text and "raj" in entry.raw_text.lower():
                raj_entries.append({
                    "id": entry.id,
                    "has_embeddings": bool(entry.embeddings and len(entry.embeddings) > 0),
                    "embedding_dimension": len(entry.embeddings) if entry.embeddings else 0,
                    "raw_text_snippet": entry.raw_text[:200] if entry.raw_text else None,
                    "structured_snippet": entry.structured_summary[:200] if entry.structured_summary else None,
                    "selected_text": _select_best_text_for_embedding(entry)[:200] if _select_best_text_for_embedding(entry) else None
                })
        
        debug_info = {
            "total_entries": total_entries,
            "entries_with_embeddings": entries_with_embeddings,
            "entries_without_embeddings": entries_without_embeddings,
            "regeneration_status": {
                "is_running": _regeneration_status["is_running"],
                "progress": _regeneration_status["progress"],
                "total": _regeneration_status["total"],
                "current_step": _regeneration_status["current_step"]
            },
            "raj_entries_found": len(raj_entries),
            "raj_entries": raj_entries[:3],  # First 3 Raj entries
            "sample_entries": []
        }
        
        for entry in sample_entries:
            embedding_info = {
                "id": entry.id,
                "has_raw": bool(entry.raw_text),
                "has_enhanced": bool(entry.enhanced_text),
                "has_structured": bool(entry.structured_summary),
                "has_embeddings": bool(entry.embeddings and len(entry.embeddings) > 0),
                "embedding_dimension": len(entry.embeddings) if entry.embeddings else 0,
                "best_text_for_embedding": _select_best_text_for_embedding(entry)[:100] + "..." if _select_best_text_for_embedding(entry) else None
            }
            debug_info["sample_entries"].append(embedding_info)
        
        logger.info(f"Debug completed: Found {total_entries} total entries, {entries_with_embeddings} with embeddings, {len(raj_entries)} containing 'Raj'")
        
        return SuccessResponse(
            success=True,
            message="Database debug information retrieved",
            data=debug_info
        )
        
    except Exception as e:
        logger.error(f"Error getting debug info: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get debug information: {str(e)}"
        )


# Global status tracking for regeneration
_regeneration_status = {
    "is_running": False,
    "progress": 0,
    "total": 0,
    "current_step": "",
    "logs": []
}

def _add_regeneration_log(message: str):
    """Add a log message to regeneration status"""
    global _regeneration_status
    logger.info(message)
    _regeneration_status["logs"].append(f"{datetime.now().strftime('%H:%M:%S')} - {message}")
    # Keep only last 50 log entries
    if len(_regeneration_status["logs"]) > 50:
        _regeneration_status["logs"] = _regeneration_status["logs"][-50:]

async def _regenerate_all_embeddings_task():
    """
    Background task to regenerate ALL embeddings with BGE improvements.
    """
    global _regeneration_status
    
    try:
        db = get_db()
        logger.info("🚀 REGENERATION TASK STARTED")
        _regeneration_status["is_running"] = True
        _regeneration_status["progress"] = 0
        _regeneration_status["logs"] = []
        
        _add_regeneration_log("🔄 Starting complete embedding regeneration...")
        logger.info("Added first log entry")
        
        # Add a small delay to ensure the status is updated
        await asyncio.sleep(1)
        logger.info("After initial delay")
        
        # Step 1: Verify embeddings are cleared (should be done in the endpoint)
        _regeneration_status["current_step"] = "Verifying embeddings are cleared"
        _add_regeneration_log("Step 1: Verifying embeddings are cleared...")
        
        # Check if embeddings were cleared
        remaining = await EntryRepository.count_entries_with_embeddings()
        if remaining > 0:
            _add_regeneration_log(f"⚠️ WARNING: {remaining} entries still have embeddings!")
            _add_regeneration_log("Attempting to clear again...")
            # Try again with direct SQL
            await db.execute("UPDATE entries SET embeddings = NULL")
            await db.commit()
            _add_regeneration_log("Force cleared all embeddings with direct SQL")
            
            # Verify again
            remaining = await EntryRepository.count_entries_with_embeddings()
            _add_regeneration_log(f"After force clear: {remaining} entries with embeddings")
        else:
            _add_regeneration_log("✅ All embeddings successfully cleared")
        
        # Add delay to ensure database is synced
        await asyncio.sleep(1)
        
        # Step 2: Get all entries for regeneration
        _regeneration_status["current_step"] = "Fetching entries"
        _add_regeneration_log("Step 2: Fetching all entries for regeneration...")
        all_entries = await EntryRepository.get_all_entries_for_embedding_generation()
        _add_regeneration_log(f"Found {len(all_entries)} entries to process")
        
        if not all_entries:
            _add_regeneration_log("No entries found for regeneration")
            _regeneration_status["is_running"] = False
            return
        
        _regeneration_status["total"] = len(all_entries)
        
        # Step 3: Process entries in batches with BGE formatting
        _regeneration_status["current_step"] = "Generating embeddings"
        embedding_service = get_embedding_service()
        batch_size = 32
        successful = 0
        failed = 0
        
        for i in range(0, len(all_entries), batch_size):
            batch = all_entries[i:i + batch_size]
            batch_num = i//batch_size + 1
            total_batches = (len(all_entries) + batch_size - 1)//batch_size
            
            _add_regeneration_log(f"Processing batch {batch_num}/{total_batches}")
            
            # Prepare texts and entry IDs for batch processing
            texts = []
            entry_ids = []
            
            for entry in batch:
                text = _select_best_text_for_embedding(entry)
                if text:
                    texts.append(text)
                    entry_ids.append(entry.id)
            
            if not texts:
                _add_regeneration_log(f"No valid texts found in batch of {len(batch)} entries")
                continue
            
            # Generate embeddings for the batch with BGE document formatting
            _add_regeneration_log(f"Generating embeddings for {len(texts)} entries with BGE formatting...")
            embeddings = await embedding_service.generate_embeddings_batch(
                texts=texts,
                batch_size=min(32, len(texts)),
                normalize=True,
                is_query=False  # Documents, not queries
            )
            _add_regeneration_log(f"Generated {len(embeddings)} embeddings, updating database...")
            
            # Update entries with their new embeddings
            for entry_id, embedding in zip(entry_ids, embeddings):
                try:
                    await EntryRepository.update_embedding(entry_id, embedding)
                    successful += 1
                    _regeneration_status["progress"] = successful
                    if successful % 10 == 0:  # Log every 10 successful updates
                        _add_regeneration_log(f"Successfully updated {successful} entries so far...")
                except Exception as e:
                    failed += 1
                    _add_regeneration_log(f"Failed to update embedding for entry {entry_id}: {e}")
            
            # Add delay between batches to prevent overwhelming the system
            await asyncio.sleep(0.5)
        
        _regeneration_status["current_step"] = "Completed"
        _add_regeneration_log(f"🎉 Embedding regeneration completed!")
        _add_regeneration_log(f"✅ Successfully regenerated: {successful} entries")
        _add_regeneration_log(f"❌ Failed: {failed} entries")
        _add_regeneration_log(f"📊 Total processed: {successful + failed} entries")
        
    except Exception as e:
        _add_regeneration_log(f"❌ Error in embedding regeneration task: {e}")
    finally:
        _regeneration_status["is_running"] = False


async def _process_entries_batch(batch_size: int, max_entries: int):
    """
    Background task to process entries and generate embeddings.
    
    Args:
        batch_size: Number of entries to process in each batch
        max_entries: Maximum number of entries to process
    """
    try:
        embedding_service = get_embedding_service()
        processed_count = 0
        
        logger.info(f"Starting batch processing for up to {max_entries} entries with batch size {batch_size}")
        
        while processed_count < max_entries:
            # Get next batch of entries without embeddings
            remaining = max_entries - processed_count
            current_batch_size = min(batch_size, remaining)
            
            entries = await EntryRepository.get_entries_without_embeddings(limit=current_batch_size)
            
            if not entries:
                logger.info("No more entries to process")
                break
            
            # Extract texts for batch processing
            texts = []
            entry_ids = []
            
            for entry in entries:
                # Use the best available text for embedding (structured > enhanced > raw)
                text = _select_best_text_for_embedding(entry)
                
                if text:  # Only process entries with actual content
                    texts.append(text)
                    entry_ids.append(entry.id)
            
            if not texts:
                logger.warning(f"No valid texts found in batch of {len(entries)} entries")
                processed_count += len(entries)
                continue
            
            # Generate embeddings for the batch with BGE document formatting
            logger.info(f"Processing batch of {len(texts)} entries")
            embeddings = await embedding_service.generate_embeddings_batch(
                texts=texts,
                batch_size=min(32, len(texts)),  # Internal batch size for model
                normalize=True,
                is_query=False  # Documents, not queries
            )
            
            # Update entries with their embeddings
            for i, (entry_id, embedding) in enumerate(zip(entry_ids, embeddings)):
                try:
                    await EntryRepository.update_embedding(entry_id, embedding)
                    logger.debug(f"Updated embedding for entry {entry_id}")
                except Exception as e:
                    logger.error(f"Failed to update embedding for entry {entry_id}: {e}")
            
            processed_count += len(entries)
            logger.info(f"Processed {processed_count}/{max_entries} entries")
        
        logger.info(f"Batch processing completed. Processed {processed_count} entries total.")
        
    except Exception as e:
        logger.error(f"Error in batch processing: {e}")
        raise


@router.post("/process-entry/{entry_id}")
async def process_single_entry(entry_id: int, background_tasks: BackgroundTasks):
    """
    Generate embedding for a single entry.
    
    Args:
        entry_id: ID of the entry to process
        background_tasks: FastAPI background tasks
        
    Returns:
        Success response indicating processing started
        
    Raises:
        HTTPException: If entry processing fails
    """
    try:
        # Check if entry exists
        entry = await EntryRepository.get_by_id(entry_id)
        if not entry:
            raise HTTPException(
                status_code=404,
                detail=f"Entry with ID {entry_id} not found"
            )
        
        # Check if entry already has embeddings
        if entry.embeddings and len(entry.embeddings) > 0:
            return SuccessResponse(
                success=True,
                message=f"Entry {entry_id} already has embeddings",
                data={"entry_id": entry_id, "status": "already_processed"}
            )
        
        # Add single entry processing to background tasks
        background_tasks.add_task(_process_single_entry, entry_id)
        
        return SuccessResponse(
            success=True,
            message=f"Processing started for entry {entry_id}",
            data={"entry_id": entry_id, "status": "processing"}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing single entry {entry_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process entry {entry_id}: {str(e)}"
        )


async def _process_single_entry(entry_id: int):
    """
    Background task to process a single entry and generate its embedding.
    
    Args:
        entry_id: ID of the entry to process
    """
    try:
        # Get the entry
        entry = await EntryRepository.get_by_id(entry_id)
        if not entry:
            logger.error(f"Entry {entry_id} not found during processing")
            return
        
        # Get the best available text for embedding
        text = _select_best_text_for_embedding(entry)
        
        if not text:
            logger.warning(f"Entry {entry_id} has no text content to process")
            return
        
        # Generate embedding with BGE document formatting
        embedding_service = get_embedding_service()
        embedding = await embedding_service.generate_embedding(text, normalize=True, is_query=False)
        
        # Update entry with embedding
        await EntryRepository.update_embedding(entry_id, embedding)
        
        logger.info(f"Successfully processed embedding for entry {entry_id}")
        
    except Exception as e:
        logger.error(f"Error processing entry {entry_id}: {e}")