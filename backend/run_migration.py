#!/usr/bin/env python3
"""
Migration Runner - Add smart_tags column

Run this script to add the smart_tags column to the entries table.
"""

import sys
from pathlib import Path

# Add the backend directory to Python path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

from migrations.add_smart_tags_column import run_migration

if __name__ == "__main__":
    print("=== Boo Database Migration ===")
    print("Adding smart_tags column to entries table...")
    print()
    
    success = run_migration()
    if success:
        print()
        print("🎉 Migration completed successfully!")
        print()
        print("Next steps:")
        print("1. Restart the backend server")
        print("2. Run the auto-tagging script to populate smart_tags for existing entries")
        print("   cd backend && python scripts/auto_tag_existing_entries.py")
    else:
        print()
        print("❌ Migration failed. Please check the error messages above.")
        sys.exit(1)