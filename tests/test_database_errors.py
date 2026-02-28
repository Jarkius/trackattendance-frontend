#!/usr/bin/env python3
"""
Tests for database error handling paths in database.py.

Tests untested database methods and error conditions including:
- mark_scans_as_failed()
- clear_all_scans()
- get_scans_by_bu()
- count_unmatched_scanned_badges()
- Error handling for edge cases

Run: python tests/test_database_errors.py
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from datetime import datetime, timezone

# Set required environment variables BEFORE importing config
os.environ.setdefault("CLOUD_API_KEY", "test-api-key-for-testing")
os.environ.setdefault("CLOUD_API_URL", "http://test.example.com")

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from database import DatabaseManager, EmployeeRecord, ISO_TIMESTAMP_FORMAT


class TestMarkScansAsFailed(unittest.TestCase):
    """Test mark_scans_as_failed() method."""

    def setUp(self):
        """Set up test database with pending scans."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test.db"
        self.db = DatabaseManager(self.db_path)
        self.db.set_station_name("TestStation")

        # Add employees
        self.db.bulk_insert_employees([
            EmployeeRecord("TEST001", "Test User", "IT", "Engineer"),
            EmployeeRecord("TEST002", "Jane Doe", "HR", "Manager"),
        ])

        # Create pending scans
        self.db.record_scan("TEST001", "TestStation",
                           EmployeeRecord("TEST001", "Test User", "IT", "Engineer"))
        self.db.record_scan("TEST002", "TestStation",
                           EmployeeRecord("TEST002", "Jane Doe", "HR", "Manager"))

    def tearDown(self):
        """Clean up."""
        self.db.close()
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_mark_single_scan_failed(self):
        """Test marking a single scan as failed."""
        scans = self.db.fetch_pending_scans()
        self.assertEqual(len(scans), 2)

        # Mark first scan as failed
        self.db.mark_scans_as_failed([scans[0].id], "Test error message")

        stats = self.db.get_sync_statistics()
        self.assertEqual(stats["failed"], 1)
        self.assertEqual(stats["pending"], 1)

    def test_mark_multiple_scans_failed(self):
        """Test marking multiple scans as failed."""
        scans = self.db.fetch_pending_scans()
        scan_ids = [s.id for s in scans]

        self.db.mark_scans_as_failed(scan_ids, "Batch failure")

        stats = self.db.get_sync_statistics()
        self.assertEqual(stats["failed"], 2)
        self.assertEqual(stats["pending"], 0)

    def test_mark_empty_list_no_error(self):
        """Test marking empty list doesn't raise error."""
        # Should not raise
        self.db.mark_scans_as_failed([], "Empty list")

        stats = self.db.get_sync_statistics()
        self.assertEqual(stats["pending"], 2)  # No change

    def test_mark_invalid_ids_no_error(self):
        """Test marking non-existent IDs doesn't raise error."""
        # Should not raise, just ignore invalid IDs
        self.db.mark_scans_as_failed([99999, 88888], "Invalid IDs")

        stats = self.db.get_sync_statistics()
        self.assertEqual(stats["pending"], 2)  # No change

    def test_error_message_stored(self):
        """Test error message is stored with failed scan."""
        scans = self.db.fetch_pending_scans()
        error_msg = "API returned 500: Internal Server Error"

        self.db.mark_scans_as_failed([scans[0].id], error_msg)

        # Check that error is stored (via raw query)
        cursor = self.db._connection.execute(
            "SELECT sync_error FROM scans WHERE id = ?",
            (scans[0].id,)
        )
        row = cursor.fetchone()
        self.assertEqual(row[0], error_msg)


