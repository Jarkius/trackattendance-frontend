#!/usr/bin/env python3
"""
Performance tests for TrackAttendance application.

Tests response times, memory usage, and scalability of core operations.

Run: python tests/test_performance.py
"""

import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from datetime import datetime

# Set required environment variables BEFORE importing config
os.environ.setdefault("CLOUD_API_KEY", "test-api-key-for-testing")
os.environ.setdefault("CLOUD_API_URL", "http://test.example.com")

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from database import DatabaseManager, EmployeeRecord


class TestDatabasePerformance(unittest.TestCase):
    """Performance tests for database operations."""

    def setUp(self):
        """Set up test database."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test.db"
        self.db = DatabaseManager(self.db_path)
        self.db.set_station_name("TestStation")

    def tearDown(self):
        """Clean up."""
        self.db.close()
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_bulk_insert_1000_employees(self):
        """Test bulk insert of 1000 employees completes in reasonable time."""
        employees = [
            EmployeeRecord(f"EMP{i:05d}", f"Employee {i}", f"BU{i % 10}", "Position")
            for i in range(1000)
        ]

        start = time.time()
        self.db.bulk_insert_employees(employees)
        elapsed = time.time() - start

        # Should complete in under 5 seconds
        self.assertLess(elapsed, 5.0, f"Bulk insert took {elapsed:.2f}s")

        # Verify data
        count = self.db.count_employees()
        self.assertEqual(count, 1000)

    def test_employee_lookup_speed(self):
        """Test employee lookup is fast after loading cache."""
        # Insert employees
        employees = [
            EmployeeRecord(f"EMP{i:05d}", f"Employee {i}", "IT", "Position")
            for i in range(500)
        ]
        self.db.bulk_insert_employees(employees)

        # Load cache
        cache = self.db.load_employee_cache()

        # Time 1000 lookups
        start = time.time()
        for _ in range(1000):
            _ = cache.get("EMP00250")
        elapsed = time.time() - start

        # 1000 lookups should be under 10ms
        self.assertLess(elapsed, 0.01, f"1000 lookups took {elapsed*1000:.2f}ms")

    def test_record_scan_speed(self):
        """Test scan recording speed."""
        self.db.bulk_insert_employees([
            EmployeeRecord("TEST001", "Test User", "IT", "Engineer")
        ])
        employee = EmployeeRecord("TEST001", "Test User", "IT", "Engineer")

        start = time.time()
        for i in range(100):
            self.db.record_scan(f"TEST{i:03d}", "TestStation", employee if i == 0 else None)
        elapsed = time.time() - start

        # 100 scans should be under 2 seconds
        self.assertLess(elapsed, 2.0, f"100 scans took {elapsed:.2f}s")

    def test_fetch_pending_scans_speed(self):
        """Test fetching pending scans is fast."""
        # Create 100 pending scans (respecting default batch limit)
        for i in range(100):
            self.db.record_scan(f"BADGE{i:03d}", "TestStation", None)

        start = time.time()
        scans = self.db.fetch_pending_scans()
        elapsed = time.time() - start

        # Should fetch scans in under 1 second
        self.assertLess(elapsed, 1.0, f"Fetch took {elapsed:.2f}s")
        # May be limited by batch size config
        self.assertGreater(len(scans), 0)

    def test_mark_synced_batch_speed(self):
        """Test batch sync marking is fast."""
        # Create 200 scans
        for i in range(200):
            self.db.record_scan(f"BADGE{i:03d}", "TestStation", None)

        scans = self.db.fetch_pending_scans()
        scan_ids = [s.id for s in scans]

        start = time.time()
        self.db.mark_scans_as_synced(scan_ids)
        elapsed = time.time() - start

        # Marking 200 scans should be under 1 second
        self.assertLess(elapsed, 1.0, f"Mark synced took {elapsed:.2f}s")


class TestMemoryUsage(unittest.TestCase):
    """Tests for memory efficiency."""

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

    def test_employee_cache_memory(self):
        """Test employee cache doesn't use excessive memory."""
        import sys

        # Insert 1000 employees
        employees = [
            EmployeeRecord(f"EMP{i:05d}", f"Employee Name {i}", f"Business Unit {i % 20}", "Position Title")
            for i in range(1000)
        ]
        self.db.bulk_insert_employees(employees)

        # Load cache and check size
        cache = self.db.load_employee_cache()

        # Estimate memory usage
        cache_size = sys.getsizeof(cache)
        # Each entry adds to the size
        estimated_per_entry = 500  # Rough estimate per entry in bytes
        expected_max = 1000 * estimated_per_entry  # 500KB

        # Cache should be under 1MB for 1000 employees
        self.assertLess(cache_size, 1024 * 1024, f"Cache size: {cache_size} bytes")

    def test_scan_batch_memory(self):
        """Test scan batches don't hold too much memory."""
        import sys

        self.db.set_station_name("TestStation")

        # Create 500 scans
        for i in range(500):
            self.db.record_scan(f"BADGE{i:03d}", "TestStation", None)

        scans = self.db.fetch_pending_scans()

        # Check memory of scan list
        scans_size = sys.getsizeof(scans)
        # Should be reasonable
        self.assertLess(scans_size, 1024 * 1024, f"Scans list size: {scans_size} bytes")


