#!/usr/bin/env python3
"""Tests for SyncService.sync_scan_batch_network_only() in sync.py.

Covers the network-only counterpart to _sync_one_batch(): identical idempotency-key
output, retry/backoff classification, and — critically — zero access to a supplied
DatabaseManager, since this method is meant to run on a background worker thread
where touching the main thread's sqlite3 connection is unsafe.

Run: python tests/test_sync_network_only_batch.py
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

os.environ.setdefault("CLOUD_API_KEY", "test-api-key-for-testing")
os.environ.setdefault("CLOUD_API_URL", "http://test.example.com")
os.environ["CLOUD_READ_ONLY"] = "False"

sys.path.insert(0, str(Path(__file__).parent.parent))

import requests
from database import DatabaseManager, ScanRecord
from sync import SyncService, BackgroundSyncCoordinator


class MockResponse:
    def __init__(self, status_code: int, json_data: dict = None, text: str = "", elapsed_seconds: float = 0.1):
        self.status_code = status_code
        self._json_data = json_data or {}
        self.text = text
        self.encoding = 'utf-8'
        self.elapsed = Mock()
        self.elapsed.total_seconds.return_value = elapsed_seconds

    def json(self):
        return self._json_data


def _make_scan(scan_id=123, badge_id="BADGE001", station_name="TestStation") -> ScanRecord:
    return ScanRecord(
        id=scan_id,
        badge_id=badge_id,
        scanned_at="2025-01-01T10:00:00Z",
        station_name=station_name,
        employee_full_name="Test User",
        legacy_id=badge_id,
        sl_l1_desc="IT",
        position_desc="Engineer",
        scan_source="badge",
    )


class ExplodingDb:
    """A DatabaseManager stand-in that raises on ANY attribute access.

    Used to prove sync_scan_batch_network_only never touches self.db — if it did,
    this would raise AssertionError instead of the test passing quietly.
    """

    def __getattr__(self, name):
        raise AssertionError(
            f"sync_scan_batch_network_only must never access db.{name} (network-only contract violated)"
        )


class TestIdempotencyKeyParity(unittest.TestCase):
    """The network-only path must produce the exact same idempotency key format
    as the main-thread path (_generate_idempotency_key / _sync_one_batch)."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test.db"
        self.db = DatabaseManager(self.db_path)
        self.db.set_station_name("Main Gate")

    def tearDown(self):
        self.db.close()
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_supplied_scan_produces_same_key_as_main_thread_path(self):
        service = SyncService(db=self.db, api_url="http://test.example.com", api_key="test-key")
        scan = _make_scan(scan_id=456, badge_id="BADGE042", station_name="Main Gate")

        main_thread_key = service._generate_idempotency_key(scan)
        network_only_key = service._build_idempotency_key("Main Gate", scan.badge_id, scan.id)

        self.assertEqual(main_thread_key, network_only_key)
        self.assertEqual(main_thread_key, "MainGate-BADGE042-456")

    def test_space_and_hyphen_sanitization_matches_exactly(self):
        service = SyncService(db=self.db, api_url="http://test.example.com", api_key="test-key")
        for station in ("Main-Gate West", "  Multi  Space  ", "Hyphen-Heavy-Name-Here"):
            self.db.set_station_name(station)
            if hasattr(service, '_cached_station_name'):
                del service._cached_station_name  # force re-resolve for this station
            scan = _make_scan(scan_id=1, badge_id="B1")

            main_thread_key = service._generate_idempotency_key(scan)
            network_only_key = service._build_idempotency_key(station, "B1", 1)

            self.assertEqual(main_thread_key, network_only_key, f"mismatch for station={station!r}")

    def test_batch_events_use_same_idempotency_key_as_single_scan_helper(self):
        service = SyncService(db=self.db, api_url="http://test.example.com", api_key="test-key")
        scan = _make_scan(scan_id=789, badge_id="BADGE789", station_name="Main Gate")

        events = service._build_batch_events([scan], "Main Gate")

        self.assertEqual(events[0]["idempotency_key"], "MainGate-BADGE789-789")