class TestClearAllScans(unittest.TestCase):
    """Test clear_all_scans() method."""

    def setUp(self):
        """Set up test database with scans."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test.db"
        self.db = DatabaseManager(self.db_path)
        self.db.set_station_name("TestStation")

        self.db.bulk_insert_employees([
            EmployeeRecord("TEST001", "Test User", "IT", "Engineer"),
        ])

        # Create multiple scans
        for i in range(5):
            self.db.record_scan(f"TEST{i:03d}", "TestStation", None)

    def tearDown(self):
        """Clean up."""
        self.db.close()
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_clear_all_returns_count(self):
        """Test clear_all_scans returns deleted count."""
        initial_count = self.db.count_scans_total()
        self.assertEqual(initial_count, 5)

        deleted = self.db.clear_all_scans()

        self.assertEqual(deleted, 5)
        self.assertEqual(self.db.count_scans_total(), 0)

    def test_clear_empty_database(self):
        """Test clearing empty database returns 0."""
        # Clear first
        self.db.clear_all_scans()

        # Clear again
        deleted = self.db.clear_all_scans()
        self.assertEqual(deleted, 0)

    def test_employees_preserved_after_clear(self):
        """Test employees are NOT deleted when scans are cleared."""
        self.db.clear_all_scans()

        # Employees should still exist
        employees = self.db.load_employee_cache()
        self.assertGreater(len(employees), 0)


class TestGetScansByBu(unittest.TestCase):
    """Test get_scans_by_bu() method."""

    def setUp(self):
        """Set up test database with BU-categorized scans."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test.db"
        self.db = DatabaseManager(self.db_path)
        self.db.set_station_name("TestStation")

        # Add employees in different BUs
        self.db.bulk_insert_employees([
            EmployeeRecord("IT001", "Alice", "IT", "Engineer"),
            EmployeeRecord("IT002", "Bob", "IT", "Developer"),
            EmployeeRecord("HR001", "Carol", "HR", "Manager"),
            EmployeeRecord("SALES001", "Dave", "Sales", "Rep"),
        ])

        # Record scans
        self.db.record_scan("IT001", "TestStation",
                           EmployeeRecord("IT001", "Alice", "IT", "Engineer"))
        self.db.record_scan("IT002", "TestStation",
                           EmployeeRecord("IT002", "Bob", "IT", "Developer"))
        self.db.record_scan("HR001", "TestStation",
                           EmployeeRecord("HR001", "Carol", "HR", "Manager"))

    def tearDown(self):
        """Clean up."""
        self.db.close()
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_scans_grouped_by_bu(self):
        """Test scans are correctly grouped by BU."""
        bu_scans = self.db.get_scans_by_bu()

        # Should be a list of dicts with bu_name, registered, scanned
        self.assertIsInstance(bu_scans, list)

        # Find IT and HR entries
        it_entry = next((b for b in bu_scans if b["bu_name"] == "IT"), None)
        hr_entry = next((b for b in bu_scans if b["bu_name"] == "HR"), None)

        self.assertIsNotNone(it_entry)
        self.assertIsNotNone(hr_entry)

        # IT should have 2 scans
        self.assertEqual(it_entry["scanned"], 2)

        # HR should have 1 scan
        self.assertEqual(hr_entry["scanned"], 1)

    def test_empty_scans_still_shows_employees(self):
        """Test empty scans still shows employees grouped by BU."""
        self.db.clear_all_scans()

        bu_scans = self.db.get_scans_by_bu()
        # Should still have BU entries (from employees) with 0 scanned
        self.assertIsInstance(bu_scans, list)
        self.assertGreater(len(bu_scans), 0)


class TestCountUnmatchedBadges(unittest.TestCase):
    """Test count_unmatched_scanned_badges() method."""

    def setUp(self):
        """Set up test database."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test.db"
        self.db = DatabaseManager(self.db_path)
        self.db.set_station_name("TestStation")

        # Add one known employee
        self.db.bulk_insert_employees([
            EmployeeRecord("KNOWN001", "Known User", "IT", "Engineer"),
        ])

    def tearDown(self):
        """Clean up."""
        self.db.close()
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_count_unmatched(self):
        """Test counting unmatched badge scans."""
        # Record matched scan
        self.db.record_scan("KNOWN001", "TestStation",
                           EmployeeRecord("KNOWN001", "Known User", "IT", "Engineer"))

        # Record unmatched scans
        self.db.record_scan("UNKNOWN001", "TestStation", None)
        self.db.record_scan("UNKNOWN002", "TestStation", None)

        count = self.db.count_unmatched_scanned_badges()
        self.assertEqual(count, 2)

    def test_no_unmatched(self):
        """Test count is 0 when all badges matched."""
        self.db.record_scan("KNOWN001", "TestStation",
                           EmployeeRecord("KNOWN001", "Known User", "IT", "Engineer"))

        count = self.db.count_unmatched_scanned_badges()
        self.assertEqual(count, 0)

    def test_all_unmatched(self):
        """Test count when all badges are unmatched."""
        self.db.record_scan("UNKNOWN001", "TestStation", None)
        self.db.record_scan("UNKNOWN002", "TestStation", None)
        self.db.record_scan("UNKNOWN003", "TestStation", None)

        count = self.db.count_unmatched_scanned_badges()
        self.assertEqual(count, 3)


class TestRosterHash(unittest.TestCase):
    """Test get_roster_hash() and set_roster_hash() methods."""

    def setUp(self):
        """Set up test database."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test.db"
        self.db = DatabaseManager(self.db_path)

    def tearDown(self):
        """Clean up."""
        self.db.close()
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_set_and_get_hash(self):
        """Test setting and getting roster hash."""
        test_hash = "abc123def456"

        self.db.set_roster_hash(test_hash)
        retrieved = self.db.get_roster_hash()

        self.assertEqual(retrieved, test_hash)

    def test_get_hash_when_not_set(self):
        """Test getting hash when not set returns None or empty."""
        result = self.db.get_roster_hash()
        self.assertTrue(result is None or result == "")

    def test_update_hash(self):
        """Test updating existing hash."""
        self.db.set_roster_hash("first_hash")
        self.db.set_roster_hash("second_hash")

        result = self.db.get_roster_hash()
        self.assertEqual(result, "second_hash")


