#!/usr/bin/env python3
"""
Migration: Add memory system tables and columns

This migration adds:
1. agent_memories table for storing personal facts, preferences, habits
2. embedding column to conversations table for semantic search
3. summary and key_topics columns to conversations table
"""

import sqlite3
import sys
import os
from pathlib import Path

def run_migration(db_path: str = "boo.db"):
    """Add memory system tables and columns."""
    
    # Ensure we're in the backend directory
    backend_dir = Path(__file__).parent.parent
    if not (backend_dir / db_path).exists():
        print(f"Database {db_path} not found in {backend_dir}")
        return False
    
    full_db_path = backend_dir / db_path
    print(f"Running memory system migration on: {full_db_path}")
    
    try:
        conn = sqlite3.connect(str(full_db_path))
        cursor = conn.cursor()
        
        # Create agent_memories table
        print("Creating agent_memories table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS agent_memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                memory_type TEXT NOT NULL,
                content TEXT NOT NULL,
                key_entities TEXT,
                importance_score REAL DEFAULT 1.0,
                embedding TEXT,
                source_conversation_id INTEGER,
                related_entry_id INTEGER,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                last_accessed_at DATETIME,
                access_count INTEGER DEFAULT 0,
                is_active BOOLEAN DEFAULT 1,
                FOREIGN KEY (related_entry_id) REFERENCES entries(id),
                FOREIGN KEY (source_conversation_id) REFERENCES conversations(id)
            )
        """)
        
        # Create indexes for agent_memories
        print("Creating indexes for agent_memories...")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_memory_type ON agent_memories(memory_type)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_memory_importance ON agent_memories(importance_score DESC)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_memory_active ON agent_memories(is_active)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_memory_entities ON agent_memories(key_entities)")
        
        # Check if conversations table exists and add new columns
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='conversations'")
        if cursor.fetchone():
            print("Adding columns to conversations table...")
            
            # Check which columns already exist
            cursor.execute("PRAGMA table_info(conversations)")
            existing_columns = [column[1] for column in cursor.fetchall()]
            
            # Add embedding column if it doesn't exist
            if 'embedding' not in existing_columns:
                cursor.execute("ALTER TABLE conversations ADD COLUMN embedding TEXT")
                print("   - Added embedding column")
            
            # Add summary column if it doesn't exist
            if 'summary' not in existing_columns:
                cursor.execute("ALTER TABLE conversations ADD COLUMN summary TEXT")
                print("   - Added summary column")
            
            # Add key_topics column if it doesn't exist
            if 'key_topics' not in existing_columns:
                cursor.execute("ALTER TABLE conversations ADD COLUMN key_topics TEXT")
                print("   - Added key_topics column")
            
            # Create index for conversation topics
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_conversation_topics ON conversations(key_topics)")
            print("   - Added index for key_topics")
        else:
            print("WARNING: Conversations table doesn't exist yet - will add columns when it's created")
        
        # Commit changes
        conn.commit()
        conn.close()
        
        print("Memory system migration completed successfully!")
        print("   - Created agent_memories table with indexes")
        print("   - Added embedding, summary, and key_topics columns to conversations table")
        
        return True
        
    except Exception as e:
        print(f"Migration failed: {e}")
        return False

if __name__ == "__main__":
    # Allow custom database path as argument
    db_path = sys.argv[1] if len(sys.argv) > 1 else "boo.db"
    success = run_migration(db_path)
    sys.exit(0 if success else 1)