class TestNetworkOnlyNeverTouchesDb(unittest.TestCase):
    """The defining contract: this method must be safe to call from a background
    worker thread, which means it must never read or write a DatabaseManager."""

    def _make_service(self):
        return SyncService(db=ExplodingDb(), api_url="http://test.example.com", api_key="test-key")

    @patch('sync.requests.post')
    def test_success_path_never_touches_db(self, mock_post):
        mock_post.return_value = MockResponse(200, {"saved": 1, "duplicates": 0})
        service = self._make_service()
        scan = _make_scan()

        result = service.sync_scan_batch_network_only([scan], "TestStation")

        self.assertEqual(result["synced_ids"], [scan.id])
        self.assertEqual(result["synced_count"], 1)

    @patch('sync.requests.post')
    def test_permanent_error_path_never_touches_db(self, mock_post):
        mock_post.return_value = MockResponse(400, text="Bad Request")
        service = self._make_service()
        scan = _make_scan()

        result = service.sync_scan_batch_network_only([scan], "TestStation")

        self.assertEqual(result["failed_ids"], [scan.id])

    @patch('sync.time.sleep')
    @patch('sync.requests.post')
    def test_retry_exhaustion_path_never_touches_db(self, mock_post, mock_sleep):
        mock_post.return_value = MockResponse(500, text="Error")
        service = self._make_service()
        scan = _make_scan()

        with patch.dict('os.environ', {
            'SYNC_RETRY_MAX_ATTEMPTS': '2', 'SYNC_RETRY_BACKOFF_SECONDS': '0.01',
        }):
            import importlib
            import config
            importlib.reload(config)
            result = service.sync_scan_batch_network_only([scan], "TestStation")
            importlib.reload(config)

        self.assertEqual(result["pending_ids"], [scan.id])

    @patch('sync.requests.post')
    def test_malformed_response_path_never_touches_db(self, mock_post):
        mock_response = MockResponse(200, {})
        mock_response.json = Mock(side_effect=ValueError("Invalid JSON"))
        mock_post.return_value = mock_response
        service = self._make_service()
        scan = _make_scan()

        result = service.sync_scan_batch_network_only([scan], "TestStation")

        self.assertFalse(result["ok"])
        self.assertEqual(result["failed_ids"], [scan.id])

    def test_empty_scan_list_never_touches_db(self):
        service = self._make_service()
        result = service.sync_scan_batch_network_only([], "TestStation")
        self.assertEqual(result, {
            "ok": True, "synced_ids": [], "failed_ids": [], "pending_ids": [],
            "synced_count": 0, "error": None,
        })

    @patch.dict(os.environ, {"CLOUD_READ_ONLY": "True"})
    def test_read_only_mode_never_touches_db(self):
        import importlib
        import config
        importlib.reload(config)
        try:
            service = self._make_service()
            scan = _make_scan()
            result = service.sync_scan_batch_network_only([scan], "TestStation")
            self.assertEqual(result["pending_ids"], [scan.id])
            self.assertEqual(result["synced_ids"], [])
        finally:
            os.environ["CLOUD_READ_ONLY"] = "False"
            importlib.reload(config)


