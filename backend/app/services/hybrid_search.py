"""
Hybrid Search Service that combines semantic similarity with exact match boosting.

This service improves search results by:
1. Using semantic embeddings for conceptual similarity
2. Boosting scores for exact keyword matches
3. Ensuring entries containing search terms rank higher
4. Capping final scores at 100% (1.0)
"""

import logging
from typing import List, Tuple, Optional
import re

logger = logging.getLogger(__name__)


class HybridSearchService:
    """Service for hybrid search combining semantic and keyword matching."""
    
    @staticmethod
    def calculate_hybrid_score(
        semantic_similarity: float,
        query: str,
        text: str,
        exact_match_boost: float = 0.2,
        partial_match_boost: float = 0.1
    ) -> float:
        """
        Calculate hybrid score combining semantic similarity with keyword matching.
        
        Args:
            semantic_similarity: Base semantic similarity score (0-1)
            query: Search query
            text: Text to search in
            exact_match_boost: Boost for exact query match
            partial_match_boost: Boost for partial word matches
            
        Returns:
            Combined score capped at 1.0 (100%)
        """
        score = semantic_similarity
        
        if not text or not query:
            return min(score, 1.0)
            
        # Normalize for comparison
        query_lower = query.lower()
        text_lower = text.lower()
        
        # Exact match boost (whole query appears in text)
        if query_lower in text_lower:
            score += exact_match_boost
            logger.debug(f"Exact match found for '{query}', boosting by {exact_match_boost}")
        else:
            # Check for partial matches (individual words)
            query_words = set(query_lower.split())
            text_words = set(text_lower.split())
            
            # Calculate overlap
            matching_words = query_words.intersection(text_words)
            if matching_words:
                # Boost based on percentage of query words found
                match_ratio = len(matching_words) / len(query_words)
                partial_boost = partial_match_boost * match_ratio
                score += partial_boost
                logger.debug(f"Partial match found ({len(matching_words)}/{len(query_words)} words), boosting by {partial_boost:.3f}")
        
        # Cap at 100% (1.0)
        return min(score, 1.0)
    
    @staticmethod
    def rerank_search_results(
        results: List[Tuple[int, float, dict]],
        query: str,
        text_field: str = "raw_text",
        exact_match_boost: float = 0.2,
        partial_match_boost: float = 0.1
    ) -> List[Tuple[int, float, dict]]:
        """
        Rerank search results using hybrid scoring.
        
        Args:
            results: List of (index, similarity, entry_data) tuples
            query: Search query
            text_field: Field name containing text to search
            exact_match_boost: Boost for exact matches
            partial_match_boost: Boost for partial matches
            
        Returns:
            Reranked list of results with updated scores
        """
        reranked = []
        
        for index, similarity, entry_data in results:
            # Get text content
            text = entry_data.get(text_field, "")
            
            # Calculate hybrid score
            hybrid_score = HybridSearchService.calculate_hybrid_score(
                semantic_similarity=similarity,
                query=query,
                text=text,
                exact_match_boost=exact_match_boost,
                partial_match_boost=partial_match_boost
            )
            
            reranked.append((index, hybrid_score, entry_data))
        
        # Sort by hybrid score descending
        reranked.sort(key=lambda x: x[1], reverse=True)
        
        return reranked
    
    @staticmethod
    def extract_search_context(
        text: str,
        query: str,
        context_length: int = 150
    ) -> str:
        """
        Extract relevant context around search matches.
        
        Args:
            text: Full text
            query: Search query
            context_length: Characters to show around match
            
        Returns:
            Context snippet with query highlighted
        """
        if not text or not query:
            return text[:context_length] + "..." if len(text) > context_length else text
            
        # Find query position (case-insensitive)
        query_lower = query.lower()
        text_lower = text.lower()
        
        pos = text_lower.find(query_lower)
        
        if pos == -1:
            # Query not found, return beginning of text
            return text[:context_length] + "..." if len(text) > context_length else text
        
        # Calculate context window
        start = max(0, pos - context_length // 2)
        end = min(len(text), pos + len(query) + context_length // 2)
        
        # Extract context
        context = text[start:end]
        
        # Add ellipsis if needed
        if start > 0:
            context = "..." + context
        if end < len(text):
            context = context + "..."
            
        return context