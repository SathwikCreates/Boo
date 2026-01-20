import aiosqlite
from typing import Optional
from datetime import datetime

from app.core.config import settings
from app.db.schema import ALL_TABLES, INDEXES
from app.db.migrations import run_migrations as run_db_migrations


class Database:
    def __init__(self):
        # Default to config path, but can be overridden by DatabaseManager
        self.db_path = settings.DATABASE_URL.replace("sqlite+aiosqlite:///", "")
        self._connection: Optional[aiosqlite.Connection] = None
        self._current_path: Optional[str] = None
    
    async def set_db_path(self, new_path: str):
        """Switch to a different database path"""
        if self.db_path != new_path:
            self.db_path = new_path
            # Force immediate disconnection to ensure clean switch
            if self._connection:
                await self.disconnect()
            self._current_path = None
    
    async def connect(self):
        """Create database connection"""
        # If we have a connection but path changed, close it first
        if self._connection and self._current_path != self.db_path:
            await self.disconnect()
        
        if not self._connection:
            self._connection = await aiosqlite.connect(self.db_path)
            self._connection.row_factory = aiosqlite.Row
            await self._connection.execute("PRAGMA foreign_keys = ON")
            self._current_path = self.db_path
    
    async def disconnect(self):
        """Close database connection"""
        if self._connection:
            await self._connection.close()
            self._connection = None
    
    async def execute(self, query: str, params: tuple = ()):
        """Execute a query"""
        if not self._connection:
            await self.connect()
        return await self._connection.execute(query, params)
    
    async def execute_many(self, query: str, params: list[tuple]):
        """Execute many queries"""
        if not self._connection:
            await self.connect()
        return await self._connection.executemany(query, params)
    
    async def fetch_one(self, query: str, params: tuple = ()):
        """Fetch one row"""
        cursor = await self.execute(query, params)
        row = await cursor.fetchone()
        return dict(row) if row else None
    
    async def fetch_all(self, query: str, params: tuple = ()):
        """Fetch all rows"""
        cursor = await self.execute(query, params)
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
    
    async def commit(self):
        """Commit transaction"""
        if self._connection:
            await self._connection.commit()
    
    async def rollback(self):
        """Rollback transaction"""
        if self._connection:
            await self._connection.rollback()


# Global database instance
db = Database()

def get_db():
    """Get the current database instance - use this for all database operations"""
    return db


async def create_tables():
    """Create all database tables"""
    # Create tables
    for table_sql in ALL_TABLES:
        await db.execute(table_sql)
    
    # Create indexes
    for index_sql in INDEXES:
        await db.execute(index_sql)
    
    await db.commit()


async def run_migrations():
    """Run database migrations"""
    await run_db_migrations(db)


async def init_db():
    """Initialize database with schema"""
    await db.connect()
    
    # Create tables
    await create_tables()
    
    # Run migrations
    await run_migrations()
    
    # Insert default preferences
    await initialize_default_preferences()
    
    print("Database initialized successfully")


async def initialize_default_preferences(db_instance=None):
    """Insert default preference values"""
    if db_instance is None:
        db_instance = db
    
    default_prefs = [
        ("hotkey", "F8", "string", "Global hotkey for voice recording"),
        ("ollama_port", "11434", "int", "Ollama server port"),
        ("ollama_model", "mistral:7b", "string", "Journal Processing - Default Ollama model"),
        ("ollama_temperature", "0.1", "float", "Journal Processing - Model temperature"),
        ("ollama_context_window", "4096", "int", "Journal Processing - Context window size"),
        ("talk_to_diary_model", "qwen3:8b", "string", "Talk to Your Diary - Ollama model"),
        ("talk_to_diary_temperature", "0.2", "float", "Talk to Your Diary - Model temperature"),
        ("talk_to_diary_context_window", "8192", "int", "Talk to Your Diary - Context window size"),
        ("whisper_model", "base", "string", "Whisper model size"),
        ("pattern_unlock_shown", "false", "bool", "Whether pattern unlock celebration was shown"),
        ("coffee_popup_shown", "false", "bool", "Whether coffee popup was shown"),
        ("coffee_popup_dismissed_date", "", "string", "Last date coffee popup was dismissed"),
        ("first_use_date", datetime.now().isoformat(), "string", "First use date of the application"),
    ]
    
    for key, value, value_type, description in default_prefs:
        # Check if preference already exists
        existing = await db_instance.fetch_one(
            "SELECT id FROM preferences WHERE key = ?", (key,)
        )
        if not existing:
            await db_instance.execute(
                """INSERT INTO preferences (key, value, value_type, description) 
                   VALUES (?, ?, ?, ?)""",
                (key, value, value_type, description)
            )
    
    await db_instance.commit()


async def initialize_preferences_for_db(db_path: str):
    """Initialize default preferences for a specific database file"""
    async with aiosqlite.connect(db_path) as temp_db:
        temp_db.row_factory = aiosqlite.Row
        
        # Create a temporary database wrapper
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
        await initialize_default_preferences(temp_db_instance)