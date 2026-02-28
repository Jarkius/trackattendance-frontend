#!/usr/bin/env python3
"""
Tests for DashboardService in dashboard.py.

Tests the dashboard data fetching, error handling, and export functionality.

Run: python tests/test_dashboard.py
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

# Set required environment variables BEFORE importing config
os.environ.setdefault("CLOUD_API_KEY", "test-api-key-for-testing")
os.environ.setdefault("CLOUD_API_URL", "http://test.example.com")

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from database import DatabaseManager, EmployeeRecord
from dashboard import DashboardService


class TestDashboardDataFetching(unittest.TestCase):
    """Test get_dashboard_data() method."""

    def setUp(self):
        """Set up test database and dashboard service."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test.db"
        self.db = DatabaseManager(self.db_path)
        self.db.set_station_name("TestStation")

        # Add test employees
        self.db.bulk_insert_employees([
            EmployeeRecord("TEST001", "Alice Smith", "IT", "Engineer"),
            EmployeeRecord("TEST002", "Bob Jones", "HR", "Manager"),
            EmployeeRecord("TEST003", "Carol White", "IT", "Developer"),
        ])

        self.export_dir = Path(self.temp_dir) / "exports"
        self.service = DashboardService(
            self.db,
            "http://test.example.com",
            "test-api-key",
            self.export_dir
        )

    def tearDown(self):
        """Clean up."""
        self.db.close()
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @patch('dashboard.requests.get')
    def test_successful_data_fetch(self, mock_get):
        """Test successful dashboard data fetch."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "total_scans": 100,
            "unique_badges": 50,
            "stations": [
                {"name": "Station1", "scans": 60, "unique": 30, "last_scan": "2024-01-01T10:30:00Z"},
                {"name": "Station2", "scans": 40, "unique": 20, "last_scan": "2024-01-01T11:00:00Z"},
            ]
        }
        mock_get.return_value = mock_response

        result = self.service.get_dashboard_data()

        self.assertEqual(result["registered"], 3)
        self.assertEqual(result["total_scans"], 100)
        self.assertEqual(result["scanned"], 50)
        self.assertEqual(len(result["stations"]), 2)
        self.assertIsNone(result["error"])

    @patch('dashboard.requests.get')
    def test_api_connection_error(self, mock_get):
        """Test handling of connection error."""
        import requests
        mock_get.side_effect = requests.exceptions.ConnectionError()

        result = self.service.get_dashboard_data()

        self.assertEqual(result["error"], "Cannot connect to cloud API")
        self.assertEqual(result["registered"], 3)  # Local data still works

    @patch('dashboard.requests.get')
    def test_api_timeout(self, mock_get):
        """Test handling of timeout."""
        import requests
        mock_get.side_effect = requests.exceptions.Timeout()

        result = self.service.get_dashboard_data()

        self.assertEqual(result["error"], "Cloud API timeout")

    @patch('dashboard.requests.get')
    def test_api_401_unauthorized(self, mock_get):
        """Test handling of 401 unauthorized."""
        mock_response = Mock()
        mock_response.status_code = 401
        mock_get.return_value = mock_response

        result = self.service.get_dashboard_data()

        self.assertEqual(result["error"], "Authentication failed - check API key")

    @patch('dashboard.requests.get')
    def test_api_503_unavailable(self, mock_get):
        """Test handling of 503 service unavailable."""
        mock_response = Mock()
        mock_response.status_code = 503
        mock_get.return_value = mock_response

        result = self.service.get_dashboard_data()

        self.assertEqual(result["error"], "Cloud database unavailable")

    @patch('dashboard.requests.get')
    def test_attendance_rate_calculation(self, mock_get):
        """Test attendance rate is calculated correctly."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "total_scans": 10,
            "unique_badges": 2,
            "stations": []
        }
        mock_get.return_value = mock_response

        result = self.service.get_dashboard_data()

        # 2 out of 3 employees = 66.7%
        self.assertAlmostEqual(result["attendance_rate"], 66.7, places=1)

    @patch('dashboard.requests.get')
    def test_zero_registered_no_division_error(self, mock_get):
        """Test no division by zero when no employees registered."""
        # Clear employees
        self.db._connection.execute("DELETE FROM employees")
        self.db._connection.commit()

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "total_scans": 5,
            "unique_badges": 3,
            "stations": []
        }
        mock_get.return_value = mock_response

        result = self.service.get_dashboard_data()

        self.assertEqual(result["attendance_rate"], 0.0)
        self.assertEqual(result["registered"], 0)


