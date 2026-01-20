#!/usr/bin/env python3
"""
Migration: Add smart_tags column to entries table

This migration adds the smart_tags column to store auto-generated semantic tags
separately from processing_metadata.
"""

import sqlite3
import sys
import os
from pathlib import Path

def run_migration(db_path: str = "boo.db"):
    """Add smart_tags column to entries table if it doesn't exist."""
    
    # Ensure we're in the backend directory
    backend_dir = Path(__file__).parent.parent
    if not (backend_dir / db_path).exists():
        print(f"❌ Database {db_path} not found in {backend_dir}")
        return False
    
    full_db_path = backend_dir / db_path
    print(f"🔄 Running migration on: {full_db_path}")
    
    try:
        conn = sqlite3.connect(str(full_db_path))
        cursor = conn.cursor()
        
        # Check if smart_tags column already exists
        cursor.execute("PRAGMA table_info(entries)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'smart_tags' in columns:
            print("✅ smart_tags column already exists, skipping migration")
            conn.close()
            return True
        
        # Add smart_tags column
        print("📝 Adding smart_tags column...")
        cursor.execute("ALTER TABLE entries ADD COLUMN smart_tags TEXT")
        
        # Add index for smart_tags
        print("📝 Adding index for smart_tags...")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_entries_smart_tags ON entries(smart_tags)")
        
        # Commit changes
        conn.commit()
        conn.close()
        
        print("✅ Migration completed successfully!")
        print("   - Added smart_tags column to entries table")
        print("   - Added index for smart_tags column")
        
        return True
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        return False

if __name__ == "__main__":
    # Allow custom database path as argument
    db_path = sys.argv[1] if len(sys.argv) > 1 else "boo.db"
    success = run_migration(db_path)
    sys.exit(0 if success else 1)