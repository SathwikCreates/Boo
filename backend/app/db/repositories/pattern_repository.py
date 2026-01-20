from typing import List, Optional
from datetime import date

from app.db.database import get_db
from app.models.pattern import Pattern


class PatternRepository:
    """Repository for pattern database operations"""
    
    @staticmethod
    async def create(pattern: Pattern) -> Pattern:
        db = get_db()
        """Create a new pattern"""
        data = pattern.to_dict()
        del data["id"]
        
        columns = ", ".join(data.keys())
        placeholders = ", ".join(["?" for _ in data])
        values = list(data.values())
        
        cursor = await db.execute(
            f"INSERT INTO patterns ({columns}) VALUES ({placeholders})",
            tuple(values)
        )
        await db.commit()
        
        pattern.id = cursor.lastrowid
        return pattern
    
    @staticmethod
    async def get_by_id(pattern_id: int) -> Optional[Pattern]:
        """Get pattern by ID"""
        db = get_db()
        row = await db.fetch_one(
            "SELECT * FROM patterns WHERE id = ?", (pattern_id,)
        )
        return Pattern.from_dict(row) if row else None
    
    @staticmethod
    async def get_all(
        pattern_type: Optional[str] = None,
        min_confidence: float = 0.0
    ) -> List[Pattern]:
        """Get all patterns with optional filters"""
        db = get_db()
        query = "SELECT * FROM patterns WHERE confidence >= ?"
        params = [min_confidence]
        
        if pattern_type:
            query += " AND pattern_type = ?"
            params.append(pattern_type)
        
        query += " ORDER BY confidence DESC, frequency DESC"
        
        rows = await db.fetch_all(query, tuple(params))
        return [Pattern.from_dict(row) for row in rows]
    
    @staticmethod
    async def update(pattern: Pattern) -> Pattern:
        """Update an existing pattern"""
        db = get_db()
        data = pattern.to_dict()
        pattern_id = data.pop("id")
        
        set_clause = ", ".join([f"{k} = ?" for k in data.keys()])
        values = list(data.values())
        values.append(pattern_id)
        
        await db.execute(
            f"UPDATE patterns SET {set_clause} WHERE id = ?",
            tuple(values)
        )
        await db.commit()
        
        return pattern
    
    @staticmethod
    async def delete(pattern_id: int) -> bool:
        """Delete a pattern"""
        db = get_db()
        await db.execute("DELETE FROM patterns WHERE id = ?", (pattern_id,))
        await db.commit()
        return True
    
    @staticmethod
    async def delete_all() -> bool:
        """Delete all patterns (for regeneration)"""
        db = get_db()
        await db.execute("DELETE FROM patterns")
        await db.commit()
        return True
    
    @staticmethod
    async def get_by_type(pattern_type: str) -> List[Pattern]:
        """Get patterns by type"""
        db = get_db()
        rows = await db.fetch_all(
            """SELECT * FROM patterns 
               WHERE pattern_type = ?
               ORDER BY confidence DESC, frequency DESC""",
            (pattern_type,)
        )
        return [Pattern.from_dict(row) for row in rows]
    
    @staticmethod
    async def update_last_seen(pattern_id: int, last_seen: date) -> bool:
        """Update the last seen date for a pattern"""
        db = get_db()
        await db.execute(
            "UPDATE patterns SET last_seen = ? WHERE id = ?",
            (last_seen.isoformat(), pattern_id)
        )
        await db.commit()
        return True
    
    @staticmethod
    async def increment_frequency(pattern_id: int) -> bool:
        """Increment the frequency count for a pattern"""
        db = get_db()
        await db.execute(
            "UPDATE patterns SET frequency = frequency + 1 WHERE id = ?",
            (pattern_id,)
        )
        await db.commit()
        return True