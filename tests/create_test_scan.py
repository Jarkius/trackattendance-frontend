#!/usr/bin/env python3
"""Create a test scan to verify sync functionality."""

import sqlite3
import os
from pathlib import Path
from datetime import datetime, timezone

# Resolve project root (parent of scripts/)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
os.chdir(PROJECT_ROOT)

def create_test_scan():
    """Create a test scan record."""
    db_path = PROJECT_ROOT / "data" / "database.db"

    if not db_path.exists():
        print("Database not found")
        return

    conn = sqlite3.connect(db_path)

    try:
        # Create a test scan record
        badge_id = f"TEST{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
        station_name = "Test Station"
        scanned_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")

        cursor = conn.execute("""
            INSERT INTO scans (
                badge_id, station_name, scanned_at, employee_full_name,
                legacy_id, sl_l1_desc, position_desc, sync_status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 'pending')
        """, (badge_id, station_name, scanned_at, "Test User", None, None, None))

        scan_id = cursor.lastrowid
        conn.commit()

        print(f"Created test scan:")
        print(f"   ID: {scan_id}")
        print(f"   Badge ID: {badge_id}")
        print(f"   Station: {station_name}")
        print(f"   Timestamp: {scanned_at}")
        print(f"   Sync Status: pending")

        return scan_id

    except Exception as e:
        print(f"Error creating test scan: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    create_test_scan()