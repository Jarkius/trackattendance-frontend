#!/usr/bin/env python3
"""Reset failed scans to pending status for testing."""

import sqlite3
import os
from pathlib import Path

# Resolve project root (parent of scripts/)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
os.chdir(PROJECT_ROOT)

def reset_failed_scans():
    """Reset all failed scans back to pending status."""
    db_path = PROJECT_ROOT / "data" / "database.db"

    if not db_path.exists():
        print("Database not found")
        return

    conn = sqlite3.connect(db_path)

    try:
        # Reset failed scans to pending
        with conn:
            cursor = conn.execute("""
                UPDATE scans
                SET sync_status = 'pending', synced_at = NULL, sync_error = NULL
                WHERE sync_status = 'failed'
            """)
            updated_count = cursor.rowcount

        print(f"Reset {updated_count} failed scans to pending")

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

        print(f"\nCurrent statistics:")
        print(f"   Total scans: {stats[0]}")
        print(f"   Pending sync: {stats[1]}")
        print(f"   Synced: {stats[2]}")
        print(f"   Failed: {stats[3]}")

        # Show a sample scan
        cursor = conn.execute("""
            SELECT id, badge_id, station_name, scanned_at
            FROM scans
            WHERE sync_status = 'pending'
            LIMIT 1
        """)
        sample = cursor.fetchone()

        if sample:
            print(f"\nSample pending scan:")
            print(f"   ID: {sample[0]}")
            print(f"   Badge: {sample[1]}")
            print(f"   Station: {sample[2]}")
            print(f"   Time: {sample[3]}")

    except Exception as e:
        print(f"Error: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    reset_failed_scans()