#!/usr/bin/env python3
"""
Tests for API authentication error handling in sync.py.

Tests authentication validation and error handling including:
- test_authentication() method
- 401/403 responses during sync
- Invalid API key scenarios

Run: python tests/test_sync_auth.py
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

# Set required environment variables BEFORE importing config
os.environ.setdefault("CLOUD_API_KEY", "test-api-key-for-testing")
os.environ.setdefault("CLOUD_API_URL", "http://test.example.com")

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import requests
from database import DatabaseManager, EmployeeRecord


class MockResponse:
    """Mock HTTP response for testing."""

    def __init__(self, status_code: int, json_data: dict = None, text: str = ""):
        self.status_code = status_code
        self._json_data = json_data or {}
        self.text = text
        self.elapsed = Mock()
        self.elapsed.total_seconds.return_value = 0.1

    def json(self):
        return self._json_data


class TestSyncAuthentication(unittest.TestCase):
    """Test authentication validation in SyncService."""

    def setUp(self):
        """Set up test database and sync service."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test.db"
        self.db = DatabaseManager(self.db_path)
        self.db.set_station_name("TestStation")

    def tearDown(self):
        """Clean up test resources."""
        self.db.close()
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _create_sync_service(self, api_key="valid-api-key"):
        """Create a SyncService with specified API key."""
        from sync import SyncService
        return SyncService(
            db=self.db,
            api_url="http://test-api.example.com",
            api_key=api_key,
            batch_size=10,
            connection_timeout=1.0,
        )

    # =========================================================================
    # test_authentication() Method Tests
    # =========================================================================

    @patch('sync.requests.post')
    def test_authentication_valid_key(self, mock_post):
        """Test authentication succeeds with valid API key."""
        mock_post.return_value = MockResponse(
            status_code=200,
            json_data={"saved": 0, "duplicates": 0}
        )

        service = self._create_sync_service(api_key="valid-key")
        success, message = service.test_authentication()

        self.assertTrue(success)
        self.assertIn("success", message.lower())

    @patch('sync.requests.post')
    def test_authentication_invalid_key_401(self, mock_post):
        """Test authentication fails with 401 Unauthorized."""
        mock_post.return_value = MockResponse(
            status_code=401,
            text="Unauthorized"
        )

        service = self._create_sync_service(api_key="invalid-key")
        success, message = service.test_authentication()

        self.assertFalse(success)
        self.assertIn("invalid", message.lower())

    @patch('sync.requests.post')
    def test_authentication_forbidden_403(self, mock_post):
        """Test authentication fails with 403 Forbidden."""
        mock_post.return_value = MockResponse(
            status_code=403,
            text="Forbidden"
        )

        service = self._create_sync_service(api_key="forbidden-key")
        success, message = service.test_authentication()

        self.assertFalse(success)
        self.assertIn("forbidden", message.lower())

    @patch('sync.requests.post')
    def test_authentication_timeout(self, mock_post):
        """Test authentication handles timeout gracefully."""
        mock_post.side_effect = requests.exceptions.Timeout("Connection timed out")

        service = self._create_sync_service()
        success, message = service.test_authentication()

        self.assertFalse(success)
        self.assertIn("timeout", message.lower())

    @patch('sync.requests.post')
    def test_authentication_connection_error(self, mock_post):
        """Test authentication handles connection error."""
        mock_post.side_effect = requests.exceptions.ConnectionError("Connection refused")

        service = self._create_sync_service()
        success, message = service.test_authentication()

        self.assertFalse(success)
        # Should contain error information
        self.assertTrue(len(message) > 0)

    @patch('sync.requests.post')
    def test_authentication_server_error_500(self, mock_post):
        """Test authentication handles 500 server error."""
        mock_post.return_value = MockResponse(
            status_code=500,
            text="Internal Server Error"
        )

        service = self._create_sync_service()
        success, message = service.test_authentication()

        self.assertFalse(success)
        self.assertIn("500", message)


