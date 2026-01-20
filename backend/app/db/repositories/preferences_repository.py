from typing import List, Optional, Any

from app.db.database import get_db
from app.models.preferences import Preferences


class PreferencesRepository:
    """Repository for preferences database operations"""
    
    @staticmethod
    async def get_by_key(key: str) -> Optional[Preferences]:
        """Get preference by key"""
        db = get_db()
        row = await db.fetch_one(
            "SELECT * FROM preferences WHERE key = ?", (key,)
        )
        return Preferences.from_dict(row) if row else None
    
    @staticmethod
    async def get_value(key: str, default: Any = None) -> Any:
        """Get typed preference value by key"""
        db = get_db()
        pref = await PreferencesRepository.get_by_key(key)
        if pref:
            return pref.get_typed_value()
        return default
    
    @staticmethod
    async def set_value(
        key: str, 
        value: Any, 
        value_type: str = "string",
        description: Optional[str] = None
    ) -> Preferences:
        """Set preference value (create or update)"""
        db = get_db()
        # Convert value to string for storage
        if value_type == "json":
            import json
            value_str = json.dumps(value)
        else:
            value_str = str(value)
        
        existing = await PreferencesRepository.get_by_key(key)
        
        if existing:
            # Update existing preference
            existing.value = value_str
            existing.value_type = value_type
            if description:
                existing.description = description
            
            await db.execute(
                """UPDATE preferences 
                   SET value = ?, value_type = ?, description = ?
                   WHERE key = ?""",
                (value_str, value_type, existing.description, key)
            )
        else:
            # Create new preference
            pref = Preferences(
                key=key,
                value=value_str,
                value_type=value_type,
                description=description
            )
            
            cursor = await db.execute(
                """INSERT INTO preferences (key, value, value_type, description)
                   VALUES (?, ?, ?, ?)""",
                (key, value_str, value_type, description)
            )
            pref.id = cursor.lastrowid
            existing = pref
        
        await db.commit()
        return existing
    
    @staticmethod
    async def get_all() -> List[Preferences]:
        """Get all preferences"""
        db = get_db()
        rows = await db.fetch_all("SELECT * FROM preferences ORDER BY key")
        return [Preferences.from_dict(row) for row in rows]
    
    @staticmethod
    async def delete(key: str) -> bool:
        """Delete a preference"""
        db = get_db()
        await db.execute("DELETE FROM preferences WHERE key = ?", (key,))
        await db.commit()
        return True
    
    @staticmethod
    async def get_multiple(keys: List[str]) -> dict:
        """Get multiple preferences as a dictionary"""
        db = get_db()
        placeholders = ", ".join(["?" for _ in keys])
        rows = await db.fetch_all(
            f"SELECT * FROM preferences WHERE key IN ({placeholders})",
            tuple(keys)
        )
        
        result = {}
        for row in rows:
            pref = Preferences.from_dict(row)
            result[pref.key] = pref.get_typed_value()
        
        return result