import os
import shutil
import aiosqlite
from typing import Optional, Dict, Any
from pathlib import Path

from .user_registry_service import get_user_registry_service
from ..db.schema import create_tables
from ..db.database import db, initialize_preferences_for_db, get_db
from ..db.migrations import run_migrations


class DatabaseManager:
    """Service for managing user-specific databases and switching contexts"""
    
    def __init__(self):
        self.current_user_id: Optional[int] = None
        self.user_db_path: Optional[str] = None
        self.user_registry = get_user_registry_service()
    
    async def switch_to_user(self, user_id: int) -> Dict[str, Any]:
        """Switch active database to specified user"""
        user = await self.user_registry.get_user_by_id(user_id)
        if not user:
            raise ValueError("User not found")
        
        self.current_user_id = user_id
        self.user_db_path = user['database_path']
        
        # Ensure user's database directory exists
        os.makedirs(os.path.dirname(self.user_db_path), exist_ok=True)
        
        # Initialize user's database if it doesn't exist
        if not os.path.exists(self.user_db_path):
            await self._initialize_user_database(self.user_db_path)
        
        # CRITICAL: Switch the global database instance to this user's database
        await db.set_db_path(self.user_db_path)
        
        return user
    
    def get_current_db_path(self) -> str:
        """Get current user's database path"""
        if not self.user_db_path:
            raise ValueError("No user session active")
        return self.user_db_path
    
    def get_current_user_id(self) -> int:
        """Get current user's ID"""
        if not self.current_user_id:
            raise ValueError("No user session active")
        return self.current_user_id
    
    async def get_current_user(self) -> Optional[Dict[str, Any]]:
        """Get current user information"""
        if not self.current_user_id:
            return None
        return await self.user_registry.get_user_by_id(self.current_user_id)
    
    async def clear_session(self):
        """Clear current user session"""
        self.current_user_id = None
        self.user_db_path = None
        
        # Reset global database to default path when clearing session
        from ..core.config import settings
        default_path = settings.DATABASE_URL.replace("sqlite+aiosqlite:///", "")
        await db.set_db_path(default_path)
    
    async def _initialize_user_database(self, db_path: str):
        """Create new user database with complete schema matching main database"""
        print(f"Initializing user database at: {db_path}")
        
        # Temporarily switch the global db to this path to use init_db()
        original_path = db.db_path
        await db.set_db_path(db_path)
        
        try:
            # Use the exact same initialization process as main database
            from ..db.database import init_db
            await init_db()
            print(f"User database initialization complete: {db_path}")
        finally:
            # Restore original db path
            await db.set_db_path(original_path)
    
    async def _run_migrations_for_db(self, db_path: str):
        """Run migrations on a specific database file"""
        print(f"Running migrations for user database: {db_path}")
        try:
            async with aiosqlite.connect(db_path) as temp_db:
                temp_db.row_factory = aiosqlite.Row
                
                # Create a temporary database wrapper that matches the expected interface
                class TempDB:
                    def __init__(self, connection):
                        self.connection = connection
                    
                    async def fetch_one(self, query, params=()):
                        cursor = await self.connection.execute(query, params)
                        row = await cursor.fetchone()
                        return dict(row) if row else None
                    
                    async def execute(self, query, params=()):
                        return await self.connection.execute(query, params)
                    
                    async def commit(self):
                        await self.connection.commit()
                
                temp_db_instance = TempDB(temp_db)
                await run_migrations(temp_db_instance)
                print(f"Migrations completed for user database: {db_path}")
        except Exception as e:
            print(f"Error running migrations on user database {db_path}: {e}")
            raise
    
    async def create_user_database(self, username: str) -> str:
        """Create a new user database and return its path"""
        user_dir = f"app_data/users/{username}"
        db_path = f"{user_dir}/boo.db"
        
        # Ensure directory exists
        os.makedirs(user_dir, exist_ok=True)
        
        # Initialize the database
        await self._initialize_user_database(db_path)
        
        return db_path
    
    async def backup_database(self, user_id: int, backup_path: str):
        """Create a backup of user's database"""
        user = await self.user_registry.get_user_by_id(user_id)
        if not user:
            raise ValueError("User not found")
        
        source_path = user['database_path']
        if not os.path.exists(source_path):
            raise ValueError("User database not found")
        
        # Ensure backup directory exists
        os.makedirs(os.path.dirname(backup_path), exist_ok=True)
        
        # Copy database file
        shutil.copy2(source_path, backup_path)
    
    async def restore_database(self, user_id: int, backup_path: str):
        """Restore user's database from backup"""
        if not os.path.exists(backup_path):
            raise ValueError("Backup file not found")
        
        user = await self.user_registry.get_user_by_id(user_id)
        if not user:
            raise ValueError("User not found")
        
        target_path = user['database_path']
        
        # Ensure target directory exists
        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        
        # Copy backup to target location
        shutil.copy2(backup_path, target_path)
    
    async def migrate_single_user_to_multi_user(self, old_db_path: str = "boo.db", default_username: str = "user1", default_display_name: str = "Default User"):
        """Migrate existing single-user installation to multi-user structure"""
        
        # Check if old database exists
        if not os.path.exists(old_db_path):
            return False  # Nothing to migrate
        
        # Check if user registry already exists (already migrated)
        if os.path.exists("app_data/shared/user_registry.db"):
            return False  # Already migrated
        
        # Initialize user registry
        await self.user_registry.initialize()
        
        # Create user directory
        new_db_path = await self.create_user_database(default_username)
        
        # Move old database to new location
        shutil.move(old_db_path, new_db_path)
        
        # Create registry entry (password will be set during first login)
        await self.user_registry.create_user(
            username=default_username,
            display_name=default_display_name,
            password_hash="",  # Will be set during setup
            database_path=new_db_path
        )
        
        return True
    
    def is_session_active(self) -> bool:
        """Check if there's an active user session"""
        return self.current_user_id is not None
    
    async def get_database_info(self, user_id: int) -> Dict[str, Any]:
        """Get database information for a user"""
        user = await self.user_registry.get_user_by_id(user_id)
        if not user:
            raise ValueError("User not found")
        
        db_path = user['database_path']
        info = {
            "path": db_path,
            "exists": os.path.exists(db_path),
            "size": 0,
            "created": None,
            "modified": None
        }
        
        if info["exists"]:
            stat = os.stat(db_path)
            info["size"] = stat.st_size
            info["created"] = stat.st_ctime
            info["modified"] = stat.st_mtime
        
        return info


# Singleton instance
_database_manager = None

def get_database_manager() -> DatabaseManager:
    """Get singleton DatabaseManager instance"""
    global _database_manager
    if _database_manager is None:
        _database_manager = DatabaseManager()
    return _database_manager