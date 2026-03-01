#!/usr/bin/env python3
"""Check timestamp format in database scans."""

import sqlite3
import os
from pathlib import Path

# Resolve project root (parent of scripts/)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
os.chdir(PROJECT_ROOT)

def check_timestamp_format():
    """Check timestamp format in scans table."""
    db_path = PROJECT_ROOT / "data" / "database.db"

    if not db_path.exists():
        print("Database not found")
        return

    conn = sqlite3.connect(db_path)

    try:
        # Get sample timestamps
        cursor = conn.execute("""
            SELECT id, badge_id, scanned_at, sync_status
            FROM scans
            WHERE sync_status = 'pending'
            LIMIT 5
        """)

        print("Sample pending scan timestamps:")
        print("=" * 50)

        for row in cursor.fetchall():
            print(f"ID: {row[0]}")
            print(f"Badge: {row[1]}")
            print(f"Timestamp: '{row[2]}'")
            print(f"Has Z suffix: {row[2].endswith('Z')}")
            print(f"Sync status: {row[3]}")
            print("-" * 30)

        # Count timestamps by format
        cursor = conn.execute("""
            SELECT
                COUNT(*) as total,
                COUNT(CASE WHEN scanned_at LIKE '%Z' THEN 1 END) as with_z,
                COUNT(CASE WHEN scanned_at NOT LIKE '%Z' THEN 1 END) as without_z
            FROM scans
            WHERE sync_status = 'pending'
        """)
        stats = cursor.fetchone()

        print(f"\nTimestamp format statistics:")
        print(f"Total pending scans: {stats[0]}")
        print(f"With Z suffix: {stats[1]}")
        print(f"Without Z suffix: {stats[2]}")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    check_timestamp_format()