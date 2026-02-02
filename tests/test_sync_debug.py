#!/usr/bin/env python3
"""Debug script to test sync functionality."""

import os
import sys
import json
from pathlib import Path
from datetime import datetime, timezone

# Resolve project root (parent of tests/)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)

from config import CLOUD_API_URL, CLOUD_API_KEY
from database import DatabaseManager
from sync import SyncService

def main():
    # Initialize database
    db_path = PROJECT_ROOT / "data" / "database.db"
    db = DatabaseManager(db_path)

    sync_service = SyncService(
        db=db,
        api_url=CLOUD_API_URL,
        api_key=CLOUD_API_KEY,
        batch_size=1,  # Small batch for testing
    )

    print("=== Testing Sync Service ===")

    # Test 1: Connection test
    print("\n1. Testing connection to API...")
    success, message = sync_service.test_connection()
    print(f"   Result: {success}")
    print(f"   Message: {message}")

    if not success:
        print("   ❌ Connection failed - cannot continue")
        return

    # Test 2: Get sync statistics
    print("\n2. Getting sync statistics...")
    try:
        stats = db.get_sync_statistics()
        print(f"   Pending: {stats['pending']}")
        print(f"   Synced: {stats['synced']}")
        print(f"   Failed: {stats['failed']}")
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return

    # Test 3: Get pending scans
    print("\n3. Getting pending scans...")
    try:
        pending_scans = db.fetch_pending_scans(limit=1)
        print(f"   Found {len(pending_scans)} pending scans")

        if not pending_scans:
            print("   ⚠️  No pending scans to test with")
            return

        # Show first scan
        scan = pending_scans[0]
        print(f"   First scan:")
        print(f"     ID: {scan.id}")
        print(f"     Badge ID: {scan.badge_id}")
        print(f"     Station: {scan.station_name}")
        print(f"     Scanned at: {scan.scanned_at}")

    except Exception as e:
        print(f"   ❌ Error: {e}")
        return

    # Test 4: Test sync (with just 1 scan)
    print("\n4. Testing sync with 1 scan...")
    try:
        result = sync_service.sync_pending_scans()
        print(f"   Result: {result}")

        if result.get('synced', 0) > 0:
            print("   ✅ Sync successful!")
        else:
            print(f"   ⚠️  Sync result: {result}")

    except Exception as e:
        print(f"   ❌ Sync error: {e}")
        return

    # Test 5: Manual API test
    print("\n5. Manual API test...")
    try:
        import requests

        # Create test event
        test_event = {
            "idempotency_key": f"manual-test-{datetime.now(timezone.utc).isoformat()}",
            "badge_id": "TEST001",
            "station_name": "Test Station",
            "scanned_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "meta": {
                "matched": True,
                "test": True
            }
        }

        response = requests.post(
            f"{CLOUD_API_URL}/v1/scans/batch",
            json={"events": [test_event]},
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {CLOUD_API_KEY}",
            },
            timeout=10,
        )

        print(f"   Status code: {response.status_code}")
        print(f"   Response: {response.text}")

    except Exception as e:
        print(f"   ❌ Manual API test error: {e}")

    print("\n=== Debug Complete ===")

if __name__ == "__main__":
    main()