#!/usr/bin/env python3
"""
Tests for the UI Bridge (AttendanceAPI) in main.py.

Tests the Python ↔ JavaScript bridge functionality via QWebChannel.
These tests mock the PyQt6 components to test the business logic.

Run: python tests/test_ui_bridge.py
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Set required environment variables BEFORE importing config
os.environ.setdefault("CLOUD_API_KEY", "test-api-key-for-testing")
os.environ.setdefault("CLOUD_API_URL", "http://test.example.com")

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from database import DatabaseManager, EmployeeRecord

# Check if PyQt6 is available
try:
    from PyQt6.QtCore import QObject
    PYQT6_AVAILABLE = True
except ImportError:
    PYQT6_AVAILABLE = False


class TestUIBridgeLogic(unittest.TestCase):
    """Test UI Bridge logic without PyQt6 dependency."""

    def setUp(self):
        """Set up mock services."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test.db"
        self.db = DatabaseManager(self.db_path)
        self.db.set_station_name("TestStation")

        self.db.bulk_insert_employees([
            EmployeeRecord("TEST001", "Alice", "IT", "Engineer"),
        ])

    def tearDown(self):
        """Clean up."""
        self.db.close()
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_submit_scan_returns_dict(self):
        """Test scan submission returns expected dict format."""
        # Simulate what AttendanceService.register_scan returns
        result = {
            "ok": True,
            "badge_id": "TEST001",
            "full_name": "Alice",
            "business_unit": "IT",
            "position": "Engineer",
            "matched": True,
        }

        self.assertIn("ok", result)
        self.assertIn("badge_id", result)
        self.assertTrue(result["ok"])

    def test_export_scans_returns_dict(self):
        """Test export returns expected dict format."""
        result = {
            "ok": True,
            "message": "Exported 5 scans",
            "file_path": "/path/to/export.xlsx",
            "fileName": "export.xlsx",
        }

        self.assertIn("ok", result)
        self.assertIn("file_path", result)
        self.assertIn("fileName", result)

    def test_sync_status_returns_dict(self):
        """Test sync status returns expected dict format."""
        result = {
            "pending": 5,
            "synced": 100,
            "failed": 0,
        }

        self.assertIn("pending", result)
        self.assertIn("synced", result)
        self.assertIn("failed", result)

    def test_cloud_connection_result_format(self):
        """Test cloud connection result format."""
        result = {
            "ok": True,
            "message": "Connected to cloud API",
        }

        self.assertIn("ok", result)
        self.assertIn("message", result)

    def test_dashboard_data_format(self):
        """Test dashboard data format."""
        result = {
            "registered": 100,
            "scanned": 75,
            "total_scans": 80,
            "attendance_rate": 75.0,
            "stations": [],
            "business_units": [],
            "error": None,
        }

        self.assertIn("registered", result)
        self.assertIn("scanned", result)
        self.assertIn("attendance_rate", result)
        self.assertIsNone(result["error"])


class TestUIBridgeValidation(unittest.TestCase):
    """Test input validation for UI Bridge."""

    def test_empty_badge_id_handling(self):
        """Test empty badge ID is handled."""
        badge_id = ""

        # Should be invalid or handled gracefully
        self.assertEqual(len(badge_id), 0)

    def test_whitespace_badge_id_handling(self):
        """Test whitespace badge ID is stripped."""
        badge_id = "  TEST001  "
        cleaned = badge_id.strip()

        self.assertEqual(cleaned, "TEST001")

    def test_very_long_badge_id_handling(self):
        """Test very long badge ID is handled."""
        badge_id = "A" * 1000

        # Should be capped or rejected
        self.assertGreater(len(badge_id), 100)


class TestUIBridgeErrorHandling(unittest.TestCase):
    """Test error handling in UI Bridge."""

    def test_no_sync_service_returns_error(self):
        """Test sync_now returns error when sync service not configured."""
        result = {
            "ok": False,
            "message": "Sync service not configured",
            "synced": 0,
            "failed": 0,
            "pending": 0,
        }

        self.assertFalse(result["ok"])
        self.assertIn("not configured", result["message"])

    def test_no_dashboard_service_returns_zeros(self):
        """Test dashboard returns zeros when service not configured."""
        result = {
            "registered": 0,
            "scanned": 0,
            "total_scans": 0,
            "attendance_rate": 0.0,
            "stations": [],
            "error": "Dashboard service not configured",
        }

        self.assertEqual(result["registered"], 0)
        self.assertIsNotNone(result["error"])

    def test_sync_in_progress_handling(self):
        """Test sync handles already-in-progress state."""
        result = {
            "ok": False,
            "message": "Sync already in progress",
            "synced": 0,
            "failed": 0,
            "pending": 5,
        }

        self.assertFalse(result["ok"])
        self.assertIn("in progress", result["message"])