class TestResultClassification(unittest.TestCase):
    """Verify the id-bucketing (synced/failed/pending) matches _sync_one_batch's
    existing classification rules for each HTTP/error scenario."""

    def _make_service(self):
        db = DatabaseManager(self.db_path)
        db.set_station_name("TestStation")
        self.db = db
        return SyncService(db=db, api_url="http://test.example.com", api_key="test-key")

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test.db"

    def tearDown(self):
        self.db.close()
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @patch('sync.requests.post')
    def test_success_returns_all_ids_as_synced(self, mock_post):
        mock_post.return_value = MockResponse(200, {"saved": 2, "duplicates": 0})
        service = self._make_service()
        scans = [_make_scan(1, "B1"), _make_scan(2, "B2")]

        result = service.sync_scan_batch_network_only(scans, "TestStation")

        self.assertTrue(result["ok"])
        self.assertEqual(sorted(result["synced_ids"]), [1, 2])
        self.assertEqual(result["failed_ids"], [])
        self.assertEqual(result["pending_ids"], [])
        self.assertEqual(result["synced_count"], 2)

    @patch('sync.requests.post')
    def test_401_returns_all_ids_as_pending_not_failed(self, mock_post):
        """Matches _sync_one_batch: 401 is an auth problem, not a per-scan failure —
        scans stay pending so a future successful auth can retry them."""
        mock_post.return_value = MockResponse(401, text="Unauthorized")
        service = self._make_service()
        scan = _make_scan()

        result = service.sync_scan_batch_network_only([scan], "TestStation")

        self.assertEqual(result["pending_ids"], [scan.id])
        self.assertEqual(result["failed_ids"], [])
        self.assertIsNotNone(result["error"])
        self.assertFalse(result["ok"])

    @patch('sync.requests.post')
    def test_400_marks_as_failed(self, mock_post):
        mock_post.return_value = MockResponse(400, text="Bad Request")
        service = self._make_service()
        scan = _make_scan()

        result = service.sync_scan_batch_network_only([scan], "TestStation")

        self.assertEqual(result["failed_ids"], [scan.id])
        self.assertEqual(result["pending_ids"], [])
        self.assertFalse(result["ok"])

    @patch('sync.time.sleep')
    @patch('sync.requests.post')
    def test_429_triggers_retry_then_succeeds(self, mock_post, mock_sleep):
        mock_post.side_effect = [
            MockResponse(429, text="Rate Limited"),
            MockResponse(200, {"saved": 1, "duplicates": 0}),
        ]
        service = self._make_service()
        scan = _make_scan()

        with patch.dict('os.environ', {'SYNC_RETRY_BACKOFF_SECONDS': '0.01'}):
            import importlib
            import config
            importlib.reload(config)
            result = service.sync_scan_batch_network_only([scan], "TestStation")
            importlib.reload(config)

        self.assertEqual(mock_post.call_count, 2)
        self.assertEqual(result["synced_ids"], [scan.id])

    @patch('sync.requests.post')
    def test_connection_error_returns_all_ids_as_failed(self, mock_post):
        mock_post.side_effect = requests.exceptions.RequestException("boom")
        service = self._make_service()
        scan = _make_scan()

        result = service.sync_scan_batch_network_only([scan], "TestStation")

        self.assertEqual(result["failed_ids"], [scan.id])
        self.assertFalse(result["ok"])

    @patch('sync.time.sleep')
    @patch('sync.requests.post')
    def test_retry_exhaustion_keeps_pending(self, mock_post, mock_sleep):
        mock_post.return_value = MockResponse(500, text="Error")
        service = self._make_service()
        scan = _make_scan()

        with patch.dict('os.environ', {
            'SYNC_RETRY_MAX_ATTEMPTS': '3', 'SYNC_RETRY_BACKOFF_SECONDS': '0.01',
        }):
            import importlib
            import config
            importlib.reload(config)
            result = service.sync_scan_batch_network_only([scan], "TestStation")
            importlib.reload(config)

        self.assertEqual(mock_post.call_count, 3)
        self.assertEqual(result["pending_ids"], [scan.id])
        self.assertEqual(result["synced_ids"], [])
        self.assertEqual(result["failed_ids"], [])
        self.assertFalse(result["ok"])


class TestCoordinatorIntegration(unittest.TestCase):
    """Sanity check that sync_scan_batch_network_only is actually safe to submit
    as a coordinator job — i.e. it can run on the coordinator's worker thread
    with a DatabaseManager stand-in that would blow up on any access."""

    @patch('sync.requests.post')
    def test_runs_cleanly_as_a_coordinator_job(self, mock_post):
        import threading
        mock_post.return_value = MockResponse(200, {"saved": 1, "duplicates": 0})
        service = SyncService(db=ExplodingDb(), api_url="http://test.example.com", api_key="test-key")
        scan = _make_scan()
        coordinator = BackgroundSyncCoordinator(max_queue_size=4)
        done = threading.Event()
        captured = {}

        def job():
            return service.sync_scan_batch_network_only([scan], "TestStation")

        def on_result(job_id, result):
            captured["result"] = result
            done.set()

        try:
            coordinator.submit(job, on_result=on_result)
            self.assertTrue(done.wait(timeout=5))
            self.assertEqual(captured["result"]["synced_ids"], [scan.id])
        finally:
            coordinator.shutdown(timeout=5)


def main():
    print("=" * 70)
    print("SYNC NETWORK-ONLY BATCH TESTS")
    print("=" * 70)
    print()

    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    suite.addTests(loader.loadTestsFromTestCase(TestIdempotencyKeyParity))
    suite.addTests(loader.loadTestsFromTestCase(TestNetworkOnlyNeverTouchesDb))
    suite.addTests(loader.loadTestsFromTestCase(TestResultClassification))
    suite.addTests(loader.loadTestsFromTestCase(TestCoordinatorIntegration))

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
