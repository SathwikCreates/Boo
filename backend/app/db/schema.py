"""Database schema definitions"""

import aiosqlite

# Entries table
ENTRIES_TABLE = """
CREATE TABLE IF NOT EXISTS entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    raw_text TEXT NOT NULL,
    enhanced_text TEXT,
    structured_summary TEXT,
    mode TEXT NOT NULL DEFAULT 'raw',
    embeddings TEXT,  -- JSON array of floats
    timestamp DATETIME NOT NULL,
    mood_tags TEXT,   -- JSON array of strings
    word_count INTEGER DEFAULT 0,
    processing_metadata TEXT,  -- JSON object for AI processing info
    smart_tags TEXT,  -- JSON array for smart tags
    memory_extracted INTEGER DEFAULT 0,
    memory_extracted_llm INTEGER DEFAULT 0,
    memory_extracted_at DATETIME
)
"""

# Patterns table
PATTERNS_TABLE = """
CREATE TABLE IF NOT EXISTS patterns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pattern_type TEXT NOT NULL,  -- 'mood', 'topic', 'behavior', 'temporal'
    description TEXT NOT NULL,
    frequency INTEGER DEFAULT 0,
    confidence REAL DEFAULT 0.0,
    first_seen DATE,
    last_seen DATE,
    related_entries TEXT,  -- JSON array of entry IDs
    keywords TEXT  -- JSON array of keywords
)
"""

# Preferences table
PREFERENCES_TABLE = """
CREATE TABLE IF NOT EXISTS preferences (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key TEXT UNIQUE NOT NULL,
    value TEXT NOT NULL,
    value_type TEXT DEFAULT 'string',  -- string, int, float, bool, json
    description TEXT
)
"""

# Drafts table for auto-save
DRAFTS_TABLE = """
CREATE TABLE IF NOT EXISTS drafts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content TEXT NOT NULL,
    metadata TEXT,  -- JSON object
    created_at DATETIME NOT NULL,
    updated_at DATETIME
)
"""

# Conversations table for Talk to Your Diary feature
CONVERSATIONS_TABLE = """
CREATE TABLE IF NOT EXISTS conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME NOT NULL,
    duration INTEGER DEFAULT 0,  -- in seconds
    transcription TEXT NOT NULL,
    conversation_type TEXT NOT NULL,  -- 'call' or 'chat'
    message_count INTEGER DEFAULT 0,
    search_queries_used TEXT,  -- JSON array
    created_at DATETIME NOT NULL,
    updated_at DATETIME,
    embedding TEXT,
    summary TEXT,
    key_topics TEXT,
    memory_extracted INTEGER DEFAULT 0,
    memory_extracted_llm INTEGER DEFAULT 0,
    memory_extracted_at DATETIME
)
"""

# Agent memories table for the memory system
AGENT_MEMORIES_TABLE = """
CREATE TABLE IF NOT EXISTS agent_memories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    memory_type TEXT NOT NULL,
    content TEXT NOT NULL,
    key_entities TEXT,
    importance_score REAL DEFAULT 5.0,
    base_importance_score REAL DEFAULT 5.0,
    final_importance_score REAL DEFAULT 5.0,
    score_source TEXT DEFAULT 'rule',
    embedding TEXT,
    source_conversation_id INTEGER,
    related_entry_id INTEGER,
    llm_processed INTEGER DEFAULT 0,
    llm_processed_at DATETIME,
    llm_importance_score REAL,
    user_rated INTEGER DEFAULT 0,
    user_score_adjustment INTEGER DEFAULT 0,
    user_rated_at DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_accessed_at DATETIME,
    access_count INTEGER DEFAULT 0,
    is_active INTEGER DEFAULT 1,
    marked_for_deletion INTEGER DEFAULT 0,
    marked_for_deletion_at DATETIME,
    deletion_reason TEXT,
    archived INTEGER DEFAULT 0,
    archived_at DATETIME,
    FOREIGN KEY (related_entry_id) REFERENCES entries(id),
    FOREIGN KEY (source_conversation_id) REFERENCES conversations(id)
)
"""

# Schema version table for migrations
SCHEMA_VERSION_TABLE = """
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at DATETIME NOT NULL,
    description TEXT
)
"""

# Indexes for better performance
INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_entries_timestamp ON entries(timestamp DESC)",
    "CREATE INDEX IF NOT EXISTS idx_entries_mode ON entries(mode)",
    "CREATE INDEX IF NOT EXISTS idx_entries_mood_tags ON entries(mood_tags)",
    "CREATE INDEX IF NOT EXISTS idx_patterns_type ON patterns(pattern_type)",
    "CREATE INDEX IF NOT EXISTS idx_patterns_confidence ON patterns(confidence DESC)",
    "CREATE INDEX IF NOT EXISTS idx_preferences_key ON preferences(key)",
    "CREATE INDEX IF NOT EXISTS idx_drafts_updated ON drafts(updated_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_conversations_timestamp ON conversations(timestamp DESC)",
    "CREATE INDEX IF NOT EXISTS idx_conversations_type ON conversations(conversation_type)"
]

# All tables in order of creation
ALL_TABLES = [
    SCHEMA_VERSION_TABLE,
    ENTRIES_TABLE,
    PATTERNS_TABLE,
    PREFERENCES_TABLE,
    DRAFTS_TABLE,
    CONVERSATIONS_TABLE,
    AGENT_MEMORIES_TABLE
]


async def create_tables(db_path: str):
    """Create all tables and indexes for a user database"""
    async with aiosqlite.connect(db_path) as db:
        # Create all tables
        for table_sql in ALL_TABLES:
            await db.execute(table_sql)
        
        # Create all indexes
        for index_sql in INDEXES:
            await db.execute(index_sql)
        
        await db.commit()