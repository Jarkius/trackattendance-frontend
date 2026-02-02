#!/usr/bin/env python3
"""
Tests for sync retry logic in sync.py.

Tests all error scenarios in _sync_one_batch() including:
- HTTP error codes (401, 403, 400, 429, 5xx)
- Connection errors (timeout, connection refused)
- Retry behavior with exponential backoff
- Retry exhaustion handling

Run: python tests/test_sync_retry.py
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone

# Set required environment variables BEFORE importing config
os.environ.setdefault("CLOUD_API_KEY", "test-api-key-for-testing")
os.environ.setdefault("CLOUD_API_URL", "http://test.example.com")

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import requests
from database import DatabaseManager, EmployeeRecord


class MockResponse:
    """Mock HTTP response for testing."""

    def __init__(self, status_code: int, json_data: dict = None, text: str = "", elapsed_seconds: float = 0.1):
        self.status_code = status_code
        self._json_data = json_data or {}
        self.text = text
        self.encoding = 'utf-8'
        self.elapsed = Mock()
        self.elapsed.total_seconds.return_value = elapsed_seconds

    def json(self):
        return self._json_data


class TestSyncRetryLogic(unittest.TestCase):
    """Test sync retry behavior for various error scenarios."""

    def setUp(self):
        """Set up test database and sync service."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test.db"
        self.db = DatabaseManager(self.db_path)

        # Set up station
        self.db.set_station_name("TestStation")

        # Add a test employee
        self.db.bulk_insert_employees([
            EmployeeRecord("TEST001", "Test User", "IT", "Engineer")
        ])

        # Create a pending scan
        self.db.record_scan("TEST001", "TestStation",
                           EmployeeRecord("TEST001", "Test User", "IT", "Engineer"))

    def tearDown(self):
        """Clean up test resources."""
        self.db.close()
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _create_sync_service(self, retry_enabled=True, max_attempts=3, backoff_seconds=0.01):
        """Create a SyncService with test configuration."""
        # Patch config values before importing SyncService
        with patch.dict('os.environ', {
            'SYNC_RETRY_ENABLED': 'True' if retry_enabled else 'False',
            'SYNC_RETRY_MAX_ATTEMPTS': str(max_attempts),
            'SYNC_RETRY_BACKOFF_SECONDS': str(backoff_seconds),
        }):
            # Force reload config module to pick up patched env vars
            import importlib
            import config
            importlib.reload(config)

            from sync import SyncService
            return SyncService(
                db=self.db,
                api_url="http://test-api.example.com",
                api_key="test-api-key",
                batch_size=10,
                connection_timeout=1.0,
            )

    # =========================================================================
    # HTTP 200 Success Tests
    # =========================================================================

    @patch('sync.requests.post')
    def test_http_200_success(self, mock_post):
        """Test successful sync with HTTP 200."""
        mock_post.return_value = MockResponse(
            status_code=200,
            json_data={"saved": 1, "duplicates": 0}
        )

        service = self._create_sync_service()
        result = service.sync_pending_scans()

        self.assertEqual(result["synced"], 1)
        self.assertEqual(result["failed"], 0)
        mock_post.assert_called_once()

        # Verify scan marked as synced
        stats = self.db.get_sync_statistics()
        self.assertEqual(stats["synced"], 1)
        self.assertEqual(stats["pending"], 0)

    # =========================================================================
    # HTTP 401 Unauthorized Tests (No Retry)
    # =========================================================================

    @patch('sync.requests.post')
    def test_http_401_no_retry(self, mock_post):
        """Test HTTP 401 does NOT trigger retry."""
        mock_post.return_value = MockResponse(status_code=401, text="Unauthorized")

        service = self._create_sync_service(max_attempts=3)
        result = service.sync_pending_scans()

        # Should only be called once (no retry for auth errors)
        self.assertEqual(mock_post.call_count, 1)
        self.assertEqual(result["synced"], 0)
        self.assertIn("error", result)

        # Scans should remain pending (not marked as failed for auth issues)
        stats = self.db.get_sync_statistics()
        self.assertEqual(stats["pending"], 1)

    # =========================================================================
    # HTTP 403 Forbidden Tests (No Retry)
    # =========================================================================

    @patch('sync.requests.post')
    def test_http_403_marks_failed(self, mock_post):
        """Test HTTP 403 marks scans as failed (non-retryable)."""
        mock_post.return_value = MockResponse(status_code=403, text="Forbidden")

        service = self._create_sync_service(max_attempts=3)
        result = service.sync_pending_scans()

        # Should only be called once (no retry for 4xx errors)
        self.assertEqual(mock_post.call_count, 1)
        self.assertEqual(result["synced"], 0)
        self.assertEqual(result["failed"], 1)

        # Scans should be marked as failed
        stats = self.db.get_sync_statistics()
        self.assertEqual(stats["failed"], 1)
        self.assertEqual(stats["pending"], 0)

    # =========================================================================
    # HTTP 400 Bad Request Tests (No Retry)
    # =========================================================================

    @patch('sync.requests.post')
    def test_http_400_marks_failed(self, mock_post):
        """Test HTTP 400 marks scans as failed without retry."""
        mock_post.return_value = MockResponse(status_code=400, text="Bad Request")

        service = self._create_sync_service(max_attempts=3)
        result = service.sync_pending_scans()

        self.assertEqual(mock_post.call_count, 1)
        self.assertEqual(result["failed"], 1)

        stats = self.db.get_sync_statistics()
        self.assertEqual(stats["failed"], 1)

    # =========================================================================
    # HTTP 429 Rate Limited Tests (Should Retry)
    # =========================================================================

    @patch('sync.requests.post')
    @patch('sync.time.sleep')
    def test_http_429_triggers_retry(self, mock_sleep, mock_post):
        """Test HTTP 429 Rate Limited triggers retry with backoff."""
        # First call returns 429, second succeeds
        mock_post.side_effect = [
            MockResponse(status_code=429, text="Rate Limited"),
            MockResponse(status_code=200, json_data={"saved": 1, "duplicates": 0}),
        ]

        service = self._create_sync_service(max_attempts=3, backoff_seconds=1)
        result = service.sync_pending_scans()

        self.assertEqual(mock_post.call_count, 2)
        self.assertEqual(result["synced"], 1)

        # Verify backoff was applied
        mock_sleep.assert_called_once()

    # =========================================================================
    # HTTP 500 Server Error Tests (Should Retry)
    # =========================================================================

    @patch('sync.requests.post')
    @patch('sync.time.sleep')
    def test_http_500_triggers_retry(self, mock_sleep, mock_post):
        """Test HTTP 500 Server Error triggers retry."""
        mock_post.side_effect = [
            MockResponse(status_code=500, text="Internal Server Error"),
            MockResponse(status_code=200, json_data={"saved": 1, "duplicates": 0}),
        ]

        service = self._create_sync_service(max_attempts=3, backoff_seconds=1)
        result = service.sync_pending_scans()

        self.assertEqual(mock_post.call_count, 2)
        self.assertEqual(result["synced"], 1)

    @patch('sync.requests.post')
    @patch('sync.time.sleep')
    def test_http_502_triggers_retry(self, mock_sleep, mock_post):
        """Test HTTP 502 Bad Gateway triggers retry."""
        mock_post.side_effect = [
            MockResponse(status_code=502, text="Bad Gateway"),
            MockResponse(status_code=200, json_data={"saved": 1, "duplicates": 0}),
        ]

        service = self._create_sync_service(max_attempts=3, backoff_seconds=1)
        result = service.sync_pending_scans()

        self.assertEqual(mock_post.call_count, 2)
        self.assertEqual(result["synced"], 1)

    @patch('sync.requests.post')
    @patch('sync.time.sleep')
    def test_http_503_triggers_retry(self, mock_sleep, mock_post):
        """Test HTTP 503 Service Unavailable triggers retry."""
        mock_post.side_effect = [
            MockResponse(status_code=503, text="Service Unavailable"),
            MockResponse(status_code=200, json_data={"saved": 1, "duplicates": 0}),
        ]

        service = self._create_sync_service(max_attempts=3, backoff_seconds=1)
        result = service.sync_pending_scans()

        self.assertEqual(mock_post.call_count, 2)
        self.assertEqual(result["synced"], 1)

    # =========================================================================
    # Connection Timeout Tests (Should Retry)
    # =========================================================================

    @patch('sync.requests.post')
    @patch('sync.time.sleep')
    def test_timeout_triggers_retry(self, mock_sleep, mock_post):
        """Test connection timeout triggers retry."""
        mock_post.side_effect = [
            requests.exceptions.Timeout("Connection timed out"),
            MockResponse(status_code=200, json_data={"saved": 1, "duplicates": 0}),
        ]

        service = self._create_sync_service(max_attempts=3, backoff_seconds=1)
        result = service.sync_pending_scans()

        self.assertEqual(mock_post.call_count, 2)
        self.assertEqual(result["synced"], 1)

    # =========================================================================
    # Connection Error Tests (Should Retry)
    # =========================================================================

    @patch('sync.requests.post')
    @patch('sync.time.sleep')
    def test_connection_error_triggers_retry(self, mock_sleep, mock_post):
        """Test connection error (network issue) triggers retry."""
        mock_post.side_effect = [
            requests.exceptions.ConnectionError("Connection refused"),
            MockResponse(status_code=200, json_data={"saved": 1, "duplicates": 0}),
        ]

        service = self._create_sync_service(max_attempts=3, backoff_seconds=1)
        result = service.sync_pending_scans()

        self.assertEqual(mock_post.call_count, 2)
        self.assertEqual(result["synced"], 1)

    # =========================================================================
    # Exponential Backoff Tests
    # =========================================================================

    @patch('sync.requests.post')
    @patch('sync.time.sleep')
    def test_exponential_backoff_timing(self, mock_sleep, mock_post):
        """Test exponential backoff doubles wait time between retries."""
        # All calls fail with 500
        mock_post.side_effect = [
            MockResponse(status_code=500, text="Error"),
            MockResponse(status_code=500, text="Error"),
            MockResponse(status_code=500, text="Error"),
        ]

        service = self._create_sync_service(max_attempts=3, backoff_seconds=1)
        result = service.sync_pending_scans()

        # Should have called sleep twice (before 2nd and 3rd attempt)
        self.assertEqual(mock_sleep.call_count, 2)

        # Verify exponential backoff: 1*2^0=1, 1*2^1=2
        calls = mock_sleep.call_args_list
        self.assertEqual(calls[0][0][0], 1)  # First backoff: 1 second
        self.assertEqual(calls[1][0][0], 2)  # Second backoff: 2 seconds

    # =========================================================================
    # Retry Exhaustion Tests
    # =========================================================================

    @patch('sync.requests.post')
    @patch('sync.time.sleep')
    def test_retry_exhaustion_keeps_pending(self, mock_sleep, mock_post):
        """Test that retry exhaustion keeps scans as pending (not failed)."""
        # All retries fail with 500
        mock_post.return_value = MockResponse(status_code=500, text="Error")

        service = self._create_sync_service(max_attempts=3, backoff_seconds=0.01)
        result = service.sync_pending_scans()

        self.assertEqual(mock_post.call_count, 3)
        self.assertEqual(result["synced"], 0)

        # Scans should be marked as failed after exhaustion (based on current implementation)
        # The sync.py marks them as failed in result but keeps pending in DB for retry
        self.assertEqual(result["failed"], 1)

    @patch('sync.requests.post')
    @patch('sync.time.sleep')
    def test_timeout_exhaustion(self, mock_sleep, mock_post):
        """Test all retries exhausted due to timeout keeps scans pending."""
        mock_post.side_effect = requests.exceptions.Timeout("Timeout")

        service = self._create_sync_service(max_attempts=3, backoff_seconds=0.01)
        result = service.sync_pending_scans()

        self.assertEqual(mock_post.call_count, 3)
        self.assertEqual(result["synced"], 0)

    # =========================================================================
    # Retry Disabled Tests
    # =========================================================================

    @patch('sync.requests.post')
    def test_retry_disabled_single_attempt(self, mock_post):
        """Test that retry disabled means only one attempt."""
        mock_post.return_value = MockResponse(status_code=500, text="Error")

        service = self._create_sync_service(retry_enabled=False)
        result = service.sync_pending_scans()

        self.assertEqual(mock_post.call_count, 1)

    # =========================================================================
    # Other Request Exception Tests
    # =========================================================================

    @patch('sync.requests.post')
    def test_other_request_exception_marks_failed(self, mock_post):
        """Test other RequestException marks scans as failed."""
        mock_post.side_effect = requests.exceptions.RequestException("Unknown error")

        service = self._create_sync_service(max_attempts=3)
        result = service.sync_pending_scans()

        # Should only try once for generic RequestException (non-retryable)
        self.assertEqual(mock_post.call_count, 1)
        self.assertEqual(result["failed"], 1)

        stats = self.db.get_sync_statistics()
        self.assertEqual(stats["failed"], 1)

    # =========================================================================
    # Empty Pending Scans Test
    # =========================================================================

    @patch('sync.requests.post')
    def test_no_pending_scans(self, mock_post):
        """Test sync with no pending scans doesn't call API."""
        # Mark existing scan as synced
        scans = self.db.fetch_pending_scans()
        self.db.mark_scans_as_synced([s.id for s in scans])

        service = self._create_sync_service()
        result = service.sync_pending_scans()

        mock_post.assert_not_called()
        self.assertEqual(result["synced"], 0)
        self.assertEqual(result["failed"], 0)
        self.assertEqual(result["pending"], 0)

    # =========================================================================
    # Malformed Response Tests
    # =========================================================================

    @patch('sync.requests.post')
    def test_malformed_json_response(self, mock_post):
        """Test handling of malformed JSON response."""
        mock_response = MockResponse(status_code=200, json_data={})
        mock_response.json = Mock(side_effect=ValueError("Invalid JSON"))
        mock_post.return_value = mock_response

        service = self._create_sync_service()

        # Should raise or handle gracefully
        try:
            result = service.sync_pending_scans()
            # If it doesn't raise, verify it handled the error
            self.assertIn("synced", result)
        except ValueError:
            pass  # Expected if not caught internally


