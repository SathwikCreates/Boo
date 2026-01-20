from typing import List, Optional, Dict, Any
from datetime import datetime

from app.db.database import get_db
from app.models.conversation import Conversation


class ConversationRepository:
    """Repository for conversation database operations"""
    
    @staticmethod
    async def create(conversation: Conversation) -> Conversation:
        """Create a new conversation"""
        db = get_db()
        data = conversation.to_dict()
        del data["id"]  # Remove id for insert
        
        columns = ", ".join(data.keys())
        placeholders = ", ".join(["?" for _ in data])
        values = list(data.values())
        
        cursor = await db.execute(
            f"INSERT INTO conversations ({columns}) VALUES ({placeholders})",
            tuple(values)
        )
        await db.commit()
        
        conversation.id = cursor.lastrowid
        return conversation
    
    @staticmethod
    async def get_by_id(conversation_id: int) -> Optional[Conversation]:
        """Get conversation by ID"""
        db = get_db()
        row = await db.fetch_one(
            "SELECT * FROM conversations WHERE id = ?", (conversation_id,)
        )
        return Conversation.from_dict(row) if row else None
    
    @staticmethod
    async def get_all(
        limit: int = 50, 
        offset: int = 0,
        conversation_type: Optional[str] = None
    ) -> List[Conversation]:
        """Get all conversations with pagination and filtering"""
        db = get_db()
        query = "SELECT * FROM conversations"
        params = []
        
        if conversation_type:
            query += " WHERE conversation_type = ?"
            params.append(conversation_type)
        
        query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        
        rows = await db.fetch_all(query, tuple(params))
        conversations = []
        for row in rows:
            # Handle None values in search_queries_used
            row_dict = dict(row)
            if row_dict.get('search_queries_used') is None:
                row_dict['search_queries_used'] = '[]'
            conversations.append(Conversation.from_dict(row_dict))
        return conversations
    
    @staticmethod
    async def update(
        conversation_id: int,
        transcription: Optional[str] = None,
        duration: Optional[int] = None,
        message_count: Optional[int] = None,
        search_queries_used: Optional[List[str]] = None
    ) -> Optional[Conversation]:
        """Update conversation fields"""
        db = get_db()
        updates = []
        params = []
        
        if transcription is not None:
            updates.append("transcription = ?")
            params.append(transcription)
        
        if duration is not None:
            updates.append("duration = ?")
            params.append(duration)
        
        if message_count is not None:
            updates.append("message_count = ?")
            params.append(message_count)
        
        if search_queries_used is not None:
            import json
            updates.append("search_queries_used = ?")
            params.append(json.dumps(search_queries_used))
        
        if updates:
            updates.append("updated_at = ?")
            params.append(datetime.now().isoformat())
            
            params.append(conversation_id)  # For WHERE clause
            
            await db.execute(
                f"UPDATE conversations SET {', '.join(updates)} WHERE id = ?",
                tuple(params)
            )
            await db.commit()
        
        return await ConversationRepository.get_by_id(conversation_id)
    
    @staticmethod
    async def update_conversation_metadata(
        conversation_id: int,
        embedding: str = None,
        summary: str = None,
        key_topics: List[str] = None
    ) -> bool:
        """Update conversation metadata for memory system - only updates non-None values"""
        db = get_db()
        import json
        
        # Build dynamic query to only update provided fields
        set_clauses = []
        params = []
        
        if embedding is not None:
            set_clauses.append("embedding = ?")
            params.append(embedding)
            
        if summary is not None:
            set_clauses.append("summary = ?")
            params.append(summary)
            
        if key_topics is not None:
            set_clauses.append("key_topics = ?")
            params.append(json.dumps(key_topics))
        
        if not set_clauses:
            return True  # Nothing to update
            
        # Always update timestamp
        set_clauses.append("updated_at = ?")
        params.append(datetime.now().isoformat())
        params.append(conversation_id)
        
        query = f"""UPDATE conversations 
                   SET {', '.join(set_clauses)}
                   WHERE id = ?"""
        
        await db.execute(query, params)
        await db.commit()
        return True
    
    @staticmethod
    async def delete(conversation_id: int) -> bool:
        """Delete a conversation and related memories"""
        db = get_db()
        try:
            # First delete related agent_memories to avoid foreign key constraint violation
            await db.execute(
                "DELETE FROM agent_memories WHERE source_conversation_id = ?", 
                (conversation_id,)
            )
            
            # Then delete the conversation
            cursor = await db.execute(
                "DELETE FROM conversations WHERE id = ?", (conversation_id,)
            )
            await db.commit()
            return cursor.rowcount > 0
            
        except Exception as e:
            # Rollback any partial changes
            await db.rollback()
            raise e
    
    @staticmethod
    async def count() -> int:
        """Count total conversations"""
        db = get_db()
        result = await db.fetch_one("SELECT COUNT(*) as count FROM conversations")
        return result["count"] if result else 0
    
    @staticmethod
    async def count_by_type(conversation_type: str) -> int:
        """Count conversations by type"""
        db = get_db()
        result = await db.fetch_one(
            "SELECT COUNT(*) as count FROM conversations WHERE conversation_type = ?",
            (conversation_type,)
        )
        return result["count"] if result else 0
    
    @staticmethod
    async def get_statistics() -> Dict[str, Any]:
        """Get comprehensive conversation statistics"""
        db = get_db()
        # Basic counts
        total_conversations = await ConversationRepository.count()
        call_conversations = await ConversationRepository.count_by_type("call")
        chat_conversations = await ConversationRepository.count_by_type("chat")
        
        # Duration and message statistics
        duration_stats = await db.fetch_one(
            "SELECT SUM(duration) as total_duration, AVG(duration) as avg_duration FROM conversations"
        )
        
        message_stats = await db.fetch_one(
            "SELECT SUM(message_count) as total_messages, AVG(message_count) as avg_messages FROM conversations"
        )
        
        # Most recent conversation
        recent_conversation = await db.fetch_one(
            "SELECT timestamp FROM conversations ORDER BY timestamp DESC LIMIT 1"
        )
        
        return {
            "total_conversations": total_conversations,
            "call_conversations": call_conversations,
            "chat_conversations": chat_conversations,
            "total_duration": duration_stats["total_duration"] or 0,
            "average_duration": float(duration_stats["avg_duration"] or 0),
            "total_messages": message_stats["total_messages"] or 0,
            "average_messages": float(message_stats["avg_messages"] or 0),
            "most_recent": recent_conversation["timestamp"] if recent_conversation else None
        }