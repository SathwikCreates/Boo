"""Database migration system"""
from datetime import datetime
from typing import List, Tuple


# Migration format: (version, description, up_sql, down_sql)
MIGRATIONS: List[Tuple[int, str, str, str]] = [
    (
        1,
        "Initial schema",
        """-- This migration is handled by schema.py create_tables()""",
        """-- Rollback not supported for initial schema"""
    ),
    (
        2,
        "Add keywords column to patterns table",
        """ALTER TABLE patterns ADD COLUMN keywords TEXT""",
        """ALTER TABLE patterns DROP COLUMN keywords"""
    ),
    (
        3,
        "Add conversations table for Talk to Your Diary feature",
        """CREATE TABLE IF NOT EXISTS conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME NOT NULL,
    duration INTEGER DEFAULT 0,
    transcription TEXT NOT NULL,
    conversation_type TEXT NOT NULL,
    message_count INTEGER DEFAULT 0,
    search_queries_used TEXT,
    created_at DATETIME NOT NULL,
    updated_at DATETIME
);
CREATE INDEX IF NOT EXISTS idx_conversations_timestamp ON conversations(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_conversations_type ON conversations(conversation_type);""",
        """DROP TABLE IF EXISTS conversations;"""
    ),
    (
        4,
        "Create agent_memories table",
        """CREATE TABLE IF NOT EXISTS agent_memories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    memory_type TEXT NOT NULL,
    content TEXT NOT NULL,
    key_entities TEXT,
    importance_score REAL DEFAULT 5.0,
    embedding TEXT,
    source_conversation_id INTEGER,
    related_entry_id INTEGER,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_accessed_at DATETIME,
    access_count INTEGER DEFAULT 0,
    is_active INTEGER DEFAULT 1,
    FOREIGN KEY (related_entry_id) REFERENCES entries(id),
    FOREIGN KEY (source_conversation_id) REFERENCES conversations(id)
);
CREATE INDEX IF NOT EXISTS idx_memory_type ON agent_memories(memory_type);
CREATE INDEX IF NOT EXISTS idx_memory_importance ON agent_memories(importance_score DESC);
CREATE INDEX IF NOT EXISTS idx_memory_active ON agent_memories(is_active);
CREATE INDEX IF NOT EXISTS idx_memory_entities ON agent_memories(key_entities);""",
        """DROP TABLE IF EXISTS agent_memories;"""
    ),
    (
        5,
        "Add smart_tags column to entries table",
        """ALTER TABLE entries ADD COLUMN smart_tags TEXT;
CREATE INDEX IF NOT EXISTS idx_entries_smart_tags ON entries(smart_tags);""",
        """DROP INDEX IF EXISTS idx_entries_smart_tags;
ALTER TABLE entries DROP COLUMN smart_tags;"""
    ),
    (
        6,
        "Add advanced memory scoring fields",
        """-- Add new scoring fields to agent_memories
ALTER TABLE agent_memories ADD COLUMN base_importance_score REAL DEFAULT 5.0;
ALTER TABLE agent_memories ADD COLUMN llm_importance_score REAL;
ALTER TABLE agent_memories ADD COLUMN user_score_adjustment REAL DEFAULT 0;
ALTER TABLE agent_memories ADD COLUMN final_importance_score REAL DEFAULT 5.0;
ALTER TABLE agent_memories ADD COLUMN user_rated INTEGER DEFAULT 0;
ALTER TABLE agent_memories ADD COLUMN score_source TEXT DEFAULT 'rule';
ALTER TABLE agent_memories ADD COLUMN llm_processed INTEGER DEFAULT 0;
ALTER TABLE agent_memories ADD COLUMN llm_processed_at DATETIME;
ALTER TABLE agent_memories ADD COLUMN user_rated_at DATETIME;
ALTER TABLE agent_memories ADD COLUMN decay_last_calculated DATETIME;
ALTER TABLE agent_memories ADD COLUMN effective_score_cache REAL;
ALTER TABLE agent_memories ADD COLUMN score_breakdown TEXT;
ALTER TABLE agent_memories ADD COLUMN marked_for_deletion INTEGER DEFAULT 0;
ALTER TABLE agent_memories ADD COLUMN marked_for_deletion_at DATETIME;
ALTER TABLE agent_memories ADD COLUMN deletion_reason TEXT;
ALTER TABLE agent_memories ADD COLUMN archived INTEGER DEFAULT 0;
ALTER TABLE agent_memories ADD COLUMN archived_at DATETIME;

-- Create indexes for new fields
CREATE INDEX IF NOT EXISTS idx_memory_user_rated ON agent_memories(user_rated);
CREATE INDEX IF NOT EXISTS idx_memory_llm_processed ON agent_memories(llm_processed);
CREATE INDEX IF NOT EXISTS idx_memory_final_score ON agent_memories(final_importance_score DESC);
CREATE INDEX IF NOT EXISTS idx_memory_marked_deletion ON agent_memories(marked_for_deletion);
CREATE INDEX IF NOT EXISTS idx_memory_archived ON agent_memories(archived);""",
        """-- Rollback: Drop indexes and columns
DROP INDEX IF EXISTS idx_memory_user_rated;
DROP INDEX IF EXISTS idx_memory_llm_processed;
DROP INDEX IF EXISTS idx_memory_final_score;
DROP INDEX IF EXISTS idx_memory_marked_deletion;
DROP INDEX IF EXISTS idx_memory_archived;"""
    ),
    (
        7,
        "Add memory extraction tracking columns",
        """-- Add memory_extracted columns to entries table
ALTER TABLE entries ADD COLUMN memory_extracted INTEGER DEFAULT 0;
ALTER TABLE entries ADD COLUMN memory_extracted_llm INTEGER DEFAULT 0;
ALTER TABLE entries ADD COLUMN memory_extracted_at DATETIME;

-- Add memory_extracted columns to conversations table  
ALTER TABLE conversations ADD COLUMN memory_extracted INTEGER DEFAULT 0;
ALTER TABLE conversations ADD COLUMN memory_extracted_llm INTEGER DEFAULT 0;
ALTER TABLE conversations ADD COLUMN memory_extracted_at DATETIME;

-- Create indexes for efficient querying
CREATE INDEX IF NOT EXISTS idx_entries_memory_extracted ON entries(memory_extracted);
CREATE INDEX IF NOT EXISTS idx_conversations_memory_extracted ON conversations(memory_extracted);
CREATE INDEX IF NOT EXISTS idx_entries_memory_extracted_llm ON entries(memory_extracted_llm);
CREATE INDEX IF NOT EXISTS idx_conversations_memory_extracted_llm ON conversations(memory_extracted_llm);""",
        """-- Rollback: Drop indexes and columns
DROP INDEX IF EXISTS idx_entries_memory_extracted;
DROP INDEX IF EXISTS idx_conversations_memory_extracted;
DROP INDEX IF EXISTS idx_entries_memory_extracted_llm;
DROP INDEX IF EXISTS idx_conversations_memory_extracted_llm;
ALTER TABLE entries DROP COLUMN memory_extracted;
ALTER TABLE entries DROP COLUMN memory_extracted_llm;
ALTER TABLE entries DROP COLUMN memory_extracted_at;
ALTER TABLE conversations DROP COLUMN memory_extracted;
ALTER TABLE conversations DROP COLUMN memory_extracted_llm;
ALTER TABLE conversations DROP COLUMN memory_extracted_at;"""
    ),
]


