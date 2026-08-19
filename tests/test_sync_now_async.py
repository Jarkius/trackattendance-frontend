#!/usr/bin/env python3
"""Tests for Api.sync_now()'s async ack + sync_now_completed signal contract.

Covers the Slice B change to main.py's Api class:
- sync_now() returns an immediate {accepted, requestId, message} acknowledgement
  instead of blocking the calling (Qt UI) thread for the full network round-trip.
- The real result arrives later via sync_now_completed, carrying the same
  requestId, so JS can distinguish a stale/superseded result from the current one.
- mark_scans_as_synced/mark_scans_as_failed only ever run from the main-thread
  result-application slot (_on_manual_sync_result), never from the network job
  closure itself.
- "already in progress" and "coordinator rejected" paths return accepted=False
  without ever touching SQLite via the coordinator.

Requires PyQt6 (Api subclasses QObject and main.py imports PyQt6 at module level
unconditionally). Tests are skipped with a clear message when PyQt6 is
unavailable, matching the existing skip pattern in tests/test_auto_sync_manager.py.

Run: python tests/test_sync_now_async.py
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

os.environ.setdefault("CLOUD_API_KEY", "test-api-key-for-testing")
os.environ.setdefault("CLOUD_API_URL", "http://test.example.com")

sys.path.insert(0, str(Path(__file__).parent.parent))

from database import DatabaseManager, EmployeeRecord

try:
    from PyQt6.QtCore import QObject, QCoreApplication  # noqa: F401
    PYQT6_AVAILABLE = True
except ImportError:
    PYQT6_AVAILABLE = False

if PYQT6_AVAILABLE:
    from main import Api
    from sync import SyncService

    # QMetaObject.invokeMethod(..., Qt.ConnectionType.QueuedConnection) only
    # queues a call — it requires a running/pumped Qt event loop to actually
    # dispatch it. Api.sync_now()'s _deliver()/_deliver_error() callbacks use
    # exactly this to hop from the (simulated) worker thread back to
    # _on_manual_sync_result() on the main thread. Without an app instance and
    # explicit processEvents() calls, the queued call is posted but never runs,
    # so tests that call sync_now() and then assert on sync_now_completed must
    # pump the event loop first — see _pump_events() below.
    _APP = QCoreApplication.instance() or QCoreApplication([])

    def _pump_events(iterations: int = 10) -> None:
        """Process pending queued-connection calls so invokeMethod(...,
        QueuedConnection) callbacks (e.g. _on_manual_sync_result) actually run
        before the test asserts on their side effects."""
        for _ in range(iterations):
            _APP.processEvents()


class SynchronousCoordinator:
    """Fake BackgroundSyncCoordinator that runs jobs immediately on submit(),
    on the calling thread. Lets tests exercise sync_now()/the result callback
    deterministically without needing a running Qt event loop to pump a real
    cross-thread QueuedConnection."""

    def __init__(self):
        self.submitted = []

    def submit(self, job, on_result=None, on_error=None):
        self.submitted.append(job)
        try:
            result = job()
        except Exception as exc:
            if on_error:
                on_error(1, exc)
            return 1
        if on_result:
            on_result(1, result)
        return 1


class RejectingCoordinator:
    """Fake coordinator whose submit() always rejects (simulates shutdown/paused/
    queue-full), to verify sync_now() reports rejection without mutating state."""

    def submit(self, job, on_result=None, on_error=None):
        return None


def _make_api(sync_service, coordinator):
    """Build a real Api instance with minimal required constructor args."""
    return Api(
        service=MagicMock(),
        quit_callback=lambda: None,
        sync_service=sync_service,
        sync_coordinator=coordinator,
    )


@unittest.skipUnless(PYQT6_AVAILABLE, "PyQt6 not installed in this environment")
class TestSyncNowImmediateAck(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test.db"
        self.db = DatabaseManager(self.db_path)
        self.db.set_station_name("TestStation")
        self.sync_service = SyncService(db=self.db, api_url="http://test.example.com", api_key="test-key")

    def tearDown(self):
        self.db.close()
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_no_sync_service_returns_not_accepted(self):
        api = _make_api(sync_service=None, coordinator=SynchronousCoordinator())
        result = api.sync_now()
        self.assertFalse(result["accepted"])
        self.assertIsNone(result["requestId"])
        self.assertIn("not configured", result["message"])

    def test_no_pending_scans_still_accepted_with_request_id(self):
        self.sync_service.test_connection = MagicMock(return_value=(True, "ok"))
        self.sync_service.test_authentication = MagicMock(return_value=(True, "ok"))
        api = _make_api(self.sync_service, SynchronousCoordinator())

        result = api.sync_now()

        self.assertTrue(result["accepted"])
        self.assertIsInstance(result["requestId"], int)

    def test_accepted_response_returns_immediately_without_blocking_on_network(self):
        """submit() on the fake coordinator runs synchronously here for test
        determinism, but the CONTRACT under test is that sync_now()'s own
        return value never depends on the network job's result — it only
        depends on whether the job was accepted into the queue."""
        block_calls = []

        def blocking_connect():
            block_calls.append(1)
            return (True, "ok")

        self.sync_service.test_connection = blocking_connect
        self.sync_service.test_authentication = MagicMock(return_value=(True, "ok"))
        api = _make_api(self.sync_service, SynchronousCoordinator())

        result = api.sync_now()

        # The ack shape must not contain "synced"/"failed"/"pending" — those
        # only appear in the later sync_now_completed payload.
        self.assertIn("accepted", result)
        self.assertIn("requestId", result)
        self.assertNotIn("synced", result)
        self.assertNotIn("failed", result)

    def test_second_call_while_in_progress_is_rejected(self):
        """A coordinator whose submit() never invokes callbacks simulates a
        job that's still running — the second sync_now() call must be rejected
        rather than racing the first."""
        class NeverCompletingCoordinator:
            def submit(self, job, on_result=None, on_error=None):
                job()  # run it, but withhold the callback to simulate "in flight"
                return 1

        api = _make_api(self.sync_service, NeverCompletingCoordinator())
        self.sync_service.test_connection = MagicMock(return_value=(True, "ok"))
        self.sync_service.test_authentication = MagicMock(return_value=(True, "ok"))

        first = api.sync_now()
        self.assertTrue(first["accepted"])

        second = api.sync_now()
        self.assertFalse(second["accepted"])
        self.assertIn("already in progress", second["message"])

    def test_rejected_coordinator_submission_returns_not_accepted(self):
        self.db.record_scan("BADGE001", "TestStation", None)
        api = _make_api(self.sync_service, RejectingCoordinator())

        result = api.sync_now()

        self.assertFalse(result["accepted"])
        self.assertIsNone(result["requestId"])
        # The snapshotted scan must remain pending — nothing was claimed/lost.
        stats = self.db.get_sync_statistics()
        self.assertEqual(stats["pending"], 1)


@unittest.skipUnless(PYQT6_AVAILABLE, "PyQt6 not installed in this environment")
class TestSyncNowCompletionSignal(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test.db"
        self.db = DatabaseManager(self.db_path)
        self.db.set_station_name("TestStation")
        self.db.bulk_insert_employees([EmployeeRecord("EMP001", "Test User", "IT", "Engineer")])
        self.sync_service = SyncService(db=self.db, api_url="http://test.example.com", api_key="test-key")

    def tearDown(self):
        self.db.close()
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_completion_signal_carries_matching_request_id(self):
        self.db.record_scan("EMP001", "TestStation",
                             EmployeeRecord("EMP001", "Test User", "IT", "Engineer"))
        self.sync_service.test_connection = MagicMock(return_value=(True, "ok"))
        self.sync_service.test_authentication = MagicMock(return_value=(True, "ok"))
        self.sync_service.sync_scan_batch_network_only = MagicMock(return_value={
            "ok": True, "synced_ids": [], "failed_ids": [], "pending_ids": [],
            "synced_count": 0, "error": None,
        })
        # Fix synced_ids to match whatever scan id was actually recorded.
        scan_id = self.db.fetch_pending_scans()[0].id
        self.sync_service.sync_scan_batch_network_only.return_value["synced_ids"] = [scan_id]
        self.sync_service.sync_scan_batch_network_only.return_value["synced_count"] = 1

        api = _make_api(self.sync_service, SynchronousCoordinator())

        received = []
        api.sync_now_completed.connect(lambda payload: received.append(payload))

        ack = api.sync_now()
        _pump_events()  # let the QueuedConnection-dispatched _on_manual_sync_result run
        self.assertTrue(ack["accepted"])

        self.assertEqual(len(received), 1)
        self.assertEqual(received[0]["requestId"], ack["requestId"])
        self.assertTrue(received[0]["ok"])
        self.assertEqual(received[0]["synced"], 1)

    def test_network_job_never_touches_db_only_result_slot_does(self):
        """The job closure must call sync_scan_batch_network_only (not
        sync_pending_scans), and mark_scans_as_synced must only be invoked
        after the coordinator's callback runs, on the main thread."""
        self.db.record_scan("EMP001", "TestStation",
                             EmployeeRecord("EMP001", "Test User", "IT", "Engineer"))
        scan_id = self.db.fetch_pending_scans()[0].id

        self.sync_service.test_connection = MagicMock(return_value=(True, "ok"))
        self.sync_service.test_authentication = MagicMock(return_value=(True, "ok"))

        call_order = []
        original_mark_synced = self.db.mark_scans_as_synced

        def spy_mark_synced(ids):
            call_order.append("mark_synced")
            return original_mark_synced(ids)

        self.db.mark_scans_as_synced = spy_mark_synced

        def spy_network_only(scans, station_name):
            call_order.append("network_only")
            return {
                "ok": True, "synced_ids": [s.id for s in scans], "failed_ids": [],
                "pending_ids": [], "synced_count": len(scans), "error": None,
            }

        self.sync_service.sync_scan_batch_network_only = spy_network_only
        self.sync_service.sync_pending_scans = MagicMock(
            side_effect=AssertionError("sync_now must not call sync_pending_scans (touches DB from worker)")
        )

        api = _make_api(self.sync_service, SynchronousCoordinator())
        api.sync_now()
        _pump_events()  # let the QueuedConnection-dispatched _on_manual_sync_result run

        self.assertEqual(call_order, ["network_only", "mark_synced"])
        stats = self.db.get_sync_statistics()
        self.assertEqual(stats["synced"], 1)

    def test_failed_batch_result_marks_failed_and_reports_not_ok(self):
        self.db.record_scan("EMP002", "TestStation", None)
        scan_id = self.db.fetch_pending_scans()[0].id

        self.sync_service.test_connection = MagicMock(return_value=(True, "ok"))
        self.sync_service.test_authentication = MagicMock(return_value=(True, "ok"))
        self.sync_service.sync_scan_batch_network_only = MagicMock(return_value={
            "ok": True, "synced_ids": [], "failed_ids": [scan_id], "pending_ids": [],
            "synced_count": 0, "error": "API error: 400 (non-retryable)",
        })

        api = _make_api(self.sync_service, SynchronousCoordinator())
        received = []
        api.sync_now_completed.connect(lambda payload: received.append(payload))

        api.sync_now()
        _pump_events()  # let the QueuedConnection-dispatched _on_manual_sync_result run

        self.assertEqual(len(received), 1)
        self.assertFalse(received[0]["ok"])
        self.assertEqual(received[0]["failed"], 1)
        stats = self.db.get_sync_statistics()
        self.assertEqual(stats["failed"], 1)

    def test_connection_failure_reports_stage_via_signal_without_touching_db(self):
        self.db.record_scan("EMP003", "TestStation", None)
        self.sync_service.test_connection = MagicMock(return_value=(False, "network down"))
        self.sync_service.sync_scan_batch_network_only = MagicMock(
            side_effect=AssertionError("must not reach batch stage on connection failure")
        )

        api = _make_api(self.sync_service, SynchronousCoordinator())
        received = []
        api.sync_now_completed.connect(lambda payload: received.append(payload))

        api.sync_now()
        _pump_events()  # let the QueuedConnection-dispatched _on_manual_sync_result run

        self.assertEqual(len(received), 1)
        self.assertFalse(received[0]["ok"])
        self.assertIn("Cannot connect", received[0]["message"])
        # Scan must remain pending — connection failure happens before any batch work.
        stats = self.db.get_sync_statistics()
        self.assertEqual(stats["pending"], 1)

    def test_manual_sync_in_progress_flag_resets_after_completion(self):
        self.sync_service.test_connection = MagicMock(return_value=(True, "ok"))
        self.sync_service.test_authentication = MagicMock(return_value=(True, "ok"))
        api = _make_api(self.sync_service, SynchronousCoordinator())

        api.sync_now()
        _pump_events()  # let the QueuedConnection-dispatched _on_manual_sync_result run

        self.assertFalse(api._manual_sync_in_progress)


def main():
    print("=" * 70)
    print("SYNC NOW ASYNC ACK/COMPLETION TESTS")
    print("=" * 70)
    if not PYQT6_AVAILABLE:
        print("\n[SKIP] PyQt6 is not installed in this environment.")
        print("All tests in this file are skipped — main.py cannot be imported")
        print("without PyQt6. Run this file in a PyQt6-enabled environment for")
        print("real coverage.\n")
    print()

    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    suite.addTests(loader.loadTestsFromTestCase(TestSyncNowImmediateAck))
    suite.addTests(loader.loadTestsFromTestCase(TestSyncNowCompletionSignal))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    print()
    print("=" * 70)
    print(f"Tests run: {result.testsRun}")
    print(f"Skipped: {len(result.skipped)}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print("=" * 70)

    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