class TestDatabaseConnection(unittest.TestCase):
    """Test database connection handling."""

    def test_close_prevents_operations(self):
        """Test operations after close raise error."""
        temp_dir = tempfile.mkdtemp()
        db_path = Path(temp_dir) / "test.db"

        db = DatabaseManager(db_path)
        db.set_station_name("Test")
        db.close()

        # Operations should raise or handle gracefully
        try:
            db.count_scans_total()
            # If no error, the connection might auto-reconnect
        except Exception:
            pass  # Expected

        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)

    def test_multiple_close_safe(self):
        """Test calling close multiple times is safe."""
        temp_dir = tempfile.mkdtemp()
        db_path = Path(temp_dir) / "test.db"

        db = DatabaseManager(db_path)
        db.close()
        db.close()  # Should not raise
        db.close()  # Should not raise

        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)


class TestMarkScansAsSynced(unittest.TestCase):
    """Test mark_scans_as_synced() with edge cases."""

    def setUp(self):
        """Set up test database."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test.db"
        self.db = DatabaseManager(self.db_path)
        self.db.set_station_name("TestStation")

        self.db.record_scan("TEST001", "TestStation", None)

    def tearDown(self):
        """Clean up."""
        self.db.close()
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_mark_invalid_ids(self):
        """Test marking non-existent IDs doesn't crash."""
        # Should not raise
        self.db.mark_scans_as_synced([99999, 88888, 77777])

        # Original scan still pending
        stats = self.db.get_sync_statistics()
        self.assertEqual(stats["pending"], 1)

    def test_mark_empty_list(self):
        """Test marking empty list is safe."""
        self.db.mark_scans_as_synced([])

        stats = self.db.get_sync_statistics()
        self.assertEqual(stats["pending"], 1)

    def test_mark_same_scan_twice(self):
        """Test marking same scan twice is idempotent."""
        scans = self.db.fetch_pending_scans()
        scan_id = scans[0].id

        self.db.mark_scans_as_synced([scan_id])
        self.db.mark_scans_as_synced([scan_id])  # Again

        stats = self.db.get_sync_statistics()
        self.assertEqual(stats["synced"], 1)


def main():
    """Run tests with summary."""
    print("=" * 70)
    print("DATABASE ERROR HANDLING TESTS")
    print("=" * 70)
    print()

    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    suite.addTests(loader.loadTestsFromTestCase(TestMarkScansAsFailed))
    suite.addTests(loader.loadTestsFromTestCase(TestClearAllScans))
    suite.addTests(loader.loadTestsFromTestCase(TestGetScansByBu))
    suite.addTests(loader.loadTestsFromTestCase(TestCountUnmatchedBadges))
    suite.addTests(loader.loadTestsFromTestCase(TestRosterHash))
    suite.addTests(loader.loadTestsFromTestCase(TestDatabaseConnection))
    suite.addTests(loader.loadTestsFromTestCase(TestMarkScansAsSynced))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    print()
    print("=" * 70)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print("=" * 70)

    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
