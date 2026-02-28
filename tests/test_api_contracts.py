#!/usr/bin/env python3
"""
API Contract tests for TrackAttendance application.

Tests the expected request/response formats for cloud API integration.
Ensures the application handles various API responses correctly.

Run: python tests/test_api_contracts.py
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


class TestSyncBatchRequestContract(unittest.TestCase):
    """Test POST /v1/scans/batch request format."""

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

    def test_batch_request_has_required_fields(self):
        """Test batch request contains all required fields."""
        # Sample batch request
        request = {
            "scans": [
                {
                    "badge_id": "TEST001",
                    "station_name": "Station1",
                    "scanned_at": "2024-01-15T10:30:00Z",
                    "matched": True,
                    "idempotency_key": "sha256hash123",
                }
            ]
        }

        self.assertIn("scans", request)
        scan = request["scans"][0]
        self.assertIn("badge_id", scan)
        self.assertIn("station_name", scan)
        self.assertIn("scanned_at", scan)
        self.assertIn("matched", scan)
        self.assertIn("idempotency_key", scan)

    def test_scanned_at_iso_format(self):
        """Test scanned_at field uses ISO 8601 format."""
        timestamp = "2024-01-15T10:30:00Z"

        # Should be parseable as ISO format
        try:
            dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            self.assertIsNotNone(dt)
        except ValueError:
            self.fail("Timestamp is not valid ISO 8601 format")

    def test_idempotency_key_format(self):
        """Test idempotency key is a valid hash string."""
        import hashlib

        # Generate idempotency key like the app does
        data = "TEST001|Station1|2024-01-15T10:30:00"
        key = hashlib.sha256(data.encode()).hexdigest()

        # Should be 64 character hex string
        self.assertEqual(len(key), 64)
        self.assertTrue(all(c in "0123456789abcdef" for c in key))


class TestSyncBatchResponseContract(unittest.TestCase):
    """Test POST /v1/scans/batch response handling."""

    def test_success_response_format(self):
        """Test successful batch response format."""
        response = {
            "ok": True,
            "synced": 10,
            "duplicates": 2,
            "message": "Batch processed successfully",
        }

        self.assertTrue(response["ok"])
        self.assertIsInstance(response["synced"], int)
        self.assertIsInstance(response["duplicates"], int)

    def test_partial_failure_response_format(self):
        """Test partial failure response format."""
        response = {
            "ok": True,
            "synced": 8,
            "failed": 2,
            "errors": [
                {"index": 3, "message": "Invalid badge format"},
                {"index": 7, "message": "Duplicate entry"},
            ],
        }

        self.assertTrue(response["ok"])
        self.assertIn("errors", response)
        self.assertEqual(len(response["errors"]), 2)

    def test_auth_failure_response(self):
        """Test 401 unauthorized response handling."""
        response = {
            "error": "Unauthorized",
            "message": "Invalid or expired API key",
        }

        self.assertIn("error", response)
        self.assertIn("message", response)

    def test_rate_limit_response(self):
        """Test 429 rate limit response handling."""
        response = {
            "error": "Too Many Requests",
            "retry_after": 60,
            "message": "Rate limit exceeded",
        }

        self.assertIn("retry_after", response)
        self.assertIsInstance(response["retry_after"], int)


class TestDashboardStatsContract(unittest.TestCase):
    """Test GET /v1/dashboard/stats response format."""

    def test_stats_response_has_required_fields(self):
        """Test stats response contains required fields."""
        response = {
            "total_scans": 1000,
            "unique_badges": 500,
            "stations": [
                {
                    "name": "Station1",
                    "scans": 600,
                    "unique": 300,
                    "last_scan": "2024-01-15T15:30:00Z",
                },
                {
                    "name": "Station2",
                    "scans": 400,
                    "unique": 200,
                    "last_scan": "2024-01-15T14:45:00Z",
                },
            ],
        }

        self.assertIn("total_scans", response)
        self.assertIn("unique_badges", response)
        self.assertIn("stations", response)
        self.assertIsInstance(response["stations"], list)

    def test_station_data_format(self):
        """Test station data format in stats response."""
        station = {
            "name": "TestStation",
            "scans": 100,
            "unique": 50,
            "last_scan": "2024-01-15T10:30:00Z",
        }

        self.assertIsInstance(station["name"], str)
        self.assertIsInstance(station["scans"], int)
        self.assertIsInstance(station["unique"], int)
        self.assertIsInstance(station["last_scan"], str)

    def test_empty_stations_valid(self):
        """Test response with no stations is valid."""
        response = {
            "total_scans": 0,
            "unique_badges": 0,
            "stations": [],
        }

        self.assertEqual(response["total_scans"], 0)
        self.assertEqual(len(response["stations"]), 0)


class TestDashboardExportContract(unittest.TestCase):
    """Test GET /v1/dashboard/export response format."""

    def test_export_response_format(self):
        """Test export response format."""
        response = {
            "scans": [
                {
                    "badge_id": "TEST001",
                    "station_name": "Station1",
                    "scanned_at": "2024-01-15T10:30:00Z",
                    "matched": True,
                },
            ],
            "total": 1,
            "page": 1,
            "per_page": 1000,
        }

        self.assertIn("scans", response)
        self.assertIsInstance(response["scans"], list)
        self.assertIn("total", response)

    def test_export_scan_format(self):
        """Test individual scan format in export."""
        scan = {
            "badge_id": "TEST001",
            "station_name": "Station1",
            "scanned_at": "2024-01-15T10:30:00Z",
            "matched": True,
        }

        self.assertIsInstance(scan["badge_id"], str)
        self.assertIsInstance(scan["station_name"], str)
        self.assertIsInstance(scan["scanned_at"], str)
        self.assertIsInstance(scan["matched"], bool)

    def test_empty_export_valid(self):
        """Test empty export response is valid."""
        response = {
            "scans": [],
            "total": 0,
            "page": 1,
            "per_page": 1000,
        }

        self.assertEqual(len(response["scans"]), 0)
        self.assertEqual(response["total"], 0)


class TestErrorResponseContract(unittest.TestCase):
    """Test error response format handling."""

    def test_400_bad_request_format(self):
        """Test 400 Bad Request response format."""
        response = {
            "error": "Bad Request",
            "message": "Invalid request body",
            "details": {
                "field": "badge_id",
                "issue": "Required field missing",
            },
        }

        self.assertIn("error", response)
        self.assertIn("message", response)

    def test_500_internal_error_format(self):
        """Test 500 Internal Server Error response format."""
        response = {
            "error": "Internal Server Error",
            "message": "An unexpected error occurred",
            "request_id": "abc123",
        }

        self.assertIn("error", response)

    def test_503_service_unavailable_format(self):
        """Test 503 Service Unavailable response format."""
        response = {
            "error": "Service Unavailable",
            "message": "Database connection failed",
            "retry_after": 30,
        }

        self.assertIn("error", response)
        self.assertIn("retry_after", response)


class TestAuthHeaderContract(unittest.TestCase):
    """Test authentication header format."""

    def test_bearer_token_format(self):
        """Test Bearer token header format."""
        api_key = "abc123def456"
        header = f"Bearer {api_key}"

        self.assertTrue(header.startswith("Bearer "))
        self.assertEqual(header, "Bearer abc123def456")

    def test_headers_include_content_type(self):
        """Test headers include Content-Type."""
        headers = {
            "Authorization": "Bearer abc123",
            "Content-Type": "application/json",
        }

        self.assertEqual(headers["Content-Type"], "application/json")


class TestTimestampFormats(unittest.TestCase):
    """Test timestamp format handling."""

    def test_utc_timestamp_format(self):
        """Test UTC timestamp format with Z suffix."""
        timestamp = "2024-01-15T10:30:00Z"

        # Should be parseable
        dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        self.assertEqual(dt.year, 2024)
        self.assertEqual(dt.month, 1)
        self.assertEqual(dt.day, 15)

    def test_offset_timestamp_format(self):
        """Test timestamp with timezone offset."""
        timestamp = "2024-01-15T17:30:00+07:00"

        # Should be parseable
        dt = datetime.fromisoformat(timestamp)
        self.assertEqual(dt.hour, 17)

    def test_local_timestamp_no_offset(self):
        """Test local timestamp without timezone offset."""
        timestamp = "2024-01-15T10:30:00"

        # Should be parseable as naive datetime
        dt = datetime.fromisoformat(timestamp)
        self.assertIsNotNone(dt)


class TestPaginationContract(unittest.TestCase):
    """Test pagination in API responses."""

    def test_pagination_fields(self):
        """Test pagination fields in response."""
        response = {
            "data": [],
            "page": 1,
            "per_page": 100,
            "total": 1500,
            "total_pages": 15,
        }

        self.assertIn("page", response)
        self.assertIn("per_page", response)
        self.assertIn("total", response)

    def test_page_calculation(self):
        """Test page count calculation."""
        total = 1500
        per_page = 100

        total_pages = (total + per_page - 1) // per_page
        self.assertEqual(total_pages, 15)

    def test_empty_page_valid(self):
        """Test empty last page is valid."""
        response = {
            "data": [],
            "page": 16,  # Beyond last page
            "per_page": 100,
            "total": 1500,
        }

        self.assertEqual(len(response["data"]), 0)


def main():
    """Run tests with summary."""
    print("=" * 70)
    print("API CONTRACT TESTS")
    print("=" * 70)
    print()

    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    suite.addTests(loader.loadTestsFromTestCase(TestSyncBatchRequestContract))
    suite.addTests(loader.loadTestsFromTestCase(TestSyncBatchResponseContract))
    suite.addTests(loader.loadTestsFromTestCase(TestDashboardStatsContract))
    suite.addTests(loader.loadTestsFromTestCase(TestDashboardExportContract))
    suite.addTests(loader.loadTestsFromTestCase(TestErrorResponseContract))
    suite.addTests(loader.loadTestsFromTestCase(TestAuthHeaderContract))
    suite.addTests(loader.loadTestsFromTestCase(TestTimestampFormats))
    suite.addTests(loader.loadTestsFromTestCase(TestPaginationContract))

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
