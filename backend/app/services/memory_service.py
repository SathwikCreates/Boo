"""
Memory Service for Boo

Handles extraction, storage, and retrieval of agent memories.
Three types of memory:
1. Personal facts (name, occupation, pets, relationships)
2. Preferences (communication style, likes/dislikes)
3. Habits/Patterns (behavioral patterns, routines)
"""

import json
import logging
import math
import asyncio
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
import numpy as np
from sentence_transformers import SentenceTransformer

from app.db.database import get_db
from app.db.repositories.preferences_repository import PreferencesRepository
from app.services.ollama import OllamaService
from app.core.config import settings

logger = logging.getLogger(__name__)

class MemoryService:
    def __init__(self):
        self.embedding_model = None
        self._init_embedding_model()
    
    def _init_embedding_model(self):
        """Initialize the BGE-small embedding model (same as used for entries)."""
        try:
            self.embedding_model = SentenceTransformer('BAAI/bge-small-en-v1.5')
            logger.info("Memory embedding model loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load embedding model: {e}")
            self.embedding_model = None
    
    def extract_memories_from_conversation(self, conversation_text: str, conversation_id: int) -> List[Dict[str, Any]]:
        """
        Extract memories from a conversation using LLM.
        
        This would normally use an LLM to identify:
        - Personal facts: "My name is X", "I work at Y", "I have a cat named Z"
        - Preferences: "I prefer X", "I don't like Y", "Call me Z"
        - Habits: "I usually X", "Every morning I Y"
        
        For now, using simple pattern matching as placeholder.
        """
        memories = []
        
        # Simple pattern matching for MVP (replace with LLM extraction later)
        patterns = {
            'factual': [
                (r"my name is (\w+)", "name"),
                (r"i work at (\w+)", "workplace"),
                (r"i have a (\w+) named (\w+)", "pet"),
                (r"i live in (\w+)", "location"),
                (r"i'm (\d+) years old", "age"),
            ],
            'behavioral': [
                (r"i (always|usually|often) (\w+)", "habit"),
                (r"every (morning|evening|day) i (\w+)", "routine"),
            ],
            'relational': [
                (r"my (wife|husband|partner|mom|dad|sister|brother) (\w+)", "relationship"),
            ],
            'preference': [
                (r"i (prefer|like|love) (\w+)", "preference"),
                (r"call me (\w+)", "nickname"),
                (r"i don't like (\w+)", "dislike"),
            ]
        }
        
        # For MVP, just store the raw conversation chunks that might contain memories
        # In production, this would use LLM to extract structured memories
        
        # Extract potential memory sentences
        sentences = conversation_text.split('.')
        for sentence in sentences:
            sentence = sentence.strip().lower()
            if any(keyword in sentence for keyword in ['my', 'i ', "i'm", "i've", 'prefer', 'like', 'usually']):
                # This looks like it might contain personal information
                memory = {
                    'content': sentence,
                    'memory_type': self._classify_memory_type(sentence),
                    'key_entities': self._extract_entities(sentence),
                    'source_conversation_id': conversation_id,
                    'base_importance_score': self._calculate_importance(sentence),
                    'final_importance_score': self._calculate_importance(sentence),
                    'score_source': 'rule'
                }
                memories.append(memory)
        
        return memories
    
    def _classify_memory_type(self, text: str) -> str:
        """Classify memory type based on content."""
        text_lower = text.lower()
        
        if any(word in text_lower for word in ['name', 'work', 'live', 'years old', 'have a']):
            return 'factual'
        elif any(word in text_lower for word in ['prefer', 'like', 'love', 'hate', "don't like", 'call me']):
            return 'preference'
        elif any(word in text_lower for word in ['usually', 'always', 'often', 'every']):
            return 'behavioral'
        elif any(word in text_lower for word in ['wife', 'husband', 'partner', 'mom', 'dad', 'sister', 'brother', 'friend']):
            return 'relational'
        else:
            return 'contextual'
    
    def _extract_entities(self, text: str) -> List[str]:
        """Extract key entities from text for indexing."""
        # Simple keyword extraction for MVP
        important_words = []
        keywords = ['name', 'work', 'cat', 'dog', 'pet', 'wife', 'husband', 'partner', 
                   'mom', 'dad', 'sister', 'brother', 'friend', 'job', 'company']
        
        text_lower = text.lower()
        for keyword in keywords:
            if keyword in text_lower:
                important_words.append(keyword)
        
        return important_words
    
    def _calculate_importance(self, text: str) -> float:
        """Calculate initial rule-based importance score for a memory."""
        # Rule-based scoring (2-5 range for initial scores)
        memory_type = self._classify_memory_type(text)
        
        if memory_type in ['factual', 'preference']:
            return 4.0  # Important personal info
        elif memory_type == 'relational':
            return 3.5  # Relationship info
        elif memory_type == 'behavioral':
            return 3.0  # Habits and patterns
        else:
            return 2.5  # Contextual info
    
    async def calculate_importance_with_llm(self, content: str, memory_type: str, key_entities: List[str]) -> float:
        """Calculate importance score using LLM (async)."""
        try:
            # Get preferences from database
            model = await PreferencesRepository.get_value('memory_importance_model') or \
                    await PreferencesRepository.get_value('ollama_model', settings.OLLAMA_DEFAULT_MODEL)
            temperature = await PreferencesRepository.get_value('memory_importance_temperature', 0.3)
            context_window = await PreferencesRepository.get_value('memory_importance_num_ctx', 2048)
            
            # Create prompt for importance scoring
            system_prompt = """You are a memory importance evaluator. Score the importance of personal memories on a scale of 1-10.
            
            Scoring guidelines:
            - 8-10: Critical personal facts (name, core identity, major life events)
            - 6-7: Important preferences, relationships, recurring patterns
            - 4-5: Moderate importance (occasional preferences, minor habits)
            - 2-3: Low importance (trivial facts, one-time mentions)
            - 1: Negligible (redundant or irrelevant)
            
            Respond with ONLY a number between 1 and 10."""
            
            user_prompt = f"""Memory Type: {memory_type}
            Key Entities: {', '.join(key_entities) if key_entities else 'None'}
            Content: {content}
            
            Importance Score (1-10):"""
            
            # Initialize Ollama service
            async with OllamaService() as ollama:
                response = await ollama.generate(
                    prompt=user_prompt,
                    system=system_prompt,
                    model=model,
                    temperature=temperature,
                    max_tokens=10,
                    num_ctx=context_window
                )
                
                # Parse response to get score
                try:
                    score_text = response.response.strip()
                    # Extract first number found
                    import re
                    match = re.search(r'\d+(\.\d+)?', score_text)
                    if match:
                        score = float(match.group())
                        return max(1.0, min(10.0, score))  # Clamp to 1-10
                    else:
                        logger.warning(f"Could not parse LLM score: {score_text}")
                        return 5.0  # Default middle score
                except Exception as e:
                    logger.error(f"Error parsing LLM score: {e}")
                    return 5.0
                    
        except Exception as e:
            logger.error(f"LLM importance scoring failed: {e}")
            # Fall back to rule-based scoring
            return self._calculate_importance(content)
    
    async def store_memory(self, memory: Dict[str, Any]) -> int:
        """Store a memory in the database and trigger async scoring and embedding pipeline."""
        db = get_db()
        
        # Check for exact duplicates first (without embedding)
        existing = await db.fetch_one("""
            SELECT id FROM agent_memories 
            WHERE content = ? AND is_active = 1
        """, (memory['content'],))
        
        if existing:
            # Update access count and timestamp instead of creating duplicate
            await db.execute("""
                UPDATE agent_memories 
                SET access_count = access_count + 1,
                    last_accessed_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (existing['id'],))
            await db.commit()
            return existing['id']
        
        # Insert new memory with all relevant fields
        cursor = await db.execute("""
            INSERT INTO agent_memories (
                memory_type, content, key_entities, 
                importance_score, base_importance_score, final_importance_score,
                score_source, embedding, source_conversation_id, related_entry_id,
                llm_processed, llm_processed_at, llm_importance_score,
                user_rated, user_score_adjustment, user_rated_at,
                is_active, created_at, last_accessed_at, access_count,
                marked_for_deletion, archived
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            memory['memory_type'],
            memory['content'],
            json.dumps(memory.get('key_entities', [])),
            memory.get('base_importance_score', 5.0),  # Legacy field
            memory.get('base_importance_score', 5.0),
            memory.get('final_importance_score', 5.0),
            memory.get('score_source', 'rule'),
            None,  # No embedding initially
            memory.get('source_conversation_id'),
            memory.get('related_entry_id'),
            memory.get('llm_processed', 0),
            memory.get('llm_processed_at'),
            memory.get('llm_importance_score'),
            memory.get('user_rated', 0),
            memory.get('user_score_adjustment', 0),
            memory.get('user_rated_at'),
            memory.get('is_active', 1),
            datetime.now().isoformat(),
            None,  # last_accessed_at
            0,  # access_count
            memory.get('marked_for_deletion', 0),
            memory.get('archived', 0)
        ))
        
        await db.commit()
        memory_id = cursor.lastrowid
        
        # Trigger async pipeline: Score → Embed (only for LLM-extracted memories)
        if memory.get('score_source') == 'llm_extraction':
            asyncio.create_task(self._score_and_embed_async(memory_id, memory))
        else:
            # For non-LLM memories (rule-based, user-modified), just generate embedding
            asyncio.create_task(self._generate_embedding_async(memory_id, memory['content']))
        
        return memory_id
    
    async def _score_and_embed_async(self, memory_id: int, memory: Dict[str, Any]):
        """Async pipeline: LLM score memory then generate embedding."""
        db = get_db()
        try:
            logger.info(f"Starting async scoring and embedding for memory {memory_id}")
            
            # Step 1: Calculate LLM importance score
            llm_score = await self.calculate_importance_with_llm(
                content=memory['content'],
                memory_type=memory['memory_type'],
                key_entities=memory.get('key_entities', [])
            )
            
            # Step 2: Update memory with LLM score
            await db.execute("""
                UPDATE agent_memories 
                SET llm_importance_score = ?,
                    final_importance_score = ?,
                    llm_processed = 1,
                    llm_processed_at = CURRENT_TIMESTAMP,
                    score_source = 'llm'
                WHERE id = ?
            """, (llm_score, llm_score, memory_id))
            await db.commit()
            
            logger.info(f"Updated memory {memory_id} with LLM score: {llm_score}")
            
            # Step 3: Generate embedding with final scored memory
            await self._generate_embedding_async(memory_id, memory['content'])
            
        except Exception as e:
            logger.error(f"Failed async scoring and embedding for memory {memory_id}: {e}")
            # Fallback: Just generate embedding without LLM scoring
            try:
                await self._generate_embedding_async(memory_id, memory['content'])
            except Exception as embed_error:
                logger.error(f"Fallback embedding generation also failed for memory {memory_id}: {embed_error}")
    
    async def _generate_embedding_async(self, memory_id: int, content: str):
        """Generate embedding for a memory asynchronously after it's stored."""
        db = get_db()
        try:
            if not self.embedding_model:
                logger.warning(f"No embedding model available for memory {memory_id}")
                return
            
            # Generate embedding
            embedding_vector = self.embedding_model.encode(content)
            embedding_json = json.dumps(embedding_vector.tolist())
            
            # Update memory with embedding
            await db.execute("""
                UPDATE agent_memories 
                SET embedding = ?
                WHERE id = ?
            """, (embedding_json, memory_id))
            await db.commit()
            
            logger.info(f"Generated embedding for memory {memory_id}")
            
        except Exception as e:
            logger.error(f"Failed to generate embedding for memory {memory_id}: {e}")
    
    async def retrieve_relevant_memories(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Retrieve memories relevant to a query.
        Uses semantic similarity if embeddings are available.
        """
        db = get_db()
        memories = []
        
        # If we have embedding model, use semantic search
        if self.embedding_model:
            try:
                query_embedding = self.embedding_model.encode(query)
                
                # Get all active memories with embeddings
                candidates = await db.fetch_all("""
                    SELECT id, memory_type, content, key_entities, importance_score,
                           embedding, created_at, last_accessed_at, access_count
                    FROM agent_memories
                    WHERE is_active = 1 AND embedding IS NOT NULL
                    ORDER BY importance_score DESC
                    LIMIT 100
                """)
                
                # Calculate similarities
                scored_memories = []
                for candidate in candidates:
                    if candidate['embedding']:
                        stored_embedding = np.array(json.loads(candidate['embedding']))
                        similarity = np.dot(query_embedding, stored_embedding) / (
                            np.linalg.norm(query_embedding) * np.linalg.norm(stored_embedding)
                        )
                        
                        # Combine similarity with importance score
                        final_score = (similarity * 0.7) + (candidate['importance_score'] / 10.0 * 0.3)
                        
                        scored_memories.append((final_score, dict(candidate)))
                
                # Sort by score and take top N
                scored_memories.sort(key=lambda x: x[0], reverse=True)
                memories = [m[1] for m in scored_memories[:limit]]
                
            except Exception as e:
                logger.error(f"Semantic search failed, falling back to keyword search: {e}")
        
        # Fallback to keyword search if semantic search fails or unavailable
        if not memories:
            # Simple keyword-based retrieval
            memories = await db.fetch_all("""
                SELECT id, memory_type, content, key_entities, importance_score,
                       created_at, last_accessed_at, access_count
                FROM agent_memories
                WHERE is_active = 1
                ORDER BY importance_score DESC, access_count DESC
                LIMIT ?
            """, (limit,))
        
        # Update access timestamps
        if memories:
            memory_ids = [m['id'] for m in memories]
            placeholders = ','.join('?' * len(memory_ids))
            await db.execute(f"""
                UPDATE agent_memories
                SET last_accessed_at = CURRENT_TIMESTAMP,
                    access_count = access_count + 1
                WHERE id IN ({placeholders})
            """, tuple(memory_ids))
            await db.commit()
        
        return memories
    
    async def get_memory_summary(self) -> Dict[str, Any]:
        """Get a summary of stored memories."""
        db = get_db()
        # Get counts by type
        type_counts_result = await db.fetch_all("""
            SELECT memory_type, COUNT(*) as count
            FROM agent_memories
            WHERE is_active = 1
            GROUP BY memory_type
        """)
        
        type_counts = {row['memory_type']: row['count'] for row in type_counts_result}
        
        # Get total count
        total_result = await db.fetch_one("""
            SELECT COUNT(*) as total
            FROM agent_memories
            WHERE is_active = 1
        """)
        
        total = total_result['total'] if total_result else 0
        
        # Get most accessed memories
        most_accessed = await db.fetch_all("""
            SELECT content, access_count
            FROM agent_memories
            WHERE is_active = 1
            ORDER BY access_count DESC
            LIMIT 5
        """)
        
        return {
            'total_memories': total,
            'by_type': type_counts,
            'most_accessed': most_accessed
        }
    
    async def deactivate_outdated_memories(self, memory_id: int):
        """Deactivate a memory (soft delete)."""
        db = get_db()
        await db.execute("""
            UPDATE agent_memories
            SET is_active = 0
            WHERE id = ?
        """, (memory_id,))
        await db.commit()
    
    async def process_conversation_for_memories(self, conversation_id: int, conversation_text: str) -> int:
        """
        Process a conversation and extract/store memories.
        Returns the number of memories extracted.
        """
        # Extract memories
        memories = self.extract_memories_from_conversation(conversation_text, conversation_id)
        
        # Store each memory
        stored_count = 0
        for memory in memories:
            try:
                await self.store_memory(memory)
                stored_count += 1
            except Exception as e:
                logger.error(f"Failed to store memory: {e}")
        
        logger.info(f"Extracted and stored {stored_count} memories from conversation {conversation_id}")
        return stored_count
    
    async def process_entry_for_memories(self, entry_id: int, enhanced_text: str) -> int:
        """
        Process a journal entry and extract/store memories.
        Uses enhanced text for better quality extraction.
        Returns the number of memories extracted.
        """
        if not enhanced_text:
            return 0
            
        db = get_db()
        # Extract memories from enhanced entry text
        memories = []
        
        # Similar extraction logic but adapted for journal entries
        sentences = enhanced_text.split('.')
        for sentence in sentences:
            sentence = sentence.strip()
            if any(keyword in sentence.lower() for keyword in ['my', 'i ', "i'm", "i've", 'prefer', 'like', 'usually', 'always', 'every']):
                base_score = self._calculate_importance(sentence) * 1.2  # Entries slightly more important
                memory = {
                    'content': sentence,
                    'memory_type': self._classify_memory_type(sentence),
                    'key_entities': self._extract_entities(sentence),
                    'related_entry_id': entry_id,  # Link to entry instead of conversation
                    'source_conversation_id': None,
                    'base_importance_score': base_score,
                    'final_importance_score': base_score,
                    'score_source': 'rule'
                }
                memories.append(memory)
        
        # Store each memory
        stored_count = 0
        for memory in memories:
            try:
                await self.store_memory(memory)
                stored_count += 1
            except Exception as e:
                logger.error(f"Failed to store memory from entry: {e}")
        
        logger.info(f"Extracted and stored {stored_count} memories from entry {entry_id}")
        return stored_count
    
    async def extract_memories_with_llm(
        self, 
        text: str, 
        source_id: int,
        source_type: str = 'conversation',
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        num_ctx: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Extract memories using LLM with preferences.
        
        Args:
            text: The text to extract memories from
            source_id: ID of the source (conversation or entry)
            source_type: 'conversation' or 'entry'
            model: Optional model override (uses preferences if None)
            temperature: Optional temperature override (uses preferences if None)
            num_ctx: Optional context window override (uses preferences if None)
        
        Returns:
            List of memory dictionaries ready for storage
        """
        db = get_db()
        try:
            # Get preferences if not provided
            if model is None:
                model = await PreferencesRepository.get_value('memory_extraction_model') or \
                        await PreferencesRepository.get_value('ollama_model', settings.OLLAMA_DEFAULT_MODEL)
            if temperature is None:
                temperature = await PreferencesRepository.get_value('memory_extraction_temperature', 0.3)
            if num_ctx is None:
                num_ctx = await PreferencesRepository.get_value('memory_extraction_num_ctx', 4096)
            
            # Get recent memories for deduplication context (last 50 memories)
            recent_memories = await db.fetch_all("""
                SELECT content, memory_type FROM agent_memories 
                WHERE is_active = 1
                ORDER BY created_at DESC
                LIMIT 50
            """)
            
            # Format existing memories for context
            existing_memories_text = ""
            if recent_memories:
                existing_facts = [m['content'] for m in recent_memories if m['memory_type'] == 'factual'][:5]
                existing_prefs = [m['content'] for m in recent_memories if m['memory_type'] == 'preference'][:5]
                existing_habits = [m['content'] for m in recent_memories if m['memory_type'] == 'behavioral'][:5]
                
                if existing_facts:
                    existing_memories_text += f"Known facts: {'; '.join(existing_facts[:3])}\n"
                if existing_prefs:
                    existing_memories_text += f"Known preferences: {'; '.join(existing_prefs[:3])}\n"
                if existing_habits:
                    existing_memories_text += f"Known habits: {'; '.join(existing_habits[:3])}\n"
            
            if not existing_memories_text:
                existing_memories_text = "No existing memories yet."
            
            # Create the extraction prompt
            system_prompt = """You are a memory extraction specialist for a personal journaling app. Extract ONLY important, permanent facts about the user from their text.

IMPORTANT: Each extracted memory must be within 1 line only.
If there are NO significant personal facts worth remembering, return an empty array [].

Categories to extract:
- factual: Name, age, occupation, location, possessions
- relational: Family, friends, colleagues (with names)
- preference: Strong likes/dislikes, choices, communication style
- behavioral: Daily routines, recurring habits, patterns

Rules:
1. ONLY extract explicitly stated facts by the user
2. Ignore temporary states (feeling tired, currently eating)
3. Ignore opinions about external things unless they reveal personal preference
4. Each memory should be complete and standalone
5. **CRITICAL: Maximum 3 memories per text - NO EXCEPTIONS!** Extract only the 3 most important facts.
6. Assign confidence score (0.0-1.0) based on clarity and importance
7. Skip facts that are already known (see existing memories below)

Output format: JSON array with objects containing:
- "content": the actual memory text
- "memory_type": one of factual/relational/preference/behavioral
- "confidence": score from 0.0 to 1.0

Example: [{"content": "My name is John", "memory_type": "factual", "confidence": 0.9}]

Output ONLY valid JSON array, no other text. Remember: MAXIMUM 3 memories only!"""

            user_prompt = f"""Existing memories to avoid duplicating:
{existing_memories_text}

Text to analyze:
{text}

Extract memories as JSON array:"""
            
            # Call Ollama service with correct options structure
            async with OllamaService() as ollama:
                response = await ollama.generate(
                    prompt=user_prompt,
                    system=system_prompt,
                    model=model,
                    options={
                        'temperature': float(temperature),
                        'num_ctx': int(num_ctx),
                        'num_predict': 500
                    }
                )
            
            # Parse JSON response
            try:
                # Clean the response - remove any markdown formatting
                response_text = response.response.strip()
                if response_text.startswith("```json"):
                    response_text = response_text[7:]
                if response_text.startswith("```"):
                    response_text = response_text[3:]
                if response_text.endswith("```"):
                    response_text = response_text[:-3]
                response_text = response_text.strip()
                
                # Parse JSON
                memories_data = json.loads(response_text)
                
                # Ensure it's a list
                if not isinstance(memories_data, list):
                    logger.warning(f"LLM returned non-list: {type(memories_data)}")
                    memories_data = []
                
                # Format memories for storage
                memories = []
                for mem in memories_data:
                    # Validate required fields
                    if not isinstance(mem, dict) or 'content' not in mem:
                        logger.warning(f"Skipping invalid memory: {mem}")
                        continue
                    
                    # Get confidence score
                    confidence = mem.get('confidence', 0.7)
                    if confidence < 0.4:  # Skip low confidence memories
                        logger.info(f"Skipping low confidence memory: {mem['content']} (confidence: {confidence})")
                        continue
                    
                    # Normalize memory type to valid values
                    raw_memory_type = mem.get('memory_type', mem.get('type', 'contextual'))
                    valid_types = ['factual', 'preference', 'behavioral', 'relational', 'contextual']
                    
                    # Validate and normalize memory type
                    if raw_memory_type not in valid_types:
                        # Try to map common variations
                        if 'factual' in raw_memory_type.lower():
                            memory_type = 'factual'
                        elif 'preference' in raw_memory_type.lower():
                            memory_type = 'preference'
                        elif 'behavioral' in raw_memory_type.lower() or 'behaviour' in raw_memory_type.lower():
                            memory_type = 'behavioral'
                        elif 'relational' in raw_memory_type.lower() or 'relationship' in raw_memory_type.lower():
                            memory_type = 'relational'
                        else:
                            memory_type = 'contextual'
                        logger.warning(f"Normalized invalid memory type '{raw_memory_type}' to '{memory_type}'")
                    else:
                        memory_type = raw_memory_type
                    
                    # Create memory object
                    memory = {
                        'content': mem['content'][:500],  # Limit length
                        'memory_type': memory_type,
                        'key_entities': mem.get('key_entities', []),
                        'source_conversation_id': source_id if source_type == 'conversation' else None,
                        'related_entry_id': source_id if source_type == 'entry' else None,
                        'base_importance_score': confidence * 10,  # Convert to 1-10 scale
                        'final_importance_score': confidence * 10,
                        'score_source': 'llm_extraction',
                        'llm_processed': 1,
                        'llm_processed_at': datetime.now().isoformat()
                    }
                    memories.append(memory)
                
                logger.info(f"LLM extracted {len(memories)} high-confidence memories from {source_type} {source_id}")
                return memories
                
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse LLM response as JSON: {e}")
                logger.error(f"Response was: {response.response[:500]}")
                return []
                
        except Exception as e:
            logger.error(f"LLM memory extraction failed: {e}")
            # Fall back to rule-based extraction
            logger.info("Falling back to rule-based extraction")
            if source_type == 'conversation':
                return self.extract_memories_from_conversation(text, source_id)
            else:
                # For entries, return empty list as the rule-based is already called separately
                return []
    
    def format_memories_for_context(self, memories: List[Dict[str, Any]]) -> str:
        """
        Format memories into a string for LLM context injection.
        Groups by type for better organization.
        """
        if not memories:
            return ""
        
        # Group memories by type
        grouped = {
            'factual': [],
            'preference': [],
            'behavioral': [],
            'relational': [],
            'contextual': []
        }
        
        for memory in memories:
            memory_type = memory.get('memory_type', 'contextual')
            # Normalize memory type to one of our valid types
            if memory_type not in grouped:
                # Handle invalid or variant memory types
                if 'factual' in memory_type.lower():
                    memory_type = 'factual'
                elif 'preference' in memory_type.lower():
                    memory_type = 'preference'
                elif 'behavioral' in memory_type.lower() or 'behaviour' in memory_type.lower():
                    memory_type = 'behavioral'
                elif 'relational' in memory_type.lower() or 'relationship' in memory_type.lower():
                    memory_type = 'relational'
                else:
                    memory_type = 'contextual'  # Default fallback
                    
            grouped[memory_type].append(memory['content'])
        
        # Format into readable context
        context_parts = []
        
        if grouped['factual']:
            context_parts.append("Personal Facts:\n" + "\n".join(f"- {m}" for m in grouped['factual']))
        
        if grouped['preference']:
            context_parts.append("Preferences:\n" + "\n".join(f"- {m}" for m in grouped['preference']))
        
        if grouped['behavioral']:
            context_parts.append("Habits & Patterns:\n" + "\n".join(f"- {m}" for m in grouped['behavioral']))
        
        if grouped['relational']:
            context_parts.append("Relationships:\n" + "\n".join(f"- {m}" for m in grouped['relational']))
        
        if grouped['contextual']:
            context_parts.append("Context:\n" + "\n".join(f"- {m}" for m in grouped['contextual']))
        
        return "\n\n".join(context_parts)
    
    def calculate_recency_decay(self, memory: Dict[str, Any]) -> float:
        """
        Calculate decay based on last access/creation time.
        - No decay for first 7 days
        - Gradual decay: -0.1 points per week after that
        - Max decay: -3 points (after ~30 weeks)
        """
        # Use last_accessed_at if available, else created_at
        last_relevant_date = memory.get('last_accessed_at') or memory.get('created_at')
        if not last_relevant_date:
            return 0
        
        # Parse date if string
        if isinstance(last_relevant_date, str):
            last_relevant_date = datetime.fromisoformat(last_relevant_date)
        
        days_since = (datetime.now() - last_relevant_date).days
        
        if days_since <= 7:
            return 0  # Grace period
        
        weeks_inactive = (days_since - 7) / 7
        decay = min(3.0, weeks_inactive * 0.1)  # -0.1 per week, max -3
        
        return -decay
    
    def calculate_frequency_boost(self, memory: Dict[str, Any]) -> float:
        """
        Calculate boost based on access patterns.
        - Recent access + high frequency = high boost
        - Old access + high frequency = moderate boost
        - Low frequency = no boost
        """
        access_count = memory.get('access_count', 0)
        
        # Time-weighted access score
        last_accessed = memory.get('last_accessed_at')
        if last_accessed:
            if isinstance(last_accessed, str):
                last_accessed = datetime.fromisoformat(last_accessed)
            days_since_access = (datetime.now() - last_accessed).days
            recency_weight = max(0.2, 1 - (days_since_access / 30))  # 100% to 20% over 30 days
        else:
            recency_weight = 0.2
        
        # Logarithmic boost (diminishing returns)
        if access_count == 0:
            return 0
        
        frequency_boost = min(2.0, math.log(access_count + 1) * 0.5)  # Max +2
        
        # Apply recency weight to boost
        return frequency_boost * recency_weight
    
    def calculate_effective_score(self, memory: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate final score with all factors including decay and boost.
        """
        # Base score (from LLM or rules)
        base = memory.get('llm_importance_score') or memory.get('base_importance_score', 5.0)
        
        # User adjustment (priority)
        user_adj = memory.get('user_score_adjustment', 0)
        
        # Recency decay
        recency_decay = self.calculate_recency_decay(memory)
        
        # Frequency boost
        frequency_boost = self.calculate_frequency_boost(memory)
        
        # Special cases for user-rated memories
        if memory.get('user_rated') == 1:
            # User-rated: reduce decay impact by 50%
            recency_decay = recency_decay * 0.5
            # Boost frequency impact for rated memories
            frequency_boost = frequency_boost * 1.5
        
        # Calculate final score
        final = base + user_adj + recency_decay + frequency_boost
        
        # Clamp to 1-10 range
        return {
            'score': max(1.0, min(10.0, final)),
            'breakdown': {
                'base': base,
                'user_adjustment': user_adj,
                'recency_decay': recency_decay,
                'frequency_boost': frequency_boost
            }
        }
    
    async def rate_memory(self, memory_id: int, adjustment: int) -> bool:
        """
        Apply user rating to a memory (-3 to +3).
        """
        db = get_db()
        # Validate adjustment
        adjustment = max(-3, min(3, adjustment))
        
        # Get current memory
        memory = await db.fetch_one(
            "SELECT * FROM agent_memories WHERE id = ?", 
            (memory_id,)
        )
        
        if not memory:
            return False
        
        # Calculate new final score
        base = memory.get('llm_importance_score') or memory.get('base_importance_score', 5.0)
        final_score = max(1, min(10, base + adjustment))
        
        # Update memory with user rating
        await db.execute("""
            UPDATE agent_memories 
            SET user_score_adjustment = ?,
                final_importance_score = ?,
                user_rated = 1,
                user_rated_at = CURRENT_TIMESTAMP,
                score_source = 'user_modified'
            WHERE id = ?
        """, (adjustment, final_score, memory_id))
        
        await db.commit()
        return True
    
    async def get_unrated_memories(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get memories that haven't been rated by user yet."""
        db = get_db()
        memories = await db.fetch_all("""
            SELECT * FROM agent_memories 
            WHERE user_rated = 0 
            AND is_active = 1
            ORDER BY 
                llm_processed DESC,  -- Show LLM-scored ones first
                created_at DESC      -- Then newest
            LIMIT ?
        """, (limit,))
        
        # Calculate effective scores for each
        for memory in memories:
            memory['effective_score_data'] = self.calculate_effective_score(dict(memory))
        
        return memories
    
    async def process_memories_with_llm_batch(self, batch_size: int = 5):
        """
        Process unprocessed memories with LLM in batches.
        Should be called periodically (e.g., every 5 minutes).
        """
        db = get_db()
        # Get memories needing LLM processing
        memories = await db.fetch_all("""
            SELECT * FROM agent_memories 
            WHERE llm_processed = 0 
            AND user_rated = 0        -- Don't process if user already rated
            AND is_active = 1
            ORDER BY created_at ASC    -- Process oldest first
            LIMIT ?
        """, (batch_size,))
        
        if not memories:
            return 0
        
        processed_count = 0
        for memory in memories:
            try:
                # Calculate LLM score
                key_entities = json.loads(memory.get('key_entities', '[]'))
                llm_score = await self.calculate_importance_with_llm(
                    content=memory['content'],
                    memory_type=memory['memory_type'],
                    key_entities=key_entities
                )
                
                # Update only if user hasn't rated yet
                await db.execute("""
                    UPDATE agent_memories 
                    SET llm_importance_score = ?,
                        final_importance_score = CASE 
                            WHEN user_rated = 1 THEN final_importance_score
                            ELSE ?
                        END,
                        llm_processed = 1,
                        llm_processed_at = CURRENT_TIMESTAMP,
                        score_source = CASE 
                            WHEN user_rated = 1 THEN score_source
                            ELSE 'llm'
                        END
                    WHERE id = ? AND user_rated = 0
                """, (llm_score, llm_score, memory['id']))
                
                processed_count += 1
                logger.info(f"Processed memory {memory['id']} with LLM score: {llm_score}")
                
            except Exception as e:
                logger.error(f"Failed to process memory {memory['id']} with LLM: {e}")
        
        await db.commit()
        return processed_count
    
    async def mark_memories_for_deletion(self) -> List[int]:
        """
        Mark memories for deletion based on criteria.
        Should be run monthly (e.g., 1st of each month).
        """
        db = get_db()
        # Find candidates for deletion
        candidates = await db.fetch_all("""
            SELECT * FROM agent_memories 
            WHERE is_active = 1
            AND user_rated = 1
            AND user_score_adjustment = -3
            AND access_count < 3
            AND julianday('now') - julianday(COALESCE(last_accessed_at, created_at)) >= 60
            AND julianday('now') - julianday(created_at) >= 30
            AND marked_for_deletion = 0
        """)
        
        deletion_batch = []
        for memory in candidates:
            score_data = self.calculate_effective_score(dict(memory))
            if score_data['score'] <= 2.0:
                deletion_batch.append(memory['id'])
        
        # Mark for deletion
        if deletion_batch:
            placeholders = ','.join(['?'] * len(deletion_batch))
            await db.execute(f"""
                UPDATE agent_memories 
                SET marked_for_deletion = 1,
                    marked_for_deletion_at = CURRENT_TIMESTAMP,
                    deletion_reason = 'User marked irrelevant, low access, stale'
                WHERE id IN ({placeholders})
            """, deletion_batch)
            await db.commit()
        
        logger.info(f"Marked {len(deletion_batch)} memories for deletion")
        return deletion_batch
    
    async def archive_marked_memories(self) -> int:
        """
        Archive memories marked for deletion (soft delete).
        Should be run 2 weeks after marking.
        """
        db = get_db()
        result = await db.execute("""
            UPDATE agent_memories 
            SET archived = 1,
                archived_at = CURRENT_TIMESTAMP,
                is_active = 0
            WHERE marked_for_deletion = 1
            AND julianday('now') - julianday(marked_for_deletion_at) >= 14
            AND archived = 0
        """)
        
        await db.commit()
        count = result.rowcount if hasattr(result, 'rowcount') else 0
        logger.info(f"Archived {count} memories")
        return count
    
    async def permanently_delete_archived(self) -> int:
        """
        Permanently delete long-archived memories.
        Should be run monthly.
        """
        db = get_db()
        result = await db.execute("""
            DELETE FROM agent_memories 
            WHERE archived = 1
            AND julianday('now') - julianday(archived_at) >= 30
            AND user_score_adjustment = -3
        """)
        
        await db.commit()
        count = result.rowcount if hasattr(result, 'rowcount') else 0
        logger.info(f"Permanently deleted {count} archived memories")
        return count
    
    async def rescue_memory(self, memory_id: int) -> bool:
        """
        Rescue a memory from deletion queue.
        """
        db = get_db()
        await db.execute("""
            UPDATE agent_memories 
            SET marked_for_deletion = 0,
                marked_for_deletion_at = NULL,
                deletion_reason = NULL,
                user_score_adjustment = 0,
                user_rated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (memory_id,))
        
        await db.commit()
        return True