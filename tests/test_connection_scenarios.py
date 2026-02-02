#!/usr/bin/env python3
"""Test different connection scenarios for sync functionality."""

import os
import sys
import time
import requests
from pathlib import Path

# Resolve project root (parent of tests/)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)

from config import CLOUD_API_KEY
from database import DatabaseManager
from sync import SyncService

def test_connection_scenarios():
    """Test various connection scenarios."""

    print("=== Connection Scenario Testing ===\n")

    # Initialize database
    db_path = PROJECT_ROOT / "data" / "database.db"
    db = DatabaseManager(db_path)

    # Test scenarios
    scenarios = [
        {
            "name": "Valid Connection (API running)",
            "api_url": "http://localhost:5000",
            "api_key": CLOUD_API_KEY,
            "expected_success": True
        },
        {
            "name": "Invalid API URL (wrong port)",
            "api_url": "http://localhost:9999",
            "api_key": CLOUD_API_KEY,
            "expected_success": False
        },
        {
            "name": "Invalid API Key",
            "api_url": "http://localhost:5000",
            "api_key": "invalid_key_12345",
            "expected_success": False
        },
        {
            "name": "Non-existent API URL",
            "api_url": "http://nonexistent.api.example.com",
            "api_key": CLOUD_API_KEY,
            "expected_success": False
        }
    ]

    for i, scenario in enumerate(scenarios, 1):
        print(f"{i}. Testing: {scenario['name']}")
        print(f"   API URL: {scenario['api_url']}")
        print(f"   API Key: {scenario['api_key'][:20]}...")

        # Initialize sync service for this scenario
        sync_service = SyncService(
            db=db,
            api_url=scenario['api_url'],
            api_key=scenario['api_key'],
            batch_size=1
        )

        # Test connection
        success, message = sync_service.test_connection()
        print(f"   Result: {'PASS' if success == scenario['expected_success'] else 'FAIL'}")
        print(f"   Success: {success}")
        print(f"   Message: {message}")

        # If connection successful, try a small sync test
        if success and scenario['expected_success']:
            print("   Testing sync (1 scan)...")
            result = sync_service.sync_pending_scans()
            synced = result.get('synced', 0)
            failed = result.get('failed', 0)
            print(f"   Sync result: synced={synced}, failed={failed}")

        print()

    # Test timeout scenarios
    print("5. Testing timeout scenarios...")

    # Test with very short timeout
    sync_service_fast = SyncService(
        db=db,
        api_url="http://localhost:5000",
        api_key=CLOUD_API_KEY,
        batch_size=1
    )

    # Manually test connection with very short timeout
    try:
        response = requests.get(
            "http://localhost:5000/healthz",
            timeout=0.001  # Very short timeout
        )
        print("   Fast timeout test: Unexpectedly succeeded")
    except requests.exceptions.Timeout:
        print("   Fast timeout test: Correctly timed out")
    except Exception as e:
        print(f"   Fast timeout test: Other error - {e}")

    # Test network resilience
    print("\n6. Testing network resilience...")

    # Make multiple rapid connection tests
    sync_service = SyncService(
        db=db,
        api_url="http://localhost:5000",
        api_key=CLOUD_API_KEY,
        batch_size=1
    )

    success_count = 0
    total_tests = 5

    for i in range(total_tests):
        success, message = sync_service.test_connection()
        if success:
            success_count += 1
        time.sleep(0.1)  # Small delay between tests

    print(f"   Rapid connection tests: {success_count}/{total_tests} successful")
    print(f"   Network reliability: {(success_count/total_tests)*100:.1f}%")

    print("\n=== Connection Testing Complete ===")

if __name__ == "__main__":
    test_connection_scenarios()