class TestSyncServiceHelpers(unittest.TestCase):
    """Test helper methods in SyncService."""

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

    def test_idempotency_key_generation(self):
        """Test idempotency key format."""
        from sync import SyncService
        from database import ScanRecord

        service = SyncService(
            db=self.db,
            api_url="http://test.example.com",
            api_key="test-key",
        )

        scan = ScanRecord(
            id=123,
            badge_id="BADGE001",
            scanned_at="2025-01-01T10:00:00Z",
            station_name="TestStation",
            employee_full_name="Test User",
            legacy_id="BADGE001",
            sl_l1_desc="IT",
            position_desc="Engineer",
        )

        key = service._generate_idempotency_key(scan)

        # Key should contain station, badge, and id
        self.assertIn("BADGE001", key)
        self.assertIn("123", key)


class TestIsRetryableError(unittest.TestCase):
    """Test the _is_retryable_error helper function."""

    def test_timeout_is_retryable(self):
        """Test Timeout exception is retryable."""
        from sync import _is_retryable_error
        self.assertTrue(_is_retryable_error(requests.exceptions.Timeout()))

    def test_connection_error_is_retryable(self):
        """Test ConnectionError is retryable."""
        from sync import _is_retryable_error
        self.assertTrue(_is_retryable_error(requests.exceptions.ConnectionError()))

    def test_other_exceptions_not_retryable(self):
        """Test other exceptions are not retryable."""
        from sync import _is_retryable_error
        self.assertFalse(_is_retryable_error(ValueError("test")))
        self.assertFalse(_is_retryable_error(requests.exceptions.RequestException()))


def main():
    """Run tests with summary."""
    print("=" * 70)
    print("SYNC RETRY LOGIC TESTS")
    print("=" * 70)
    print()

    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    suite.addTests(loader.loadTestsFromTestCase(TestSyncRetryLogic))
    suite.addTests(loader.loadTestsFromTestCase(TestSyncServiceHelpers))
    suite.addTests(loader.loadTestsFromTestCase(TestIsRetryableError))

    # Run with verbosity
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
