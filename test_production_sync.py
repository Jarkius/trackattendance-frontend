#!/usr/bin/env python3
"""Test production sync from QR app to Cloud Run API."""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import DatabaseManager
from sync import SyncService

def test_production_sync():
    """Test sync to production Cloud Run API."""

    # Production Cloud Run API Configuration
    api_url = "https://trackattendance-api-969370105809.asia-southeast1.run.app"
    api_key = "6541f2c7892b4e5287d50c2414d179f8"

    print("=== Testing QR App Sync to Production Cloud Run API ===")
    print(f"API URL: {api_url}")
    print(f"Database: data/database.db")
    print("=" * 60)

    # Initialize database and sync service
    try:
        db = DatabaseManager("data/database.db")
        sync_service = SyncService(db, api_url, api_key)
        print("[OK] Database and sync service initialized")
    except Exception as e:
        print(f"[ERROR] Failed to initialize: {e}")
        return

    print()

    # Test 1: Connection Test
    print("1. Testing connection to Cloud Run API...")
    try:
        connected, message = sync_service.test_connection()
        print(f"   Status: {'[OK] Connected' if connected else '[ERROR] Failed'}")
        print(f"   Message: {message}")
    except Exception as e:
        print(f"   [ERROR] Connection test error: {e}")

    print()

    # Test 2: Get Sync Statistics
    print("2. Checking sync statistics...")
    try:
        stats = db.get_sync_statistics()
        print(f"   Pending scans: {stats.get('pending', 0)}")
        print(f"   Synced scans: {stats.get('synced', 0)}")
        print(f"   Failed scans: {stats.get('failed', 0)}")
    except Exception as e:
        print(f"   [ERROR] Stats error: {e}")

    print()

    # Test 3: Sync Pending Scans
    print("3. Syncing pending scans to production...")
    try:
        result = sync_service.sync_pending_scans()
        print(f"   Scans synced: {result.get('synced', 0)}")
        print(f"   Scans failed: {result.get('failed', 0)}")
        print(f"   Remaining pending: {result.get('pending', 0)}")

        if result.get('synced', 0) > 0:
            print("   [OK] Successfully synced scans to production!")
        else:
            print("   [INFO] No pending scans to sync")

    except Exception as e:
        print(f"   [ERROR] Sync error: {e}")

    print()

    # Test 4: Verify Updated Statistics
    print("4. Verifying updated sync statistics...")
    try:
        stats = db.get_sync_statistics()
        print(f"   Pending scans: {stats.get('pending', 0)}")
        print(f"   Synced scans: {stats.get('synced', 0)}")
        print(f"   Failed scans: {stats.get('failed', 0)}")
    except Exception as e:
        print(f"   [ERROR] Stats error: {e}")

    print()
    print("=== Production Sync Test Complete ===")

if __name__ == "__main__":
    test_production_sync()