class TestSyncAuthDuringSync(unittest.TestCase):
    """Test authentication errors during sync operations."""

    def setUp(self):
        """Set up test database with pending scan."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test.db"
        self.db = DatabaseManager(self.db_path)
        self.db.set_station_name("TestStation")

        # Add employee and create pending scan
        self.db.bulk_insert_employees([
            EmployeeRecord("TEST001", "Test User", "IT", "Engineer")
        ])
        self.db.record_scan("TEST001", "TestStation",
                           EmployeeRecord("TEST001", "Test User", "IT", "Engineer"))

    def tearDown(self):
        """Clean up."""
        self.db.close()
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _create_sync_service(self):
        """Create SyncService for testing."""
        from sync import SyncService
        return SyncService(
            db=self.db,
            api_url="http://test-api.example.com",
            api_key="test-key",
            batch_size=10,
        )

    @patch('sync.requests.post')
    def test_sync_401_no_retry(self, mock_post):
        """Test 401 during sync does not retry."""
        mock_post.return_value = MockResponse(status_code=401, text="Unauthorized")

        service = self._create_sync_service()
        result = service.sync_pending_scans()

        # Should only call once (no retry for auth errors)
        self.assertEqual(mock_post.call_count, 1)
        self.assertEqual(result["synced"], 0)

        # Scans should remain pending for manual intervention
        stats = self.db.get_sync_statistics()
        self.assertEqual(stats["pending"], 1)

    @patch('sync.requests.post')
    def test_sync_403_marks_failed(self, mock_post):
        """Test 403 during sync marks scans as failed."""
        mock_post.return_value = MockResponse(status_code=403, text="Forbidden")

        service = self._create_sync_service()
        result = service.sync_pending_scans()

        self.assertEqual(mock_post.call_count, 1)
        self.assertEqual(result["synced"], 0)
        self.assertEqual(result["failed"], 1)

        # Scans should be marked as failed
        stats = self.db.get_sync_statistics()
        self.assertEqual(stats["failed"], 1)

    @patch('sync.requests.post')
    def test_auth_error_message_propagated(self, mock_post):
        """Test authentication error message is in result."""
        mock_post.return_value = MockResponse(
            status_code=401,
            text="Invalid API key"
        )

        service = self._create_sync_service()
        result = service.sync_pending_scans()

        # Result should contain error information
        self.assertIn("error", result)


class TestEmptyApiKey(unittest.TestCase):
    """Test behavior with empty or missing API key."""

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

    def test_empty_api_key_detected(self):
        """Test empty API key is handled."""
        from sync import SyncService

        service = SyncService(
            db=self.db,
            api_url="http://test.example.com",
            api_key="",  # Empty key
        )

        # Empty key should still allow service creation
        # but auth test should fail
        self.assertIsNotNone(service)

    def test_whitespace_api_key_handled(self):
        """Test whitespace-only API key is handled."""
        from sync import SyncService

        service = SyncService(
            db=self.db,
            api_url="http://test.example.com",
            api_key="   ",  # Whitespace only
        )

        self.assertIsNotNone(service)


class TestAuthHeader(unittest.TestCase):
    """Test authentication header format."""

    def setUp(self):
        """Set up test database."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test.db"
        self.db = DatabaseManager(self.db_path)
        self.db.set_station_name("TestStation")

        # Add pending scan
        self.db.bulk_insert_employees([
            EmployeeRecord("TEST001", "Test User", "IT", "Engineer")
        ])
        self.db.record_scan("TEST001", "TestStation",
                           EmployeeRecord("TEST001", "Test User", "IT", "Engineer"))

    def tearDown(self):
        """Clean up."""
        self.db.close()
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @patch('sync.requests.post')
    def test_bearer_token_format(self, mock_post):
        """Test Authorization header uses Bearer token format."""
        mock_post.return_value = MockResponse(
            status_code=200,
            json_data={"saved": 1, "duplicates": 0}
        )

        from sync import SyncService
        service = SyncService(
            db=self.db,
            api_url="http://test.example.com",
            api_key="my-secret-key",
        )
        service.sync_pending_scans()

        # Check that Authorization header was set correctly
        call_kwargs = mock_post.call_args[1]
        headers = call_kwargs.get("headers", {})
        auth_header = headers.get("Authorization", "")

        self.assertTrue(auth_header.startswith("Bearer "))
        self.assertIn("my-secret-key", auth_header)

    @patch('sync.requests.post')
    def test_auth_endpoint_uses_bearer(self, mock_post):
        """Test authentication endpoint uses Bearer token."""
        mock_post.return_value = MockResponse(status_code=200, json_data={"saved": 0, "duplicates": 0})

        from sync import SyncService
        service = SyncService(
            db=self.db,
            api_url="http://test.example.com",
            api_key="test-key-123",
        )
        service.test_authentication()

        call_kwargs = mock_post.call_args[1]
        headers = call_kwargs.get("headers", {})
        auth_header = headers.get("Authorization", "")

        self.assertTrue(auth_header.startswith("Bearer "))


def main():
    """Run tests with summary."""
    print("=" * 70)
    print("SYNC AUTHENTICATION TESTS")
    print("=" * 70)
    print()

    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    suite.addTests(loader.loadTestsFromTestCase(TestSyncAuthentication))
    suite.addTests(loader.loadTestsFromTestCase(TestSyncAuthDuringSync))
    suite.addTests(loader.loadTestsFromTestCase(TestEmptyApiKey))
    suite.addTests(loader.loadTestsFromTestCase(TestAuthHeader))

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
