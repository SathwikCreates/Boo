from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta

from app.db.database import get_db
from app.models.entry import Entry


class EntryRepository:
    """Repository for entry database operations"""
    
    @staticmethod
    async def create(entry: Entry) -> Entry:
        """Create a new entry"""
        data = entry.to_dict()
        del data["id"]  # Remove id for insert
        
        columns = ", ".join(data.keys())
        placeholders = ", ".join(["?" for _ in data])
        values = list(data.values())
        
        db = get_db()
        cursor = await db.execute(
            f"INSERT INTO entries ({columns}) VALUES ({placeholders})",
            tuple(values)
        )
        await db.commit()
        
        entry.id = cursor.lastrowid
        return entry
    
    @staticmethod
    async def get_by_id(entry_id: int) -> Optional[Entry]:
        """Get entry by ID"""
        db = get_db()
        row = await db.fetch_one(
            "SELECT * FROM entries WHERE id = ?", (entry_id,)
        )
        return Entry.from_dict(row) if row else None
    
    @staticmethod
    async def get_all(
        limit: int = 100, 
        offset: int = 0,
        mode: Optional[str] = None
    ) -> List[Entry]:
        """Get all entries with pagination"""
        query = "SELECT * FROM entries"
        params = []
        
        if mode:
            query += " WHERE mode = ?"
            params.append(mode)
        
        query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        
        db = get_db()
        rows = await db.fetch_all(query, tuple(params))
        return [Entry.from_dict(row) for row in rows]
    
    @staticmethod
    async def update(entry: Entry) -> Entry:
        """Update an existing entry"""
        db = get_db()
        data = entry.to_dict()
        entry_id = data.pop("id")
        
        set_clause = ", ".join([f"{k} = ?" for k in data.keys()])
        values = list(data.values())
        values.append(entry_id)
        
        await db.execute(
            f"UPDATE entries SET {set_clause} WHERE id = ?",
            tuple(values)
        )
        await db.commit()
        
        return entry
    
    @staticmethod
    async def delete(entry_id: int) -> bool:
        """Delete an entry and related memories"""
        db = get_db()
        try:
            # First delete related agent_memories to avoid foreign key constraint violation
            await db.execute(
                "DELETE FROM agent_memories WHERE related_entry_id = ?", 
                (entry_id,)
            )
            
            # Then delete the entry
            cursor = await db.execute(
                "DELETE FROM entries WHERE id = ?", (entry_id,)
            )
            await db.commit()
            return cursor.rowcount > 0
        except Exception as e:
            await db.rollback()
            raise e
    
    @staticmethod
    async def count() -> int:
        """Get total count of entries"""
        db = get_db()
        result = await db.fetch_one("SELECT COUNT(*) as count FROM entries")
        return result["count"] if result else 0
    
    @staticmethod
    async def get_all_for_streak() -> List[Entry]:
        """Get all entries for streak calculation (no pagination limit)"""
        db = get_db()
        rows = await db.fetch_all(
            "SELECT * FROM entries ORDER BY timestamp DESC"
        )
        # Handle new memory columns gracefully
        entries = []
        for row in rows:
            try:
                # Convert row to dict and ensure all fields exist
                row_dict = dict(row)
                # Set defaults for new fields if they don't exist
                if 'memory_extracted' not in row_dict:
                    row_dict['memory_extracted'] = 0
                if 'memory_extracted_llm' not in row_dict:
                    row_dict['memory_extracted_llm'] = 0
                if 'memory_extracted_at' not in row_dict:
                    row_dict['memory_extracted_at'] = None
                    
                entry = Entry.from_dict(row_dict)
                entries.append(entry)
            except Exception as e:
                # Skip problematic entries but log them
                continue
        return entries
    
    @staticmethod
    async def search(
        query: str,
        limit: int = 50
    ) -> List[Entry]:
        """Search entries by text content"""
        search_query = f"%{query}%"
        db = get_db()
        rows = await db.fetch_all(
            """SELECT * FROM entries 
               WHERE raw_text LIKE ? 
                  OR enhanced_text LIKE ? 
                  OR structured_summary LIKE ?
               ORDER BY timestamp DESC
               LIMIT ?""",
            (search_query, search_query, search_query, limit)
        )
        return [Entry.from_dict(row) for row in rows]
    
    @staticmethod
    async def get_by_date_range(
        start_date: datetime,
        end_date: datetime
    ) -> List[Entry]:
        """Get entries within a date range"""
        db = get_db()
        rows = await db.fetch_all(
            """SELECT * FROM entries 
               WHERE timestamp BETWEEN ? AND ?
               ORDER BY timestamp DESC""",
            (start_date.isoformat(), end_date.isoformat())
        )
        return [Entry.from_dict(row) for row in rows]
    
    @staticmethod
    async def get_recent(days: int = 7) -> List[Entry]:
        """Get recent entries from the last N days"""
        start_date = datetime.now() - timedelta(days=days)
        return await EntryRepository.get_by_date_range(
            start_date, datetime.now()
        )
    
    @staticmethod
    async def get_entries_without_embeddings(limit: int = 100) -> List[Entry]:
        """Get entries that don't have embeddings yet"""
        db = get_db()
        rows = await db.fetch_all(
            """SELECT * FROM entries 
               WHERE embeddings IS NULL OR embeddings = '[]' OR embeddings = ''
               ORDER BY timestamp DESC
               LIMIT ?""",
            (limit,)
        )
        return [Entry.from_dict(row) for row in rows]
    
    @staticmethod
    async def get_entries_with_embeddings(
        limit: Optional[int] = 100, 
        offset: int = 0,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        mood_tags: Optional[List[str]] = None
    ) -> List[Entry]:
        """Get entries that have embeddings for similarity search with optional filtering"""
        # Base query
        query = """SELECT * FROM entries 
                   WHERE embeddings IS NOT NULL AND embeddings != '[]' AND embeddings != ''"""
        params = []
        
        # Add date filtering if specified
        if start_date:
            query += " AND timestamp >= ?"
            params.append(start_date)
        
        if end_date:
            query += " AND timestamp <= ?"
            params.append(end_date)
        
        # Add mood tag filtering if specified
        if mood_tags:
            # Use JSON_EXTRACT or LIKE for mood tag filtering (SQLite JSON support)
            mood_conditions = []
            for mood_tag in mood_tags:
                mood_conditions.append("mood_tags LIKE ?")
                params.append(f'%"{mood_tag}"%')
            
            if mood_conditions:
                query += f" AND ({' OR '.join(mood_conditions)})"
        
        # Add ordering
        query += " ORDER BY timestamp DESC"
        
        # Add pagination only if limit is specified
        if limit is not None:
            query += " LIMIT ? OFFSET ?"
            params.extend([limit, offset])
        
        db = get_db()
        rows = await db.fetch_all(query, tuple(params))
        return [Entry.from_dict(row) for row in rows]
    
    @staticmethod
    async def update_embedding(entry_id: int, embeddings: List[float]) -> bool:
        """Update only the embeddings field for an entry"""
        import json
        embeddings_json = json.dumps(embeddings)
        
        db = get_db()
        await db.execute(
            "UPDATE entries SET embeddings = ? WHERE id = ?",
            (embeddings_json, entry_id)
        )
        await db.commit()
        return True
    
    @staticmethod
    async def count_entries_with_embeddings() -> int:
        """Count entries that have embeddings"""
        db = get_db()
        result = await db.fetch_one(
            """SELECT COUNT(*) as count FROM entries 
               WHERE embeddings IS NOT NULL AND embeddings != '[]' AND embeddings != '' AND LENGTH(embeddings) > 2"""
        )
        return result["count"] if result else 0
    
    @staticmethod
    async def count_entries_without_embeddings() -> int:
        """Count entries that don't have embeddings"""
        db = get_db()
        result = await db.fetch_one(
            """SELECT COUNT(*) as count FROM entries 
               WHERE embeddings IS NULL OR embeddings = '[]' OR embeddings = ''"""
        )
        return result["count"] if result else 0
    
    @staticmethod
    async def get_entries_before_timestamp(timestamp: datetime, limit: int = 5) -> List[Entry]:
        """Get entries before a specific timestamp"""
        db = get_db()
        rows = await db.fetch_all(
            "SELECT * FROM entries WHERE timestamp < ? ORDER BY timestamp DESC LIMIT ?",
            (timestamp, limit)
        )
        return [Entry.from_dict(row) for row in rows]
    
    @staticmethod
    async def get_entries_after_timestamp(timestamp: datetime, limit: int = 5) -> List[Entry]:
        """Get entries after a specific timestamp"""
        db = get_db()
        rows = await db.fetch_all(
            "SELECT * FROM entries WHERE timestamp > ? ORDER BY timestamp ASC LIMIT ?",
            (timestamp, limit)
        )
        return [Entry.from_dict(row) for row in rows]
    
    @staticmethod
    async def clear_all_embeddings() -> int:
        """Clear all embeddings from all entries. Returns count of affected rows."""
        import logging
        logger = logging.getLogger(__name__)
        
        # First, count how many entries have embeddings
        before_count = await EntryRepository.count_entries_with_embeddings()
        logger.info(f"Before clearing: {before_count} entries have embeddings")
        
        if before_count == 0:
            logger.warning("No entries have embeddings to clear!")
            return 0
        
        # Clear all embeddings - try multiple approaches
        db = get_db()
        try:
            # Method 1: Update with NULL
            await db.execute(
                "UPDATE entries SET embeddings = NULL WHERE embeddings IS NOT NULL"
            )
            await db.commit()
            
            # Method 2: Also clear empty arrays and empty strings
            await db.execute(
                "UPDATE entries SET embeddings = NULL WHERE embeddings = '[]' OR embeddings = ''"
            )
            await db.commit()
            
        except Exception as e:
            logger.error(f"Error clearing embeddings: {e}")
            # Try direct approach
            await db.execute("UPDATE entries SET embeddings = NULL")
            await db.commit()
        
        # Verify they were cleared
        after_count = await EntryRepository.count_entries_with_embeddings()
        logger.info(f"After clearing: {after_count} entries have embeddings")
        
        return before_count  # Return how many were cleared
    
    @staticmethod
    async def get_all_entries_for_embedding_generation() -> List[Entry]:
        """Get all entries for embedding generation (no pagination)"""
        db = get_db()
        rows = await db.fetch_all(
            """SELECT id, raw_text, enhanced_text, structured_summary, mode, 
                      embeddings, timestamp, mood_tags, word_count, processing_metadata
               FROM entries 
               ORDER BY id ASC"""
        )
        return [Entry.from_dict(row) for row in rows]