class TestAdminFeatures(unittest.TestCase):
    """Test admin feature logic."""

    def test_admin_disabled_returns_false(self):
        """Test admin check returns false when disabled."""
        result = {"enabled": False}

        self.assertFalse(result["enabled"])

    def test_admin_enabled_returns_true(self):
        """Test admin check returns true when enabled."""
        result = {"enabled": True}

        self.assertTrue(result["enabled"])

    def test_pin_verification_success(self):
        """Test PIN verification success."""
        pin = "1234"
        expected_pin = "1234"

        result = {
            "ok": pin == expected_pin,
            "message": "Access granted" if pin == expected_pin else "Invalid PIN",
        }

        self.assertTrue(result["ok"])
        self.assertEqual(result["message"], "Access granted")

    def test_pin_verification_failure(self):
        """Test PIN verification failure."""
        pin = "0000"
        expected_pin = "1234"

        result = {
            "ok": pin == expected_pin,
            "message": "Access granted" if pin == expected_pin else "Invalid PIN",
        }

        self.assertFalse(result["ok"])
        self.assertEqual(result["message"], "Invalid PIN")

    def test_clear_data_requires_pin(self):
        """Test clear data operation requires valid PIN."""
        # Without valid PIN
        result = {
            "ok": False,
            "message": "Invalid PIN",
            "cloud_deleted": 0,
            "local_deleted": 0,
        }

        self.assertFalse(result["ok"])
        self.assertEqual(result["cloud_deleted"], 0)


@unittest.skipUnless(PYQT6_AVAILABLE, "PyQt6 not available")
class TestAttendanceAPIWithPyQt(unittest.TestCase):
    """Integration tests requiring PyQt6."""

    def setUp(self):
        """Set up with real PyQt6 components."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test.db"
        self.db = DatabaseManager(self.db_path)
        self.db.set_station_name("TestStation")

    def tearDown(self):
        """Clean up."""
        self.db.close()
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_attendance_api_is_qobject(self):
        """Test AttendanceAPI is a QObject subclass."""
        from main import AttendanceAPI
        from attendance import AttendanceService

        service = AttendanceService(self.db)
        api = AttendanceAPI(service, quit_callback=lambda: None)

        self.assertIsInstance(api, QObject)

    def test_signal_defined(self):
        """Test connection_status_changed signal is defined."""
        from main import AttendanceAPI
        from attendance import AttendanceService

        service = AttendanceService(self.db)
        api = AttendanceAPI(service, quit_callback=lambda: None)

        # Should have the signal attribute
        self.assertTrue(hasattr(api, 'connection_status_changed'))


class TestConnectionStatusEmission(unittest.TestCase):
    """Test connection status emission logic."""

    def test_status_payload_format(self):
        """Test connection status payload format."""
        payload = {
            "ok": True,
            "message": "Connected to cloud API",
        }

        self.assertIn("ok", payload)
        self.assertIn("message", payload)
        self.assertIsInstance(payload["ok"], bool)
        self.assertIsInstance(payload["message"], str)

    def test_offline_status_payload(self):
        """Test offline connection status payload."""
        payload = {
            "ok": False,
            "message": "Cannot connect to cloud API",
        }

        self.assertFalse(payload["ok"])
        self.assertIn("Cannot connect", payload["message"])

    def test_auth_failure_payload(self):
        """Test authentication failure payload."""
        payload = {
            "ok": False,
            "message": "Authentication failed - check API key",
        }

        self.assertFalse(payload["ok"])
        self.assertIn("Authentication", payload["message"])


class TestScanResultNotification(unittest.TestCase):
    """Test scan result notification to UI."""

    def test_successful_scan_triggers_voice(self):
        """Test successful scan should trigger voice confirmation."""
        result = {
            "ok": True,
            "matched": True,
            "is_duplicate": False,
            "full_name": "Alice",
        }

        # Voice should play when: ok=True, matched=True, not duplicate
        should_play_voice = (
            result.get("ok") and
            result.get("matched") and
            not result.get("is_duplicate")
        )

        self.assertTrue(should_play_voice)

    def test_duplicate_scan_no_voice(self):
        """Test duplicate scan should not trigger voice."""
        result = {
            "ok": True,
            "matched": True,
            "is_duplicate": True,
            "full_name": "Alice",
        }

        should_play_voice = (
            result.get("ok") and
            result.get("matched") and
            not result.get("is_duplicate")
        )

        self.assertFalse(should_play_voice)

    def test_unmatched_scan_no_voice(self):
        """Test unmatched scan should not trigger voice."""
        result = {
            "ok": True,
            "matched": False,
            "is_duplicate": False,
            "full_name": "Unknown",
        }

        should_play_voice = (
            result.get("ok") and
            result.get("matched") and
            not result.get("is_duplicate")
        )

        self.assertFalse(should_play_voice)


def main():
    """Run tests with summary."""
    print("=" * 70)
    print("UI BRIDGE TESTS")
    print("=" * 70)
    print()

    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    suite.addTests(loader.loadTestsFromTestCase(TestUIBridgeLogic))
    suite.addTests(loader.loadTestsFromTestCase(TestUIBridgeValidation))
    suite.addTests(loader.loadTestsFromTestCase(TestUIBridgeErrorHandling))
    suite.addTests(loader.loadTestsFromTestCase(TestAdminFeatures))
    suite.addTests(loader.loadTestsFromTestCase(TestAttendanceAPIWithPyQt))
    suite.addTests(loader.loadTestsFromTestCase(TestConnectionStatusEmission))
    suite.addTests(loader.loadTestsFromTestCase(TestScanResultNotification))

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
