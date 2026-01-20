"""
Conversation Service for Talk to Your Diary feature.

This service handles:
- Conversation lifecycle management (start, active, end, save)
- Turn-based conversation logic
- Duration tracking and transcription formatting
- State management for active conversations
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field
from enum import Enum

from app.models.conversation import Conversation
from app.db.repositories.conversation_repository import ConversationRepository
from app.db.database import get_db
from app.services.diary_chat_service import get_diary_chat_service
from app.services.memory_service import MemoryService
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)


class ConversationState(Enum):
    """Conversation state enumeration."""
    ACTIVE = "active"
    ENDED = "ended"
    SAVED = "saved"
    ABANDONED = "abandoned"


class ConversationType(Enum):
    """Conversation type enumeration."""
    CALL = "call"
    CHAT = "chat"


@dataclass
class ConversationTurn:
    """Represents a single turn in a conversation."""
    timestamp: datetime
    speaker: str  # 'user' or 'boo'
    message: str
    search_queries_used: List[str] = field(default_factory=list)
    duration_seconds: float = 0.0


@dataclass
class ActiveConversation:
    """Represents an active conversation session."""
    conversation_id: Optional[int]
    conversation_type: ConversationType
    state: ConversationState
    start_time: datetime
    end_time: Optional[datetime]
    turns: List[ConversationTurn] = field(default_factory=list)
    total_search_queries: Set[str] = field(default_factory=set)
    
    @property
    def duration_seconds(self) -> int:
        """Get conversation duration in seconds."""
        if self.end_time:
            return int((self.end_time - self.start_time).total_seconds())
        return int((datetime.now() - self.start_time).total_seconds())
    
    @property
    def message_count(self) -> int:
        """Get total message count."""
        return len(self.turns)
    
    @property
    def transcription(self) -> str:
        """Get formatted transcription."""
        if not self.turns:
            return ""
        
        lines = []
        for turn in self.turns:
            timestamp_str = turn.timestamp.strftime("%H:%M:%S")
            speaker = "You" if turn.speaker == "user" else "Boo"
            lines.append(f"[{timestamp_str}] {speaker}: {turn.message}")
        
        return "\n".join(lines)


class ConversationService:
    """Service for managing conversation workflows and state."""
    
    def __init__(self):
        """Initialize the conversation service."""
        self.active_conversations: Dict[str, ActiveConversation] = {}
        self.repository = ConversationRepository()
        self.chat_service = None  # Lazy loaded
        self.memory_service = MemoryService()
        self.embedding_model = None  # Lazy loaded
        
    async def start_conversation(
        self, 
        conversation_type: ConversationType,
        session_id: Optional[str] = None
    ) -> str:
        """
        Start a new conversation.
        
        Args:
            conversation_type: Type of conversation (call or chat)
            session_id: Optional session ID, generated if not provided
            
        Returns:
            Session ID for the new conversation
        """
        if session_id is None:
            session_id = self._generate_session_id()
        
        # Create active conversation
        active_conversation = ActiveConversation(
            conversation_id=None,
            conversation_type=conversation_type,
            state=ConversationState.ACTIVE,
            start_time=datetime.now()
        )
        
        self.active_conversations[session_id] = active_conversation
        
        logger.info(f"Started {conversation_type.value} conversation with session ID: {session_id}")
        return session_id
    
    async def add_turn(
        self,
        session_id: str,
        speaker: str,
        message: str,
        search_queries_used: Optional[List[str]] = None
    ) -> bool:
        """
        Add a conversation turn.
        
        Args:
            session_id: Session ID of the conversation
            speaker: 'user' or 'boo'
            message: The message content
            search_queries_used: List of search queries used (for Boo responses)
            
        Returns:
            True if turn was added successfully
        """
        if session_id not in self.active_conversations:
            logger.warning(f"Attempted to add turn to non-existent conversation: {session_id}")
            return False
        
        conversation = self.active_conversations[session_id]
        
        if conversation.state != ConversationState.ACTIVE:
            logger.warning(f"Attempted to add turn to inactive conversation: {session_id}")
            return False
        
        # Create conversation turn
        turn = ConversationTurn(
            timestamp=datetime.now(),
            speaker=speaker,
            message=message,
            search_queries_used=search_queries_used or []
        )
        
        conversation.turns.append(turn)
        
        # Track search queries
        if search_queries_used:
            conversation.total_search_queries.update(search_queries_used)
        
        logger.info(f"Added {speaker} turn to conversation {session_id}")
        return True
    
    async def process_user_message(
        self,
        session_id: str,
        user_message: str
    ) -> Dict[str, Any]:
        """
        Process a user message and get Boo's response.
        
        Args:
            session_id: Session ID of the conversation
            user_message: User's message
            
        Returns:
            Response data with Boo's message and metadata
        """
        if session_id not in self.active_conversations:
            raise ValueError(f"Conversation {session_id} not found")
        
        conversation = self.active_conversations[session_id]
        
        if conversation.state != ConversationState.ACTIVE:
            raise ValueError(f"Conversation {session_id} is not active")
        
        # Add user turn
        await self.add_turn(session_id, "user", user_message)
        
        # Get conversation history for context
        conversation_history = self._build_conversation_history(conversation)
        
        # Get chat service (lazy loading)
        if self.chat_service is None:
            self.chat_service = get_diary_chat_service()
        
        # Process message with chat service
        chat_response = await self.chat_service.process_message(
            message=user_message,
            conversation_history=conversation_history
        )
        
        boo_message = chat_response.get("response", "")
        search_queries = chat_response.get("search_queries_used", [])
        
        # Add Boo turn
        await self.add_turn(session_id, "boo", boo_message, search_queries)
        
        return {
            "response": boo_message,
            "search_queries_used": search_queries,
            "tool_calls_made": chat_response.get("tool_calls_made", []),
            "turn_count": conversation.message_count,
            "duration_seconds": conversation.duration_seconds
        }
    
    async def end_conversation(self, session_id: str) -> bool:
        """
        End an active conversation.
        
        Args:
            session_id: Session ID of the conversation
            
        Returns:
            True if conversation was ended successfully
        """
        if session_id not in self.active_conversations:
            logger.warning(f"Attempted to end non-existent conversation: {session_id}")
            return False
        
        conversation = self.active_conversations[session_id]
        conversation.state = ConversationState.ENDED
        conversation.end_time = datetime.now()
        
        logger.info(f"Ended conversation {session_id} after {conversation.duration_seconds} seconds")
        return True
    
    async def save_conversation(self, session_id: str) -> Optional[int]:
        """
        Save a conversation to the database.
        
        Args:
            session_id: Session ID of the conversation
            
        Returns:
            Database ID of saved conversation, or None if failed
        """
        if session_id not in self.active_conversations:
            logger.warning(f"Attempted to save non-existent conversation: {session_id}")
            return None
        
        conversation = self.active_conversations[session_id]
        
        if conversation.state not in [ConversationState.ENDED, ConversationState.ACTIVE]:
            logger.warning(f"Cannot save conversation {session_id} in state {conversation.state}")
            return None
        
        # Ensure conversation is ended
        if conversation.state == ConversationState.ACTIVE:
            await self.end_conversation(session_id)
        
        # Create conversation model
        conversation_model = Conversation(
            timestamp=conversation.start_time,
            duration=conversation.duration_seconds,
            transcription=conversation.transcription,
            conversation_type=conversation.conversation_type.value,
            message_count=conversation.message_count,
            search_queries_used=list(conversation.total_search_queries),
            created_at=datetime.now()
        )
        
        # Save to database
        saved_conversation = await self.repository.create(conversation_model)
        
        if saved_conversation:
            conversation.conversation_id = saved_conversation.id
            conversation.state = ConversationState.SAVED
            
            # Generate embedding, summary, and metadata for conversation
            try:
                if self.embedding_model is None:
                    self.embedding_model = SentenceTransformer('BAAI/bge-small-en-v1.5')
                
                # Generate embedding from transcription
                embedding_vector = self.embedding_model.encode(conversation.transcription)
                embedding_json = json.dumps(embedding_vector.tolist())
                
                # Extract key topics from conversation (simple keyword extraction for now)
                key_topics = self._extract_key_topics(conversation.transcription)
                
                # Generate AI summary using same model as entry processing (not truncation!)
                summary = await self._generate_conversation_summary(conversation.transcription)
                
                # Update conversation with embedding and metadata
                await self.repository.update_conversation_metadata(
                    saved_conversation.id,
                    embedding_json,
                    summary,
                    key_topics
                )
                
                logger.info(f"Generated embedding and summary for conversation {saved_conversation.id}")
            except Exception as e:
                logger.error(f"Failed to generate embedding and summary for conversation: {e}")
            
            # Extract and store memories from conversation using async LLM
            # Fire and forget - user doesn't wait for this
            asyncio.create_task(
                self._extract_memories_with_llm_async(
                    saved_conversation.id,
                    conversation.transcription
                )
            )
            logger.info(f"Queued async LLM memory extraction for conversation {saved_conversation.id}")
            
            logger.info(f"Saved conversation {session_id} to database with ID {saved_conversation.id}")
            return saved_conversation.id
        
        logger.error(f"Failed to save conversation {session_id} to database")
        return None
    
    async def _extract_memories_with_llm_async(self, conversation_id: int, text: str):
        """
        Background task to extract memories from conversation using LLM.
        This runs asynchronously after conversation is saved.
        """
        try:
            logger.info(f"Starting async LLM memory extraction for conversation {conversation_id}")
            
            # Extract memories using LLM
            memories = await self.memory_service.extract_memories_with_llm(
                text=text,
                source_id=conversation_id,
                source_type='conversation'
                # model, temperature, num_ctx will be loaded from preferences
            )
            
            # Store each memory
            stored_count = 0
            for memory in memories:
                try:
                    await self.memory_service.store_memory(memory)
                    stored_count += 1
                except Exception as e:
                    logger.error(f"Failed to store memory: {e}")
            
            logger.info(f"LLM extracted and stored {stored_count} memories from conversation {conversation_id}")
            
            # Mark conversation as processed for memory extraction
            db = get_db()
            await db.execute("""
                UPDATE conversations 
                SET memory_extracted = 1,
                    memory_extracted_llm = 1,
                    memory_extracted_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (conversation_id,))
            await db.commit()
            logger.info(f"Marked conversation {conversation_id} as memory_extracted")
            
            # Optionally, also run rule-based extraction as fallback/comparison
            # This can be removed once LLM extraction is proven reliable
            if stored_count == 0:
                logger.info("No memories from LLM, trying rule-based extraction as fallback")
                fallback_count = await self.memory_service.process_conversation_for_memories(
                    conversation_id,
                    text
                )
                logger.info(f"Rule-based fallback extracted {fallback_count} memories")
                
        except Exception as e:
            logger.error(f"Async LLM memory extraction failed for conversation {conversation_id}: {e}")
            # Try rule-based as final fallback
            try:
                fallback_count = await self.memory_service.process_conversation_for_memories(
                    conversation_id,
                    text
                )
                logger.info(f"Rule-based fallback after error extracted {fallback_count} memories")
            except Exception as fallback_error:
                logger.error(f"Even rule-based fallback failed: {fallback_error}")
    
    async def abandon_conversation(self, session_id: str) -> bool:
        """
        Abandon a conversation without saving.
        
        Args:
            session_id: Session ID of the conversation
            
        Returns:
            True if conversation was abandoned successfully
        """
        if session_id not in self.active_conversations:
            logger.warning(f"Attempted to abandon non-existent conversation: {session_id}")
            return False
        
        conversation = self.active_conversations[session_id]
        conversation.state = ConversationState.ABANDONED
        conversation.end_time = datetime.now()
        
        # Remove from active conversations
        del self.active_conversations[session_id]
        
        logger.info(f"Abandoned conversation {session_id}")
        return True
    
    def get_conversation_state(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get current state of a conversation.
        
        Args:
            session_id: Session ID of the conversation
            
        Returns:
            Conversation state data or None if not found
        """
        if session_id not in self.active_conversations:
            return None
        
        conversation = self.active_conversations[session_id]
        
        return {
            "session_id": session_id,
            "conversation_id": conversation.conversation_id,
            "type": conversation.conversation_type.value,
            "state": conversation.state.value,
            "start_time": conversation.start_time.isoformat(),
            "end_time": conversation.end_time.isoformat() if conversation.end_time else None,
            "duration_seconds": conversation.duration_seconds,
            "message_count": conversation.message_count,
            "turn_count": len(conversation.turns),
            "search_queries_used": list(conversation.total_search_queries)
        }
    
    def list_active_conversations(self) -> List[Dict[str, Any]]:
        """
        List all active conversations.
        
        Returns:
            List of active conversation states
        """
        return [
            self.get_conversation_state(session_id)
            for session_id in self.active_conversations.keys()
        ]
    
    async def cleanup_stale_conversations(self, max_age_hours: int = 24) -> int:
        """
        Clean up stale conversations that have been active too long.
        
        Args:
            max_age_hours: Maximum age in hours before considering stale
            
        Returns:
            Number of conversations cleaned up
        """
        cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
        stale_sessions = []
        
        for session_id, conversation in self.active_conversations.items():
            if conversation.start_time < cutoff_time:
                stale_sessions.append(session_id)
        
        cleaned_count = 0
        for session_id in stale_sessions:
            await self.abandon_conversation(session_id)
            cleaned_count += 1
        
        if cleaned_count > 0:
            logger.info(f"Cleaned up {cleaned_count} stale conversations")
        
        return cleaned_count
    
    def _generate_session_id(self) -> str:
        """Generate a unique session ID."""
        import uuid
        return f"conv_{uuid.uuid4().hex[:12]}"
    
    def _build_conversation_history(self, conversation: ActiveConversation) -> List[Dict[str, str]]:
        """
        Build conversation history for chat service.
        
        Args:
            conversation: Active conversation
            
        Returns:
            Conversation history in chat format
        """
        history = []
        for turn in conversation.turns:
            role = "user" if turn.speaker == "user" else "assistant"
            history.append({
                "role": role,
                "content": turn.message
            })
        return history
    
    async def _generate_conversation_summary(self, transcription: str) -> str:
        """
        Generate AI summary of conversation using same model as entry processing.
        Uses the same ollama preferences as enhanced/structured modes.
        """
        try:
            # Import here to avoid circular dependencies
            from app.db.repositories.preferences_repository import PreferencesRepository
            from app.core.config import settings
            import requests
            
            # Get same model preferences as entry processing
            model = await PreferencesRepository.get_value('ollama_model', settings.OLLAMA_DEFAULT_MODEL)
            temperature = await PreferencesRepository.get_value('ollama_temperature', 0.2)
            context_window = await PreferencesRepository.get_value('ollama_context_window', 4096)
            ollama_url = await PreferencesRepository.get_value('ollama_url', 'http://localhost:11434')
            
            # Summary generation prompt (similar to structured mode but for conversations)
            system_prompt = """You are a conversation summarizer. Create a concise summary of this conversation between the user and Boo (their journal assistant). 

INSTRUCTIONS:
1. Summarize the key points discussed
2. Capture the main topics and insights
3. Keep it under 300 words
4. Focus on what was meaningful or important
5. Use a warm, personal tone as if speaking to the user

Do not include timestamps or speaker labels in your summary."""
            
            # Prepare request
            payload = {
                "model": model,
                "prompt": transcription,
                "system": system_prompt,
                "stream": False,
                "options": {
                    "temperature": float(temperature),
                    "num_ctx": int(context_window)
                }
            }
            
            # Make request to Ollama
            api_url = f"{ollama_url}/api/generate"
            response = requests.post(api_url, json=payload, timeout=60)
            
            if response.status_code == 200:
                result = response.json()
                summary = result.get("response", "").strip()
                
                # Fallback if summary is empty or too short
                if not summary or len(summary) < 20:
                    logger.warning("AI generated summary too short, using fallback")
                    return self._create_fallback_summary(transcription)
                
                logger.info(f"Generated AI conversation summary using model {model}")
                return summary
            else:
                logger.error(f"Ollama API error: {response.status_code} - {response.text}")
                return self._create_fallback_summary(transcription)
                
        except Exception as e:
            logger.error(f"Failed to generate AI conversation summary: {e}")
            return self._create_fallback_summary(transcription)
    
    def _create_fallback_summary(self, transcription: str) -> str:
        """Create a simple fallback summary when AI generation fails."""
        lines = transcription.split('\n')
        
        # Count user vs Boo turns
        user_turns = len([l for l in lines if 'You:' in l])
        boo_turns = len([l for l in lines if 'Boo:' in l])
        
        # Get first few significant lines
        content_lines = [l for l in lines if l.strip() and not l.startswith('[')][:3]
        preview = ' '.join(content_lines)[:200] + "..." if len(' '.join(content_lines)) > 200 else ' '.join(content_lines)
        
        return f"Conversation with {user_turns} user messages and {boo_turns} Boo responses. Topics discussed: {preview}"

    def _extract_key_topics(self, transcription: str) -> List[str]:
        """
        Extract key topics from conversation transcription.
        Simple keyword extraction for MVP.
        """
        # Common important keywords to look for
        important_words = ['work', 'family', 'health', 'stress', 'happy', 'sad', 
                          'anxious', 'project', 'relationship', 'goal', 'problem',
                          'success', 'failure', 'love', 'fear', 'hope', 'dream']
        
        topics = []
        text_lower = transcription.lower()
        
        for word in important_words:
            if word in text_lower:
                topics.append(word)
        
        # Limit to top 5 topics
        return topics[:5]


# Global conversation service instance
_conversation_service: Optional[ConversationService] = None


def get_conversation_service() -> ConversationService:
    """Get the global conversation service instance."""
    global _conversation_service
    if _conversation_service is None:
        _conversation_service = ConversationService()
    return _conversation_service