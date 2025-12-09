#!/usr/bin/env python3
"""Debug sync performance to identify bottlenecks."""

import time
from database import DatabaseManager
from sync import SyncService

def debug_sync_performance():
    """Analyze sync performance step by step."""

    print("=== Sync Performance Analysis ===")

    # Initialize services
    start_total = time.time()
    db = DatabaseManager('data/database.db')
    init_time = time.time() - start_total
    print(f"Database initialization: {init_time:.3f}s")

    # Initialize sync service
    start_sync = time.time()
    sync_service = SyncService(
        db=db,
        api_url="https://trackattendance-api-969370105809.asia-southeast1.run.app",
        api_key="6541f2c7892b4e5287d50c2414d179f8",
        batch_size=100,
    )
    sync_init_time = time.time() - start_sync
    print(f"Sync service initialization: {sync_init_time:.3f}s")

    # Get pending scans
    start_pending = time.time()
    pending_scans = db.fetch_pending_scans()
    pending_time = time.time() - start_pending
    print(f"Getting pending scans: {pending_time:.3f}s ({len(pending_scans)} scans)")

    if not pending_scans:
        print("No pending scans to sync")
        return

    # Test database operations
    start_db_ops = time.time()
    for scan in pending_scans:
        # Simulate idempotency key generation
        station = db.get_station_name() or "UnknownStation"
        key = f"{station.replace(' ', '').replace('-', '')}-{scan.badge_id}-{scan.id}"
    db_ops_time = time.time() - start_db_ops
    print(f"Database operations (idempotency keys): {db_ops_time:.3f}s")

    # Test connection
    start_conn = time.time()
    success, message = sync_service.test_connection()
    conn_time = time.time() - start_conn
    print(f"Connection test: {conn_time:.3f}s - {message}")

    if not success:
        print("Connection failed - cannot test sync performance")
        return

    # Measure actual sync performance
    print("\n=== Measuring Sync Performance ===")
    start_actual_sync = time.time()

    result = sync_service.sync_pending_scans()

    actual_sync_time = time.time() - start_actual_sync
    total_time = time.time() - start_total

    print(f"Actual sync operation: {actual_sync_time:.3f}s")
    print(f"Total time: {total_time:.3f}s")
    print(f"Sync result: {result}")

    # Analyze bottlenecks
    print("\n=== Bottleneck Analysis ===")
    total = total_time * 1000
    print(f"Database init: {init_time/total*100:.1f}%")
    print(f"Sync service init: {sync_init_time/total*100:.1f}%")
    print(f"Get pending scans: {pending_time/total*100:.1f}%")
    print(f"Database operations: {db_ops_time/total*100:.1f}%")
    print(f"Connection test: {conn_time/total*100:.1f}%")
    print(f"Actual sync: {actual_sync_time/total*100:.1f}%")

    # Network performance test
    print("\n=== Network Performance Test ===")
    try:
        import requests
        start_ping = time.time()
        response = requests.get(
            "https://trackattendance-api-969370105809.asia-southeast1.run.app/",
            timeout=5
        )
        ping_time = time.time() - start_ping
        print(f"API ping (root endpoint): {ping_time:.3f}s")
        print(f"Response size: {len(response.content)} bytes")
    except Exception as e:
        print(f"Network test failed: {e}")

if __name__ == "__main__":
    debug_sync_performance()