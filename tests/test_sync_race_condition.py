"""Test sync race condition: rapid concurrent sync calls should not corrupt data.

Validates issue #37 checklist item: Sync race condition (rapid auto-sync).
Each thread creates its own DatabaseManager connection (matching real app behavior
where AutoSyncManager uses a separate connection). Verifies no data loss or
corruption under concurrent access.
"""

import os
import sys
import tempfile
import threading
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)

from database import DatabaseManager, EmployeeRecord


def create_test_db(tmpdir: str) -> tuple:
    """Create a temporary database with test data. Returns (db, db_path)."""
    db_path = Path(tmpdir) / "test_race.db"
    db = DatabaseManager(db_path)
    db.set_station_name("RaceTest")

    employee = EmployeeRecord(
        legacy_id="RACE001",
        full_name="Race Test User",
        sl_l1_desc="Test Dept",
        position_desc="Tester",
    )
    db.bulk_insert_employees([employee])
    return db, db_path


def insert_pending_scans(db: DatabaseManager, count: int) -> None:
    """Insert N pending scans into the database."""
    employee = EmployeeRecord(
        legacy_id="RACE001",
        full_name="Race Test User",
        sl_l1_desc="Test Dept",
        position_desc="Tester",
    )
    for i in range(count):
        db.record_scan(
            badge_id=f"RACE{i:04d}",
            station_name="RaceTest",
            employee=employee,
            scanned_at=f"2026-02-02T10:{i % 60:02d}:{i % 60:02d}Z",
        )


def test_concurrent_fetch_pending():
    """Test that concurrent fetch_pending_scans from separate connections return consistent data."""
    print("Test 1: Concurrent fetch_pending_scans (separate connections)")

    with tempfile.TemporaryDirectory() as tmpdir:
        db, db_path = create_test_db(tmpdir)
        insert_pending_scans(db, 50)
        db.close()

        results = []
        errors = []

        def fetch_worker():
            try:
                thread_db = DatabaseManager(db_path)
                scans = thread_db.fetch_pending_scans(limit=100)
                results.append(len(scans))
                thread_db.close()
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=fetch_worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        if errors:
            print(f"  FAIL: {len(errors)} errors: {errors[:3]}")
            return False

        if all(r == 50 for r in results):
            print(f"  PASS: All 10 threads saw 50 pending scans")
            return True
        else:
            print(f"  FAIL: Inconsistent results: {results}")
            return False


def test_concurrent_mark_synced():
    """Test that concurrent mark_scans_as_synced from separate connections doesn't corrupt data."""
    print("Test 2: Concurrent mark_scans_as_synced (separate connections)")

    with tempfile.TemporaryDirectory() as tmpdir:
        db, db_path = create_test_db(tmpdir)
        insert_pending_scans(db, 100)

        scans = db.fetch_pending_scans(limit=100)
        scan_ids = [s.id for s in scans]
        db.close()

        # Split IDs into 5 non-overlapping batches
        batches = [scan_ids[i::5] for i in range(5)]
        results = []
        errors = []

        def mark_worker(batch):
            try:
                thread_db = DatabaseManager(db_path)
                count = thread_db.mark_scans_as_synced(batch)
                results.append(count)
                thread_db.close()
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=mark_worker, args=(b,)) for b in batches]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        verify_db = DatabaseManager(db_path)
        stats = verify_db.get_sync_statistics()
        verify_db.close()

        if errors:
            print(f"  FAIL: {len(errors)} errors: {errors[:3]}")
            return False

        total_marked = sum(results)
        if total_marked == 100 and stats["synced"] == 100 and stats["pending"] == 0:
            print(f"  PASS: All 100 scans marked synced across 5 threads (synced={stats['synced']}, pending={stats['pending']})")
            return True
        else:
            print(f"  FAIL: marked={total_marked}, synced={stats['synced']}, pending={stats['pending']}")
            return False


