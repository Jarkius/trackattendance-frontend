#!/usr/bin/env python3
"""Database migration script to add sync tracking columns to existing scans table."""

import sqlite3
from pathlib import Path

def migrate_database():
    """Add sync tracking columns to scans table if they don't exist."""
    db_path = Path("data/database.db")

    if not db_path.exists():
        print("Database not found at data/database.db")
        return

    conn = sqlite3.connect(db_path)

    try:
        # Check if sync_status column exists
        cursor = conn.execute("PRAGMA table_info(scans)")
        columns = [row[1] for row in cursor.fetchall()]

        if 'sync_status' not in columns:
            print("Adding sync tracking columns...")
            with conn:
                # Add sync tracking columns
                conn.execute("""
                    ALTER TABLE scans ADD COLUMN sync_status TEXT NOT NULL DEFAULT 'pending'
                """)
                conn.execute("""
                    ALTER TABLE scans ADD COLUMN synced_at TEXT
                """)
                conn.execute("""
                    ALTER TABLE scans ADD COLUMN sync_error TEXT
                """)
                # Create index for sync status
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_scans_sync_status ON scans(sync_status)
                """)

            print("[SUCCESS] Migration completed successfully")
            print("All existing scans marked as 'pending' for sync")
        else:
            print("[INFO] Sync columns already exist")

        # Show current statistics
        cursor = conn.execute("""
            SELECT
                COUNT(*) as total,
                COUNT(CASE WHEN sync_status = 'pending' THEN 1 END) as pending,
                COUNT(CASE WHEN sync_status = 'synced' THEN 1 END) as synced,
                COUNT(CASE WHEN sync_status = 'failed' THEN 1 END) as failed
            FROM scans
        """)
        stats = cursor.fetchone()

        print(f"\n[STATS] Current scan statistics:")
        print(f"   Total scans: {stats[0]}")
        print(f"   Pending sync: {stats[1]}")
        print(f"   Synced: {stats[2]}")
        print(f"   Failed: {stats[3]}")

    except Exception as e:
        print(f"[ERROR] Migration failed: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    migrate_database()