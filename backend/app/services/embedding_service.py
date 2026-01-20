"""
Embedding Service for generating and managing text embeddings using BGE-small-en-v1.5 model.

This service handles:
- Loading and managing the BGE-small-en-v1.5 embedding model
- Generating embeddings for text content with caching
- Batch processing capabilities
- Cosine similarity calculations for semantic search
"""

import json
import logging
import asyncio
from typing import List, Dict, Optional, Union, Tuple
from functools import lru_cache
import numpy as np
import torch
from sentence_transformers import SentenceTransformer, util

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Service for generating text embeddings using BGE-small-en-v1.5 model."""
    
    def __init__(self, model_name: str = "BAAI/bge-small-en-v1.5", device: Optional[str] = None):
        """
        Initialize the embedding service.
        
        Args:
            model_name: The name of the embedding model to use
            device: Device to run the model on ('cuda', 'mps', 'cpu')
        """
        self.model_name = model_name
        self.device = device or self._get_best_device()
        self.model: Optional[SentenceTransformer] = None
        self.embedding_dimension = 384  # BGE-small-en-v1.5 produces 384-dimensional embeddings
        self._model_loading_lock = asyncio.Lock()
        
        logger.info(f"Initializing EmbeddingService with model: {model_name} on device: {self.device}")
    
    def _get_best_device(self) -> str:
        """Determine the best available device for the model."""
        if torch.cuda.is_available():
            return "cuda"
        elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
            return "mps"
        else:
            return "cpu"
    
    def _format_text_for_bge(self, text: str, is_query: bool) -> str:
        """
        Apply BGE-specific prompt formatting for optimal embedding quality.
        Based on official FlagEmbedding documentation.
        
        Args:
            text: The text to format
            is_query: Whether this is a search query or document
            
        Returns:
            Formatted text with BGE-specific prompt
        """
        if is_query:
            # Official BGE query format for bge-small-en-v1.5
            formatted = f"Represent this sentence for searching relevant passages: {text}"
            logger.debug(f"BGE Query formatting applied: '{text[:50]}...' -> '{formatted[:80]}...'")
            return formatted
        else:
            # Documents don't need prefix in BGE - return raw text
            logger.debug(f"BGE Document (no formatting): '{text[:50]}...'")
            return text
    
    async def _ensure_model_loaded(self) -> None:
        """Ensure the embedding model is loaded (lazy loading)."""
        if self.model is None:
            async with self._model_loading_lock:
                if self.model is None:  # Double-check after acquiring lock
                    logger.info(f"Loading embedding model: {self.model_name}")
                    try:
                        # Run model loading in thread pool to avoid blocking
                        loop = asyncio.get_event_loop()
                        self.model = await loop.run_in_executor(
                            None, 
                            self._load_model
                        )
                        logger.info(f"Successfully loaded embedding model on {self.device}")
                    except Exception as e:
                        logger.error(f"Failed to load embedding model: {e}")
                        raise RuntimeError(f"Failed to load embedding model: {e}")
    
    def _load_model(self) -> SentenceTransformer:
        """Load the sentence transformer model (blocking operation)."""
        try:
            model = SentenceTransformer(self.model_name, device=self.device)
            # Verify the model produces expected embedding dimensions
            test_embedding = model.encode("test", convert_to_numpy=True)
            actual_dim = test_embedding.shape[0] if len(test_embedding.shape) == 1 else test_embedding.shape[-1]
            
            if actual_dim != self.embedding_dimension:
                logger.warning(f"Model produces {actual_dim}D embeddings, expected {self.embedding_dimension}D")
                self.embedding_dimension = actual_dim
            
            return model
        except Exception as e:
            logger.error(f"Error loading model {self.model_name}: {e}")
            raise
    
    async def generate_embedding(self, text: str, normalize: bool = True, is_query: bool = False) -> List[float]:
        """
        Generate embedding for a single text with BGE-specific prompt formatting.
        
        Args:
            text: Input text to embed
            normalize: Whether to normalize the embedding vector
            is_query: Whether this is a search query (True) or document (False)
            
        Returns:
            List of float values representing the embedding
        """
        if not text or not text.strip():
            logger.warning("Empty text provided for embedding generation")
            return [0.0] * self.embedding_dimension
        
        await self._ensure_model_loaded()
        
        try:
            # Apply BGE-specific prompt formatting
            formatted_text = self._format_text_for_bge(text.strip(), is_query)
            
            # Run embedding generation in thread pool
            loop = asyncio.get_event_loop()
            embedding = await loop.run_in_executor(
                None,
                self._generate_single_embedding,
                formatted_text,
                normalize
            )
            return embedding.tolist()
        
        except Exception as e:
            logger.error(f"Error generating embedding for text: {text[:100]}... Error: {e}")
            # Return zero vector as fallback
            return [0.0] * self.embedding_dimension
    
    def _generate_single_embedding(self, text: str, normalize: bool) -> np.ndarray:
        """Generate embedding for a single text (blocking operation)."""
        embedding = self.model.encode(
            text,
            convert_to_tensor=True,
            normalize_embeddings=normalize,
            show_progress_bar=False
        )
        # Convert tensor to numpy for consistent return type
        return embedding.cpu().numpy()
    
    async def generate_embeddings_batch(
        self, 
        texts: List[str], 
        batch_size: int = 32,
        normalize: bool = True,
        is_query: bool = False
    ) -> List[List[float]]:
        """
        Generate embeddings for multiple texts efficiently with BGE formatting.
        
        Args:
            texts: List of texts to embed
            batch_size: Number of texts to process in each batch
            normalize: Whether to normalize the embedding vectors
            is_query: Whether these are search queries or documents
            
        Returns:
            List of embeddings, each as a list of floats
        """
        if not texts:
            return []
        
        # Filter out empty texts, apply BGE formatting, and keep track of original indices
        formatted_texts = []
        text_indices = []
        
        for i, text in enumerate(texts):
            if text and text.strip():
                formatted_text = self._format_text_for_bge(text.strip(), is_query)
                formatted_texts.append(formatted_text)
                text_indices.append(i)
        
        if not formatted_texts:
            logger.warning("All provided texts are empty")
            return [[0.0] * self.embedding_dimension] * len(texts)
        
        await self._ensure_model_loaded()
        
        try:
            # Run batch embedding generation in thread pool
            loop = asyncio.get_event_loop()
            embeddings = await loop.run_in_executor(
                None,
                self._generate_batch_embeddings,
                formatted_texts,
                batch_size,
                normalize
            )
            
            # Map embeddings back to original positions
            result = [[0.0] * self.embedding_dimension] * len(texts)
            for i, embedding in enumerate(embeddings):
                original_index = text_indices[i]
                result[original_index] = embedding.tolist()
            
            return result
        
        except Exception as e:
            logger.error(f"Error generating batch embeddings: {e}")
            # Return zero vectors as fallback
            return [[0.0] * self.embedding_dimension] * len(texts)
    
    def _generate_batch_embeddings(
        self, 
        texts: List[str], 
        batch_size: int, 
        normalize: bool
    ) -> np.ndarray:
        """Generate embeddings for multiple texts (blocking operation)."""
        embeddings = self.model.encode(
            texts,
            batch_size=batch_size,
            convert_to_tensor=True,
            normalize_embeddings=normalize,
            show_progress_bar=len(texts) > 100  # Show progress for large batches
        )
        # Convert tensor to numpy for consistent return type
        return embeddings.cpu().numpy()
    
    @staticmethod
    def cosine_similarity(embedding1: List[float], embedding2: List[float]) -> float:
        """
        Calculate cosine similarity between two embeddings.
        
        Args:
            embedding1: First embedding vector
            embedding2: Second embedding vector
            
        Returns:
            Cosine similarity score (-1 to 1)
        """
        try:
            # Convert to tensors for computation
            emb1 = torch.tensor(embedding1, dtype=torch.float32)
            emb2 = torch.tensor(embedding2, dtype=torch.float32)
            
            # Calculate cosine similarity using sentence-transformers utility
            similarity = util.cos_sim(emb1, emb2)
            return float(similarity.item())
        
        except Exception as e:
            logger.error(f"Error calculating cosine similarity: {e}")
            return 0.0
    
    @staticmethod
    def cosine_similarity_batch(
        embeddings1: List[List[float]], 
        embeddings2: List[List[float]]
    ) -> np.ndarray:
        """
        Calculate cosine similarities between two sets of embeddings.
        
        Args:
            embeddings1: First set of embedding vectors
            embeddings2: Second set of embedding vectors
            
        Returns:
            2D numpy array of similarity scores
        """
        try:
            # Convert to tensors
            emb1_tensor = torch.tensor(embeddings1, dtype=torch.float32)
            emb2_tensor = torch.tensor(embeddings2, dtype=torch.float32)
            
            # Calculate cosine similarity matrix using sentence-transformers utility
            similarities = util.cos_sim(emb1_tensor, emb2_tensor)
            return similarities.numpy()
        
        except Exception as e:
            logger.error(f"Error calculating batch cosine similarities: {e}")
            return np.zeros((len(embeddings1), len(embeddings2)))
    
    def search_similar_embeddings(
        self, 
        query_embedding: List[float], 
        candidate_embeddings: List[List[float]], 
        top_k: int = 5,
        similarity_threshold: float = 0.0
    ) -> List[Tuple[int, float]]:
        """
        Search for most similar embeddings to a query embedding.
        
        Args:
            query_embedding: The query embedding to match against
            candidate_embeddings: List of candidate embeddings to search
            top_k: Number of top results to return
            similarity_threshold: Minimum similarity threshold
            
        Returns:
            List of tuples (index, similarity_score) sorted by similarity descending
        """
        if not candidate_embeddings:
            return []
        
        try:
            # Calculate similarities
            similarities = self.cosine_similarity_batch(
                [query_embedding], 
                candidate_embeddings
            )[0]  # Take first row since query is single embedding
            
            # Create list of (index, similarity) pairs
            indexed_similarities = [
                (i, float(sim)) for i, sim in enumerate(similarities)
                if sim >= similarity_threshold
            ]
            
            # Sort by similarity descending and take top_k
            indexed_similarities.sort(key=lambda x: x[1], reverse=True)
            return indexed_similarities[:top_k]
        
        except Exception as e:
            logger.error(f"Error searching similar embeddings: {e}")
            return []
    
    async def get_model_info(self) -> Dict[str, Union[str, int]]:
        """
        Get information about the loaded model.
        
        Returns:
            Dictionary with model information
        """
        await self._ensure_model_loaded()
        
        return {
            "model_name": self.model_name,
            "device": self.device,
            "embedding_dimension": self.embedding_dimension,
            "max_seq_length": getattr(self.model, 'max_seq_length', 512)
        }
    
    @staticmethod
    def serialize_embedding(embedding: List[float]) -> str:
        """
        Serialize embedding to JSON string for database storage.
        
        Args:
            embedding: List of float values
            
        Returns:
            JSON string representation
        """
        try:
            return json.dumps(embedding)
        except Exception as e:
            logger.error(f"Error serializing embedding: {e}")
            return "[]"
    
    @staticmethod
    def deserialize_embedding(embedding_json: str) -> List[float]:
        """
        Deserialize embedding from JSON string.
        
        Args:
            embedding_json: JSON string representation
            
        Returns:
            List of float values
        """
        try:
            embedding = json.loads(embedding_json)
            if isinstance(embedding, list) and all(isinstance(x, (int, float)) for x in embedding):
                return [float(x) for x in embedding]
            else:
                logger.warning(f"Invalid embedding format in JSON: {embedding_json[:100]}")
                return []
        except (json.JSONDecodeError, TypeError) as e:
            logger.error(f"Error deserializing embedding: {e}")
            return []


# Global embedding service instance
_embedding_service: Optional[EmbeddingService] = None


def get_embedding_service() -> EmbeddingService:
    """Get the global embedding service instance."""
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service


async def initialize_embedding_service() -> None:
    """Initialize the embedding service (preload model)."""
    service = get_embedding_service()
    await service._ensure_model_loaded()
    logger.info("Embedding service initialized successfully")