async def get_current_version(db=None) -> int:
    """Get current schema version"""
    if db is None:
        from app.db.database import get_db
        db = get_db()
    try:
        result = await db.fetch_one(
            "SELECT MAX(version) as version FROM schema_version"
        )
        return result["version"] if result and result["version"] else 0
    except:
        # Table doesn't exist yet
        return 0


async def apply_migration(db, version: int, description: str, up_sql: str):
    """Apply a single migration"""
    if db is None:
        from app.db.database import get_db
        db = get_db()
    if up_sql.strip() and not up_sql.strip().startswith("--"):
        # Split multiple statements by semicolon and execute each one
        statements = [stmt.strip() for stmt in up_sql.split(';') if stmt.strip()]
        for statement in statements:
            # Skip comment-only statements
            if statement.startswith('--') or not statement:
                continue
            try:
                await db.execute(statement)
            except Exception as e:
                # Check if it's a harmless "already exists" error
                error_msg = str(e).lower()
                if any(phrase in error_msg for phrase in [
                    "duplicate column name",
                    "table already exists", 
                    "index already exists",
                    "column already exists"
                ]):
                    print(f"Migration {version}: Skipping statement (already exists): {statement}")
                    continue
                else:
                    print(f"Migration {version} failed on statement: {statement}")
                    print(f"Error: {e}")
                    raise
    
    await db.execute(
        "INSERT INTO schema_version (version, applied_at, description) VALUES (?, ?, ?)",
        (version, datetime.now().isoformat(), description)
    )
    await db.commit()
    print(f"Applied migration {version}: {description}")


async def run_migrations(db=None):
    """Run all pending migrations"""
    if db is None:
        from app.db.database import get_db
        db = get_db()
    current_version = await get_current_version(db)
    print(f"Current database version: {current_version}")
    
    for version, description, up_sql, _ in MIGRATIONS:
        print(f"Checking migration {version}: {description}")
        if version > current_version:
            print(f"Applying migration {version}: {description}")
            await apply_migration(db, version, description, up_sql)
        else:
            print(f"Skipping migration {version} (already applied)")
    
    final_version = await get_current_version(db)
    if final_version > current_version:
        print(f"Database migrated from version {current_version} to {final_version}")
    else:
        print(f"Database is up to date at version {final_version}")