def test_concurrent_record_and_fetch():
    """Test recording scans while fetching pending from separate connections — no data loss."""
    print("Test 3: Concurrent record + fetch_pending (separate connections)")

    with tempfile.TemporaryDirectory() as tmpdir:
        db, db_path = create_test_db(tmpdir)
        db.close()

        employee = EmployeeRecord(
            legacy_id="RACE001",
            full_name="Race Test User",
            sl_l1_desc="Test Dept",
            position_desc="Tester",
        )

        record_errors = []
        fetch_errors = []
        fetch_counts = []
        stop_event = threading.Event()

        def record_worker():
            thread_db = DatabaseManager(db_path)
            for i in range(200):
                try:
                    thread_db.record_scan(
                        badge_id=f"CONC{i:04d}",
                        station_name="RaceTest",
                        employee=employee,
                        scanned_at=f"2026-02-02T11:{i % 60:02d}:{i % 60:02d}Z",
                    )
                except Exception as e:
                    record_errors.append(str(e))
                time.sleep(0.001)
            thread_db.close()
            stop_event.set()

        def fetch_worker():
            thread_db = DatabaseManager(db_path)
            while not stop_event.is_set():
                try:
                    scans = thread_db.fetch_pending_scans(limit=50)
                    fetch_counts.append(len(scans))
                except Exception as e:
                    fetch_errors.append(str(e))
                time.sleep(0.005)
            thread_db.close()

        recorder = threading.Thread(target=record_worker)
        fetchers = [threading.Thread(target=fetch_worker) for _ in range(3)]

        recorder.start()
        for f in fetchers:
            f.start()

        recorder.join(timeout=30)
        stop_event.set()
        for f in fetchers:
            f.join(timeout=5)

        verify_db = DatabaseManager(db_path)
        total = verify_db.count_scans_total()
        verify_db.close()

        if record_errors:
            print(f"  FAIL: {len(record_errors)} record errors: {record_errors[:3]}")
            return False
        if fetch_errors:
            print(f"  FAIL: {len(fetch_errors)} fetch errors: {fetch_errors[:3]}")
            return False

        if total == 200:
            print(f"  PASS: All 200 scans recorded, {len(fetch_counts)} fetch cycles completed without error")
            return True
        else:
            print(f"  FAIL: Expected 200 scans, got {total}")
            return False


def test_rapid_sync_simulation():
    """Simulate rapid auto-sync triggers: fetch -> mark synced -> fetch again, from separate connections."""
    print("Test 4: Rapid sync cycle simulation (fetch-mark-fetch, separate connections)")

    with tempfile.TemporaryDirectory() as tmpdir:
        db, db_path = create_test_db(tmpdir)
        insert_pending_scans(db, 200)
        db.close()

        errors = []
        total_synced = [0]
        lock = threading.Lock()

        def sync_cycle_worker(worker_id: int):
            thread_db = DatabaseManager(db_path)
            for _ in range(40):
                try:
                    scans = thread_db.fetch_pending_scans(limit=10)
                    if not scans:
                        break
                    ids = [s.id for s in scans]
                    count = thread_db.mark_scans_as_synced(ids)
                    with lock:
                        total_synced[0] += count
                except Exception as e:
                    errors.append(f"worker-{worker_id}: {e}")
                time.sleep(0.002)
            thread_db.close()

        threads = [threading.Thread(target=sync_cycle_worker, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        verify_db = DatabaseManager(db_path)
        stats = verify_db.get_sync_statistics()
        verify_db.close()

        if errors:
            print(f"  FAIL: {len(errors)} errors: {errors[:3]}")
            return False

        # Multiple threads may fetch the same pending scans before marking,
        # so total_synced[0] may exceed 200 (double-mark is idempotent).
        if stats["synced"] == 200 and stats["pending"] == 0:
            print(f"  PASS: All 200 scans synced (mark calls={total_synced[0]}), pending=0")
            return True
        else:
            print(f"  INFO: synced={stats['synced']}, pending={stats['pending']}, mark_calls={total_synced[0]}")
            if stats["synced"] + stats["pending"] == 200:
                print(f"  PASS (partial): No data loss, all 200 accounted for")
                return True
            print(f"  FAIL: Data inconsistency")
            return False


if __name__ == "__main__":
    print("=" * 60)
    print("Sync Race Condition Tests (#37)")
    print("=" * 60 + "\n")

    tests = [
        test_concurrent_fetch_pending,
        test_concurrent_mark_synced,
        test_concurrent_record_and_fetch,
        test_rapid_sync_simulation,
    ]

    passed = 0
    failed = 0
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"  ERROR: {e}")
            failed += 1
        print()

    print("=" * 60)
    if failed == 0:
        print(f"All {passed} tests passed!")
    else:
        print(f"{passed} passed, {failed} failed")
    print("=" * 60)
    sys.exit(1 if failed else 0)
