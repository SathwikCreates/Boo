from typing import Optional
from datetime import datetime

from app.db.database import get_db
from app.models.draft import Draft


class DraftRepository:
    """Repository for draft database operations"""
    
    @staticmethod
    async def create(draft: Draft) -> Draft:
        """Create a new draft"""
        db = get_db()
        data = draft.to_dict()
        del data["id"]
        
        columns = ", ".join(data.keys())
        placeholders = ", ".join(["?" for _ in data])
        values = list(data.values())
        
        cursor = await db.execute(
            f"INSERT INTO drafts ({columns}) VALUES ({placeholders})",
            tuple(values)
        )
        await db.commit()
        
        draft.id = cursor.lastrowid
        return draft
    
    @staticmethod
    async def get_latest() -> Optional[Draft]:
        """Get the most recent draft"""
        db = get_db()
        row = await db.fetch_one(
            """SELECT * FROM drafts 
               ORDER BY updated_at DESC, created_at DESC 
               LIMIT 1"""
        )
        return Draft.from_dict(row) if row else None
    
    @staticmethod
    async def get_by_id(draft_id: int) -> Optional[Draft]:
        """Get draft by ID"""
        db = get_db()
        row = await db.fetch_one(
            "SELECT * FROM drafts WHERE id = ?", (draft_id,)
        )
        return Draft.from_dict(row) if row else None
    
    @staticmethod
    async def update(draft: Draft) -> Draft:
        """Update an existing draft"""
        db = get_db()
        draft.updated_at = datetime.now()
        data = draft.to_dict()
        draft_id = data.pop("id")
        
        set_clause = ", ".join([f"{k} = ?" for k in data.keys()])
        values = list(data.values())
        values.append(draft_id)
        
        await db.execute(
            f"UPDATE drafts SET {set_clause} WHERE id = ?",
            tuple(values)
        )
        await db.commit()
        
        return draft
    
    @staticmethod
    async def save_or_update(content: str, metadata: Optional[dict] = None) -> Draft:
        """Save draft content, always updating the latest draft (one draft at a time)"""
        # Clean up - ensure only one draft exists
        await DraftRepository.cleanup_old_drafts_keep_one()
        
        latest = await DraftRepository.get_latest()
        
        # If there's any existing draft, update it
        if latest:
            latest.content = content
            # Always update metadata - new metadata takes precedence
            if metadata is not None:
                latest.metadata = metadata
            return await DraftRepository.update(latest)
        
        # Otherwise create a new draft (first time)
        draft = Draft(content=content, metadata=metadata)
        return await DraftRepository.create(draft)
    
    @staticmethod
    async def cleanup_old_drafts_keep_one() -> int:
        """Keep only the most recent draft, delete all others"""
        db = get_db()
        # Get all drafts ordered by most recent first
        rows = await db.fetch_all(
            """SELECT id FROM drafts 
               ORDER BY updated_at DESC, created_at DESC"""
        )
        
        if len(rows) <= 1:
            return 0  # Nothing to clean up
        
        # Keep the first (most recent), delete the rest
        draft_ids_to_delete = [row["id"] for row in rows[1:]]
        
        deleted_count = 0
        for draft_id in draft_ids_to_delete:
            await db.execute("DELETE FROM drafts WHERE id = ?", (draft_id,))
            deleted_count += 1
        
        await db.commit()
        return deleted_count
    
    @staticmethod
    async def delete(draft_id: int) -> bool:
        """Delete a draft"""
        db = get_db()
        await db.execute("DELETE FROM drafts WHERE id = ?", (draft_id,))
        await db.commit()
        return True
    
    @staticmethod
    async def delete_old_drafts(days: int = 7) -> int:
        """Delete drafts older than specified days"""
        db = get_db()
        cutoff_date = datetime.now()
        cutoff_date = cutoff_date.replace(
            day=cutoff_date.day - days if cutoff_date.day > days else 1
        )
        
        cursor = await db.execute(
            "DELETE FROM drafts WHERE created_at < ?",
            (cutoff_date.isoformat(),)
        )
        await db.commit()
        
        return cursor.rowcount