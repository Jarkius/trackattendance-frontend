#!/usr/bin/env python3
"""Test batch sync functionality."""

import sys
import json
from pathlib import Path
from database import DatabaseManager
from sync import SyncService

def main():
    # Initialize database
    db_path = Path("data/database.db")
    db = DatabaseManager(db_path)

    # Initialize sync service (same config as main.py)
    CLOUD_API_URL = "http://localhost:5000"
    CLOUD_API_KEY = "6541f2c7892b4e5287d50c2414d179f8"

    sync_service = SyncService(
        db=db,
        api_url=CLOUD_API_URL,
        api_key=CLOUD_API_KEY,
        batch_size=10,  # Test with 10 scans at a time
    )

    print("=== Testing Batch Sync ===")

    # Test connection
    print("\n1. Testing connection...")
    success, message = sync_service.test_connection()
    print(f"   Result: {success} - {message}")

    if not success:
        print("   Connection failed - cannot continue")
        return

    # Get initial stats
    print("\n2. Initial sync statistics...")
    stats = db.get_sync_statistics()
    print(f"   Pending: {stats['pending']}")
    print(f"   Synced: {stats['synced']}")
    print(f"   Failed: {stats['failed']}")

    if stats['pending'] == 0:
        print("   No pending scans to sync")
        return

    # Test batch sync
    print(f"\n3. Testing batch sync (batch size: {sync_service.batch_size})...")

    total_synced = 0
    total_failed = 0
    batch_count = 0

    # Continue until no more pending scans or max 3 batches
    while batch_count < 3 and total_synced + total_failed < 30:
        result = sync_service.sync_pending_scans()
        batch_count += 1

        synced = result.get('synced', 0)
        failed = result.get('failed', 0)
        pending = result.get('pending', 0)

        total_synced += synced
        total_failed += failed

        print(f"   Batch {batch_count}: synced={synced}, failed={failed}, pending={pending}")

        if synced == 0 and failed == 0:
            print("   No more progress - stopping")
            break

    print(f"\n4. Batch sync summary:")
    print(f"   Total batches processed: {batch_count}")
    print(f"   Total synced: {total_synced}")
    print(f"   Total failed: {total_failed}")

    # Final stats
    print("\n5. Final sync statistics...")
    stats = db.get_sync_statistics()
    print(f"   Pending: {stats['pending']}")
    print(f"   Synced: {stats['synced']}")
    print(f"   Failed: {stats['failed']}")

    # Verify cloud database
    print("\n6. Verifying cloud database...")
    import subprocess
    try:
        result = subprocess.run(
            ["npx", "tsx", "../NodeJS/trackattendance-api/testscript/test-neon.js"],
            capture_output=True,
            text=True,
            cwd="C:/Workspace/Dev/NodeJS/trackattendance-api"
        )

        if "Records in scans table:" in result.stdout:
            for line in result.stdout.split('\n'):
                if "Records in scans table:" in line:
                    record_count = line.split(':')[1].strip()
                    print(f"   Cloud database records: {record_count}")
                    break
        else:
            print(f"   Could not get cloud record count")
            print(f"   Output: {result.stdout}")

    except Exception as e:
        print(f"   Error checking cloud database: {e}")

    print("\n=== Batch Sync Test Complete ===")

if __name__ == "__main__":
    main()