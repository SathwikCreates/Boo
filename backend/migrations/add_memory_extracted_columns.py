"""
Add memory_extracted columns to track LLM memory extraction status
"""

import sqlite3
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

def run_migration():
    """Add memory_extracted columns to entries and conversations tables"""
    
    # Get database path
    db_path = Path(__file__).parent.parent / "boo.db"
    
    if not db_path.exists():
        logger.error(f"Database not found at {db_path}")
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check and add memory_extracted column to entries table
        cursor.execute("PRAGMA table_info(entries)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'memory_extracted' not in columns:
            print("Adding memory_extracted column to entries table...")
            cursor.execute("""
                ALTER TABLE entries 
                ADD COLUMN memory_extracted INTEGER DEFAULT 0
            """)
            print("[OK] Added memory_extracted to entries table")
        else:
            print("[OK] memory_extracted column already exists in entries table")
        
        # Check and add memory_extracted column to conversations table
        cursor.execute("PRAGMA table_info(conversations)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'memory_extracted' not in columns:
            print("Adding memory_extracted column to conversations table...")
            cursor.execute("""
                ALTER TABLE conversations 
                ADD COLUMN memory_extracted INTEGER DEFAULT 0
            """)
            print("[OK] Added memory_extracted to conversations table")
        else:
            print("[OK] memory_extracted column already exists in conversations table")
        
        # Add columns to track LLM extraction separately
        cursor.execute("PRAGMA table_info(entries)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'memory_extracted_llm' not in columns:
            print("Adding memory_extracted_llm column to entries table...")
            cursor.execute("""
                ALTER TABLE entries 
                ADD COLUMN memory_extracted_llm INTEGER DEFAULT 0
            """)
            print("[OK] Added memory_extracted_llm to entries table")
        
        cursor.execute("PRAGMA table_info(conversations)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'memory_extracted_llm' not in columns:
            print("Adding memory_extracted_llm column to conversations table...")
            cursor.execute("""
                ALTER TABLE conversations 
                ADD COLUMN memory_extracted_llm INTEGER DEFAULT 0
            """)
            print("[OK] Added memory_extracted_llm to conversations table")
        
        # Add timestamp columns for tracking when extraction happened
        cursor.execute("PRAGMA table_info(entries)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'memory_extracted_at' not in columns:
            print("Adding memory_extracted_at column to entries table...")
            cursor.execute("""
                ALTER TABLE entries 
                ADD COLUMN memory_extracted_at DATETIME
            """)
            print("[OK] Added memory_extracted_at to entries table")
        
        cursor.execute("PRAGMA table_info(conversations)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'memory_extracted_at' not in columns:
            print("Adding memory_extracted_at column to conversations table...")
            cursor.execute("""
                ALTER TABLE conversations 
                ADD COLUMN memory_extracted_at DATETIME
            """)
            print("[OK] Added memory_extracted_at to conversations table")
        
        # Create indexes for efficient querying
        print("Creating indexes for memory extraction columns...")
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_entries_memory_extracted 
            ON entries(memory_extracted)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_conversations_memory_extracted 
            ON conversations(memory_extracted)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_entries_memory_extracted_llm 
            ON entries(memory_extracted_llm)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_conversations_memory_extracted_llm 
            ON conversations(memory_extracted_llm)
        """)
        print("[OK] Created indexes for memory extraction columns")
        
        # Commit changes
        conn.commit()
        print("\n[SUCCESS] Migration completed successfully!")
        
        # Show current statistics
        cursor.execute("SELECT COUNT(*) FROM entries WHERE memory_extracted = 0")
        unprocessed_entries = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM conversations WHERE memory_extracted = 0")
        unprocessed_conversations = cursor.fetchone()[0]
        
        print(f"\nCurrent status:")
        print(f"- Unprocessed entries: {unprocessed_entries}")
        print(f"- Unprocessed conversations: {unprocessed_conversations}")
        
        conn.close()
        return True
        
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        print(f"[ERROR] Migration failed: {e}")
        return False

if __name__ == "__main__":
    run_migration()