class TestConcurrency(unittest.TestCase):
    """Test concurrent operations."""

    def setUp(self):
        """Set up test database."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test.db"
        self.db = DatabaseManager(self.db_path)
        self.db.set_station_name("TestStation")

    def tearDown(self):
        """Clean up."""
        self.db.close()
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_rapid_consecutive_scans(self):
        """Test rapid consecutive scans don't cause issues."""
        # Simulate rapid badge scanning
        start = time.time()
        for i in range(50):
            self.db.record_scan(f"BADGE{i:03d}", "TestStation", None)
        elapsed = time.time() - start

        # All should complete without error
        count = self.db.count_scans_total()
        self.assertEqual(count, 50)

        # Should be fast
        self.assertLess(elapsed, 2.0)

    def test_interleaved_read_write(self):
        """Test interleaved read/write operations."""
        # Insert some data
        self.db.bulk_insert_employees([
            EmployeeRecord("TEST001", "Test User", "IT", "Engineer")
        ])

        # Interleave reads and writes
        for i in range(20):
            # Write
            self.db.record_scan(f"BADGE{i:03d}", "TestStation", None)

            # Read
            _ = self.db.fetch_pending_scans()
            _ = self.db.get_sync_statistics()

        # Should complete without error
        stats = self.db.get_sync_statistics()
        self.assertEqual(stats["pending"], 20)


class TestScalability(unittest.TestCase):
    """Test behavior at scale."""

    def setUp(self):
        """Set up test database."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test.db"
        self.db = DatabaseManager(self.db_path)
        self.db.set_station_name("TestStation")

    def tearDown(self):
        """Clean up."""
        self.db.close()
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_large_employee_roster(self):
        """Test handling large employee roster (5000 employees)."""
        employees = [
            EmployeeRecord(f"EMP{i:05d}", f"Employee Name {i}", f"BU{i % 50}", "Position")
            for i in range(5000)
        ]

        start = time.time()
        self.db.bulk_insert_employees(employees)
        elapsed = time.time() - start

        # Should complete in reasonable time
        self.assertLess(elapsed, 30.0, f"Insert 5000 employees took {elapsed:.2f}s")

        # Verify
        count = self.db.count_employees()
        self.assertEqual(count, 5000)

    def test_many_business_units(self):
        """Test handling many business units."""
        # Create employees in 100 different BUs
        employees = [
            EmployeeRecord(f"EMP{i:05d}", f"Employee {i}", f"BusinessUnit{i % 100}", "Position")
            for i in range(1000)
        ]
        self.db.bulk_insert_employees(employees)

        # Record scans across BUs
        for i in range(100):
            self.db.record_scan(
                f"EMP{i*10:05d}",
                "TestStation",
                EmployeeRecord(f"EMP{i*10:05d}", f"Employee {i*10}", f"BusinessUnit{i}", "Position")
            )

        # Get BU breakdown
        start = time.time()
        bu_data = self.db.get_scans_by_bu()
        elapsed = time.time() - start

        # Should be fast
        self.assertLess(elapsed, 1.0)
        self.assertGreater(len(bu_data), 0)


class TestDatabaseSize(unittest.TestCase):
    """Test database file size management."""

    def setUp(self):
        """Set up test database."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test.db"
        self.db = DatabaseManager(self.db_path)
        self.db.set_station_name("TestStation")

    def tearDown(self):
        """Clean up."""
        self.db.close()
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_database_file_size_reasonable(self):
        """Test database file size stays reasonable."""
        # Insert 1000 employees
        employees = [
            EmployeeRecord(f"EMP{i:05d}", f"Employee Name {i}", "Business Unit", "Position")
            for i in range(1000)
        ]
        self.db.bulk_insert_employees(employees)

        # Record 1000 scans
        for i in range(1000):
            self.db.record_scan(f"EMP{i:05d}", "TestStation", None)

        # Check file size
        file_size = self.db_path.stat().st_size
        file_size_mb = file_size / (1024 * 1024)

        # Should be under 5MB for 1000 employees + 1000 scans
        self.assertLess(file_size_mb, 5.0, f"Database size: {file_size_mb:.2f}MB")


def main():
    """Run tests with summary."""
    print("=" * 70)
    print("PERFORMANCE TESTS")
    print("=" * 70)
    print()

    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    suite.addTests(loader.loadTestsFromTestCase(TestDatabasePerformance))
    suite.addTests(loader.loadTestsFromTestCase(TestMemoryUsage))
    suite.addTests(loader.loadTestsFromTestCase(TestConcurrency))
    suite.addTests(loader.loadTestsFromTestCase(TestScalability))
    suite.addTests(loader.loadTestsFromTestCase(TestDatabaseSize))

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
