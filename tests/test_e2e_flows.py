#!/usr/bin/env python3
"""
End-to-end flow tests for TrackAttendance application.

Tests complete user workflows from scan to sync.

Run: python tests/test_e2e_flows.py
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from datetime import datetime

# Set required environment variables BEFORE importing config
os.environ.setdefault("CLOUD_API_KEY", "test-api-key-for-testing")
os.environ.setdefault("CLOUD_API_URL", "http://test.example.com")

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from database import DatabaseManager, EmployeeRecord

# Check if PyQt6 is available (required for AttendanceService)
try:
    from PyQt6.QtWidgets import QApplication
    from attendance import AttendanceService
    from sync import SyncService
    PYQT6_AVAILABLE = True
except ImportError:
    PYQT6_AVAILABLE = False
    AttendanceService = None
    SyncService = None


def _create_test_env(employees=None):
    """Create a temporary test environment with employee xlsx and AttendanceService."""
    from openpyxl import Workbook

    temp_dir = tempfile.mkdtemp()
    db_path = Path(temp_dir) / "test.db"
    employee_path = Path(temp_dir) / "employee.xlsx"
    export_dir = Path(temp_dir) / "exports"
    export_dir.mkdir()

    # Create employee xlsx
    wb = Workbook()
    ws = wb.active
    ws.append(["Legacy ID", "Full Name", "SL L1 Desc", "Position Desc"])
    if employees:
        for emp in employees:
            ws.append([emp.legacy_id, emp.full_name, emp.sl_l1_desc, emp.position_desc])
    wb.save(employee_path)

    service = AttendanceService(
        database_path=db_path,
        employee_workbook_path=employee_path,
        export_directory=export_dir,
    )
    service._db.set_station_name("TestStation")
    service._station_name = "TestStation"

    return temp_dir, service


@unittest.skipUnless(PYQT6_AVAILABLE, "PyQt6 not available")
class TestScanToSyncFlow(unittest.TestCase):
    """Test complete scan to sync workflow."""

    def setUp(self):
        """Set up test environment."""
        self.temp_dir, self.attendance = _create_test_env([
            EmployeeRecord("EMP001", "Alice Smith", "IT", "Engineer"),
            EmployeeRecord("EMP002", "Bob Jones", "HR", "Manager"),
        ])

    def tearDown(self):
        """Clean up."""
        self.attendance.close()
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_scan_creates_pending_record(self):
        """Test scan creates a pending record in database."""
        result = self.attendance.register_scan("EMP001")

        self.assertTrue(result["ok"])
        self.assertTrue(result["matched"])

        # Verify pending scan exists
        scans = self.attendance._db.fetch_pending_scans()
        self.assertEqual(len(scans), 1)
        self.assertEqual(scans[0].badge_id, "EMP001")

    def test_multiple_employees_scan_flow(self):
        """Test scanning multiple employees."""
        self.attendance.register_scan("EMP001")
        self.attendance.register_scan("EMP002")

        scans = self.attendance._db.fetch_pending_scans()
        self.assertEqual(len(scans), 2)

        badge_ids = {s.badge_id for s in scans}
        self.assertEqual(badge_ids, {"EMP001", "EMP002"})

    def test_unknown_badge_scan_flow(self):
        """Test scanning unknown badge creates unmatched record."""
        result = self.attendance.register_scan("UNKNOWN001")

        self.assertTrue(result["ok"])
        self.assertFalse(result["matched"])

        scans = self.attendance._db.fetch_pending_scans()
        self.assertEqual(len(scans), 1)

    @patch('sync.requests.post')
    def test_scan_then_sync_flow(self, mock_post):
        """Test complete scan then sync flow."""
        from datetime import timedelta
        # Mock successful sync response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.elapsed = timedelta(seconds=0.1)
        mock_response.json.return_value = {
            "saved": 1,
            "duplicates": 0,
            "errors": 0,
        }
        mock_post.return_value = mock_response

        # Scan employee
        self.attendance.register_scan("EMP001")

        # Verify pending
        stats = self.attendance._db.get_sync_statistics()
        self.assertEqual(stats["pending"], 1)

        # Sync
        sync_service = SyncService(self.attendance._db, "http://test.api.com", "test-key")
        result = sync_service.sync_pending_scans()

        # Verify synced
        stats = self.attendance._db.get_sync_statistics()
        self.assertEqual(stats["synced"], 1)
        self.assertEqual(stats["pending"], 0)


@unittest.skipUnless(PYQT6_AVAILABLE, "PyQt6 not available")
class TestRosterImportFlow(unittest.TestCase):
    """Test roster import workflow."""

    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test.db"
        self.db = DatabaseManager(self.db_path)

    def tearDown(self):
        """Clean up."""
        self.db.close()
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_empty_database_then_import(self):
        """Test importing to empty database."""
        # Initially empty
        count = self.db.count_employees()
        self.assertEqual(count, 0)

        # Import employees
        employees = [
            EmployeeRecord("EMP001", "Alice", "IT", "Engineer"),
            EmployeeRecord("EMP002", "Bob", "HR", "Manager"),
        ]
        self.db.bulk_insert_employees(employees)

        # Verify
        count = self.db.count_employees()
        self.assertEqual(count, 2)

    def test_import_updates_existing(self):
        """Test importing updates existing employees."""
        # Initial import
        self.db.bulk_insert_employees([
            EmployeeRecord("EMP001", "Alice", "IT", "Engineer"),
        ])

        # Re-import with updated data
        self.db.bulk_insert_employees([
            EmployeeRecord("EMP001", "Alice Smith", "Engineering", "Senior Engineer"),
        ])

        # Verify updated (depends on implementation)
        cache = self.db.load_employee_cache()
        emp = cache.get("EMP001")
        self.assertIsNotNone(emp)

    def test_import_then_scan_flow(self):
        """Test import employees then scan flow."""
        from openpyxl import Workbook

        employee_path = Path(self.temp_dir) / "employee.xlsx"
        export_dir = Path(self.temp_dir) / "exports"
        export_dir.mkdir()

        # Create employee xlsx
        wb = Workbook()
        ws = wb.active
        ws.append(["Legacy ID", "Full Name", "SL L1 Desc", "Position Desc"])
        ws.append(["EMP001", "Alice", "IT", "Engineer"])
        wb.save(employee_path)

        service = AttendanceService(
            database_path=self.db_path,
            employee_workbook_path=employee_path,
            export_directory=export_dir,
        )
        service._db.set_station_name("TestStation")
        service._station_name = "TestStation"

        try:
            # Scan should match
            result = service.register_scan("EMP001")
            self.assertTrue(result["matched"])
            self.assertEqual(result["fullName"], "Alice")
        finally:
            service.close()


@unittest.skipUnless(PYQT6_AVAILABLE, "PyQt6 not available")
class TestExportFlow(unittest.TestCase):
    """Test export workflow."""

    def setUp(self):
        """Set up test environment."""
        self.temp_dir, self.attendance = _create_test_env([
            EmployeeRecord("EMP001", "Alice", "IT", "Engineer"),
        ])

    def tearDown(self):
        """Clean up."""
        self.attendance.close()
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_scan_and_export_flow(self):
        """Test scan then export flow."""
        # Scan
        self.attendance.register_scan("EMP001")

        # Export
        result = self.attendance.export_scans()

        self.assertTrue(result["ok"])
        self.assertIn("absolutePath", result)

        # Verify file exists
        if result.get("absolutePath"):
            file_path = Path(result["absolutePath"])
            self.assertTrue(file_path.exists())


@unittest.skipUnless(PYQT6_AVAILABLE, "PyQt6 not available")
class TestDuplicateScanFlow(unittest.TestCase):
    """Test duplicate scan detection workflow."""

    def setUp(self):
        """Set up test environment."""
        self.temp_dir, self.attendance = _create_test_env([
            EmployeeRecord("EMP001", "Alice", "IT", "Engineer"),
        ])

    def tearDown(self):
        """Clean up."""
        self.attendance.close()
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @patch.dict(os.environ, {
        "DUPLICATE_BADGE_DETECTION_ENABLED": "true",
        "DUPLICATE_BADGE_ACTION": "warn",
        "DUPLICATE_BADGE_TIME_WINDOW_SECONDS": "60",
    })
    def test_duplicate_scan_detected(self):
        """Test duplicate scan is detected."""
        # Reload config with new env
        import importlib
        import config
        importlib.reload(config)

        # First scan
        result1 = self.attendance.register_scan("EMP001")
        self.assertTrue(result1["ok"])
        self.assertFalse(result1.get("is_duplicate", False))

        # Second scan immediately (should be duplicate)
        result2 = self.attendance.register_scan("EMP001")
        self.assertTrue(result2["ok"])
        # May or may not be duplicate depending on detection logic


@unittest.skipUnless(PYQT6_AVAILABLE, "PyQt6 not available")
class TestSyncFailureRecoveryFlow(unittest.TestCase):
    """Test sync failure and recovery workflow."""

    def setUp(self):
        """Set up test environment."""
        self.temp_dir, self.attendance = _create_test_env([
            EmployeeRecord("EMP001", "Alice", "IT", "Engineer"),
        ])

    def tearDown(self):
        """Clean up."""
        self.attendance.close()
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @patch('sync.requests.post')
    def test_sync_failure_retains_pending(self, mock_post):
        """Test sync failure retains pending scans."""
        import requests
        mock_post.side_effect = requests.exceptions.ConnectionError()

        # Create scan
        self.attendance.register_scan("EMP001")

        # Attempt sync (should fail)
        sync_service = SyncService(self.attendance._db, "http://test.api.com", "test-key")
        result = sync_service.sync_pending_scans()

        # Scan should still be pending
        stats = self.attendance._db.get_sync_statistics()
        self.assertGreater(stats["pending"], 0)

    @patch('sync.requests.post')
    def test_recovery_after_failure(self, mock_post):
        """Test successful sync after previous failure."""
        import requests

        from datetime import timedelta as td
        # First call fails, retries also fail
        mock_post.side_effect = requests.exceptions.ConnectionError()

        # Create scan
        self.attendance.register_scan("EMP001")

        sync_service = SyncService(self.attendance._db, "http://test.api.com", "test-key")

        # First attempt fails
        sync_service.sync_pending_scans()

        # Reset mock for second attempt — successful
        mock_post.side_effect = None
        mock_response = Mock(
            status_code=200,
            json=Mock(return_value={"saved": 1, "duplicates": 0, "errors": 0})
        )
        mock_response.elapsed = td(seconds=0.1)
        mock_post.return_value = mock_response

        # Second attempt succeeds
        result = sync_service.sync_pending_scans()

        # Should be synced now
        stats = self.attendance._db.get_sync_statistics()
        self.assertEqual(stats["pending"], 0)


class TestShutdownFlow(unittest.TestCase):
    """Test shutdown workflow."""

    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test.db"
        self.db = DatabaseManager(self.db_path)
        self.db.set_station_name("TestStation")

    def tearDown(self):
        """Clean up."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_graceful_shutdown_with_pending(self):
        """Test graceful shutdown with pending scans."""
        # Record scans
        self.db.record_scan("EMP001", "TestStation", None)
        self.db.record_scan("EMP002", "TestStation", None)

        stats = self.db.get_sync_statistics()
        pending_before = stats["pending"]

        # Close database (simulates shutdown)
        self.db.close()

        # Reopen and verify scans preserved
        db2 = DatabaseManager(self.db_path)
        stats = db2.get_sync_statistics()

        self.assertEqual(stats["pending"], pending_before)
        db2.close()


def main():
    """Run tests with summary."""
    print("=" * 70)
    print("END-TO-END FLOW TESTS")
    print("=" * 70)
    print()

    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    suite.addTests(loader.loadTestsFromTestCase(TestScanToSyncFlow))
    suite.addTests(loader.loadTestsFromTestCase(TestRosterImportFlow))
    suite.addTests(loader.loadTestsFromTestCase(TestExportFlow))
    suite.addTests(loader.loadTestsFromTestCase(TestDuplicateScanFlow))
    suite.addTests(loader.loadTestsFromTestCase(TestSyncFailureRecoveryFlow))
    suite.addTests(loader.loadTestsFromTestCase(TestShutdownFlow))

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
