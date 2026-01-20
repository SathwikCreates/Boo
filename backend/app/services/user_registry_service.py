import asyncio
import aiosqlite
import os
import uuid
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from pathlib import Path

from ..db.user_registry_schema import USER_REGISTRY_SCHEMA
from ..db.database import get_db


class UserRegistryService:
    """Service for managing the shared user registry database"""
    
    def __init__(self, registry_path: str = "app_data/shared/user_registry.db"):
        self.registry_path = registry_path
        self._ensure_directory()
    
    def _ensure_directory(self):
        """Ensure the shared directory exists"""
        os.makedirs(os.path.dirname(self.registry_path), exist_ok=True)
    
    async def initialize(self):
        """Initialize the user registry database with schema"""
        async with aiosqlite.connect(self.registry_path) as db:
            await db.executescript(USER_REGISTRY_SCHEMA)
            await db.commit()
    
    async def create_user(
        self,
        username: str,
        display_name: str,
        password_hash: str,
        secret_phrase_hash: Optional[str] = None,
        recovery_key: Optional[str] = None,
        database_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a new user in the registry"""
        
        # Generate recovery key if not provided
        if not recovery_key:
            recovery_key = str(uuid.uuid4())
        
        # Generate database path if not provided
        if not database_path:
            database_path = f"app_data/users/{username}/boo.db"
        
        async with aiosqlite.connect(self.registry_path) as db:
            try:
                cursor = await db.execute("""
                    INSERT INTO users (
                        username, display_name, password_hash, 
                        secret_phrase_hash, recovery_key, database_path
                    ) VALUES (?, ?, ?, ?, ?, ?)
                """, (username, display_name, password_hash, secret_phrase_hash, recovery_key, database_path))
                
                await db.commit()
                user_id = cursor.lastrowid
                
                return await self.get_user_by_id(user_id)
                
            except aiosqlite.IntegrityError as e:
                if "username" in str(e):
                    raise ValueError("Username already exists")
                raise ValueError(f"Failed to create user: {str(e)}")
    
    async def get_user_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        """Get user by username"""
        async with aiosqlite.connect(self.registry_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("""
                SELECT * FROM users WHERE username = ? AND is_active = TRUE
            """, (username,))
            row = await cursor.fetchone()
            return dict(row) if row else None
    
    async def get_user_by_id(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get user by ID"""
        async with aiosqlite.connect(self.registry_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("""
                SELECT * FROM users WHERE id = ? AND is_active = TRUE
            """, (user_id,))
            row = await cursor.fetchone()
            return dict(row) if row else None
    
    async def list_users(self) -> List[Dict[str, Any]]:
        """List all active users (username and display_name only for security)"""
        async with aiosqlite.connect(self.registry_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("""
                SELECT id, username, display_name, created_at, last_login 
                FROM users WHERE is_active = TRUE
                ORDER BY display_name
            """)
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    
    async def update_last_login(self, user_id: int):
        """Update user's last login timestamp"""
        async with aiosqlite.connect(self.registry_path) as db:
            await db.execute("""
                UPDATE users SET last_login = CURRENT_TIMESTAMP 
                WHERE id = ?
            """, (user_id,))
            await db.commit()
    
    async def increment_failed_attempts(self, user_id: int) -> int:
        """Increment failed login attempts and return new count"""
        async with aiosqlite.connect(self.registry_path) as db:
            await db.execute("""
                UPDATE users SET failed_login_attempts = failed_login_attempts + 1
                WHERE id = ?
            """, (user_id,))
            await db.commit()
            
            cursor = await db.execute("""
                SELECT failed_login_attempts FROM users WHERE id = ?
            """, (user_id,))
            result = await cursor.fetchone()
            return result[0] if result else 0
    
    async def reset_failed_attempts(self, user_id: int):
        """Reset failed login attempts to 0"""
        async with aiosqlite.connect(self.registry_path) as db:
            await db.execute("""
                UPDATE users SET failed_login_attempts = 0 
                WHERE id = ?
            """, (user_id,))
            await db.commit()
    
    async def lock_account(self, user_id: int, lock_duration_minutes: int = 60):
        """Temporarily lock user account"""
        unlock_time = datetime.now() + timedelta(minutes=lock_duration_minutes)
        
        async with aiosqlite.connect(self.registry_path) as db:
            await db.execute("""
                UPDATE users SET account_locked_until = ?
                WHERE id = ?
            """, (unlock_time.isoformat(), user_id))
            await db.commit()
    
    async def is_account_locked(self, user_id: int) -> bool:
        """Check if account is currently locked"""
        async with aiosqlite.connect(self.registry_path) as db:
            cursor = await db.execute("""
                SELECT account_locked_until FROM users WHERE id = ?
            """, (user_id,))
            result = await cursor.fetchone()
            
            if not result or not result[0]:
                return False
            
            lock_time = datetime.fromisoformat(result[0])
            return datetime.now() < lock_time
    
    async def update_display_name(self, user_id: int, new_display_name: str):
        """Update user's display name"""
        async with aiosqlite.connect(self.registry_path) as db:
            await db.execute("""
                UPDATE users SET display_name = ? WHERE id = ?
            """, (new_display_name, user_id))
            await db.commit()
    
    async def update_password_hash(self, user_id: int, new_password_hash: str):
        """Update user's password hash"""
        async with aiosqlite.connect(self.registry_path) as db:
            await db.execute("""
                UPDATE users SET password_hash = ? WHERE id = ?
            """, (new_password_hash, user_id))
            await db.commit()
    
    async def update_secret_phrase_hash(self, user_id: int, new_phrase_hash: str):
        """Update user's recovery phrase hash"""
        async with aiosqlite.connect(self.registry_path) as db:
            await db.execute("""
                UPDATE users SET secret_phrase_hash = ? WHERE id = ?
            """, (new_phrase_hash, user_id))
            await db.commit()
    
    async def deactivate_user(self, user_id: int):
        """Deactivate user account (soft delete)"""
        async with aiosqlite.connect(self.registry_path) as db:
            await db.execute("""
                UPDATE users SET is_active = FALSE WHERE id = ?
            """, (user_id,))
            await db.commit()
    
    async def user_exists(self, username: str) -> bool:
        """Check if username already exists"""
        user = await self.get_user_by_username(username)
        return user is not None
    
    async def cleanup_expired_locks(self):
        """Remove expired account locks"""
        async with aiosqlite.connect(self.registry_path) as db:
            await db.execute("""
                UPDATE users SET account_locked_until = NULL 
                WHERE account_locked_until < datetime('now')
            """)
            await db.commit()


# Singleton instance
_user_registry_service = None

def get_user_registry_service() -> UserRegistryService:
    """Get singleton UserRegistryService instance"""
    global _user_registry_service
    if _user_registry_service is None:
        _user_registry_service = UserRegistryService()
    return _user_registry_service