class TestDashboardFormatTime(unittest.TestCase):
    """Test _format_time() helper method."""

    def setUp(self):
        """Set up test service."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test.db"
        self.db = DatabaseManager(self.db_path)

        self.service = DashboardService(
            self.db,
            "http://test.example.com",
            "test-api-key"
        )

    def tearDown(self):
        """Clean up."""
        self.db.close()
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_format_valid_iso_timestamp(self):
        """Test formatting valid ISO timestamp."""
        result = self.service._format_time("2024-01-15T10:30:45Z")
        # Should return HH:MM:SS format in local timezone
        self.assertRegex(result, r'^\d{2}:\d{2}:\d{2}$')

    def test_format_none_returns_dash(self):
        """Test None timestamp returns '--'."""
        result = self.service._format_time(None)
        self.assertEqual(result, "--")

    def test_format_empty_string_returns_dash(self):
        """Test empty string returns '--'."""
        result = self.service._format_time("")
        self.assertEqual(result, "--")

    def test_format_invalid_timestamp_returns_dash(self):
        """Test invalid timestamp returns '--'."""
        result = self.service._format_time("not-a-timestamp")
        self.assertEqual(result, "--")


class TestDashboardBusinessUnits(unittest.TestCase):
    """Test BU breakdown functionality."""

    def setUp(self):
        """Set up test database with BU data."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test.db"
        self.db = DatabaseManager(self.db_path)
        self.db.set_station_name("TestStation")

        # Add employees in different BUs
        self.db.bulk_insert_employees([
            EmployeeRecord("IT001", "Alice", "IT", "Engineer"),
            EmployeeRecord("IT002", "Bob", "IT", "Developer"),
            EmployeeRecord("HR001", "Carol", "HR", "Manager"),
        ])

        # Record scans
        self.db.record_scan("IT001", "TestStation",
                           EmployeeRecord("IT001", "Alice", "IT", "Engineer"))

        self.service = DashboardService(
            self.db,
            "http://test.example.com",
            "test-api-key"
        )

    def tearDown(self):
        """Clean up."""
        self.db.close()
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @patch('dashboard.requests.get')
    def test_bu_breakdown_included(self, mock_get):
        """Test BU breakdown is included in dashboard data."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "total_scans": 1,
            "unique_badges": 1,
            "stations": []
        }
        mock_get.return_value = mock_response

        result = self.service.get_dashboard_data()

        self.assertIn("business_units", result)
        self.assertIsInstance(result["business_units"], list)

    @patch('dashboard.requests.get')
    def test_unmatched_badges_counted(self, mock_get):
        """Test unmatched badges are counted separately."""
        # Record unmatched scan
        self.db.record_scan("UNKNOWN001", "TestStation", None)

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "total_scans": 2,
            "unique_badges": 2,
            "stations": []
        }
        mock_get.return_value = mock_response

        result = self.service.get_dashboard_data()

        # Should have "(Unmatched)" entry
        unmatched = next(
            (bu for bu in result["business_units"] if bu["bu_name"] == "(Unmatched)"),
            None
        )
        self.assertIsNotNone(unmatched)
        self.assertEqual(unmatched["scanned"], 1)


class TestDashboardExport(unittest.TestCase):
    """Test export_to_excel() method."""

    def setUp(self):
        """Set up test database and service."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test.db"
        self.db = DatabaseManager(self.db_path)
        self.db.set_station_name("TestStation")

        self.db.bulk_insert_employees([
            EmployeeRecord("TEST001", "Alice", "IT", "Engineer"),
        ])

        self.export_dir = Path(self.temp_dir) / "exports"
        self.service = DashboardService(
            self.db,
            "http://test.example.com",
            "test-api-key",
            self.export_dir
        )

    def tearDown(self):
        """Clean up."""
        self.db.close()
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @patch('dashboard.requests.get')
    def test_export_connection_error(self, mock_get):
        """Test export handles connection error."""
        import requests
        mock_get.side_effect = requests.exceptions.ConnectionError()

        result = self.service.export_to_excel()

        self.assertFalse(result["ok"])
        self.assertEqual(result["message"], "Cannot connect to cloud API")

    @patch('dashboard.requests.get')
    def test_export_timeout(self, mock_get):
        """Test export handles timeout."""
        import requests
        mock_get.side_effect = requests.exceptions.Timeout()

        result = self.service.export_to_excel()

        self.assertFalse(result["ok"])
        self.assertEqual(result["message"], "Cloud API timeout")

    @patch('dashboard.requests.get')
    def test_export_no_data(self, mock_get):
        """Test export handles no data case."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"scans": []}
        mock_get.return_value = mock_response

        result = self.service.export_to_excel()

        self.assertFalse(result["ok"])
        self.assertEqual(result["message"], "No scan data to export")
        self.assertTrue(result.get("noData", False))

    @patch('dashboard.requests.get')
    def test_export_api_error(self, mock_get):
        """Test export handles API error status."""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_get.return_value = mock_response

        result = self.service.export_to_excel()

        self.assertFalse(result["ok"])
        self.assertIn("API error: 500", result["message"])


class TestDashboardHeaders(unittest.TestCase):
    """Test HTTP header generation."""

    def setUp(self):
        """Set up test service."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test.db"
        self.db = DatabaseManager(self.db_path)

        self.service = DashboardService(
            self.db,
            "http://test.example.com",
            "my-secret-api-key"
        )

    def tearDown(self):
        """Clean up."""
        self.db.close()
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_authorization_header(self):
        """Test Bearer token is included in headers."""
        headers = self.service._get_headers()

        self.assertIn("Authorization", headers)
        self.assertEqual(headers["Authorization"], "Bearer my-secret-api-key")

    def test_content_type_header(self):
        """Test Content-Type is set to JSON."""
        headers = self.service._get_headers()

        self.assertIn("Content-Type", headers)
        self.assertEqual(headers["Content-Type"], "application/json")


def main():
    """Run tests with summary."""
    print("=" * 70)
    print("DASHBOARD SERVICE TESTS")
    print("=" * 70)
    print()

    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    suite.addTests(loader.loadTestsFromTestCase(TestDashboardDataFetching))
    suite.addTests(loader.loadTestsFromTestCase(TestDashboardFormatTime))
    suite.addTests(loader.loadTestsFromTestCase(TestDashboardBusinessUnits))
    suite.addTests(loader.loadTestsFromTestCase(TestDashboardExport))
    suite.addTests(loader.loadTestsFromTestCase(TestDashboardHeaders))

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
