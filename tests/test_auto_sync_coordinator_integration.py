#!/usr/bin/env python3
"""Tests for AutoSyncManager's coordinator integration and failure-cooldown logic.

Covers the Slice B changes to main.py's AutoSyncManager:
- AUTO_SYNC_MAX_CONSECUTIVE_FAILURES / AUTO_SYNC_FAILURE_COOLDOWN_SECONDS threshold
  and reset behavior (pure state, no Qt event loop required).
- _on_auto_sync_result() correctly applies mark_scans_as_synced/mark_scans_as_failed
  on the (simulated) main thread using the id lists a coordinator job would return,
  and never touches the DB from the job closure itself.

Requires PyQt6 (AutoSyncManager subclasses QObject and main.py imports PyQt6 at
module level unconditionally, so it cannot be imported at all without it). Tests
are skipped with a clear message when PyQt6 is unavailable, matching the existing
skip pattern in tests/test_auto_sync_manager.py and tests/test_duplicate_detection.py.

Run: python tests/test_auto_sync_coordinator_integration.py
"""

import os
import sys
import tempfile
import threading
import time
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
    import config
    from main import AutoSyncManager
    from sync import SyncService

    # QMetaObject.invokeMethod(..., Qt.ConnectionType.QueuedConnection) only
    # queues a call — it requires a running/pumped Qt event loop to actually
    # dispatch it. AutoSyncManager.trigger_auto_sync()'s _deliver()/_deliver_error()
    # callbacks use exactly this to hop from the (simulated) worker thread back
    # to _on_auto_sync_result() on the main thread. Without an app instance and
    # explicit processEvents() calls, the queued call is posted but never runs,
    # so tests that call trigger_auto_sync() and then assert on its result must
    # pump the event loop first — see _pump_events() below.
    _APP = QCoreApplication.instance() or QCoreApplication([])

    def _pump_events(iterations: int = 10) -> None:
        """Process pending queued-connection calls so invokeMethod(...,
        QueuedConnection) callbacks (e.g. _on_auto_sync_result) actually run
        before the test asserts on their side effects."""
        for _ in range(iterations):
            _APP.processEvents()


class SynchronousCoordinator:
    """Fake BackgroundSyncCoordinator that runs jobs immediately on submit(),
    on the calling thread, instead of spawning a real worker thread. Lets tests
    exercise trigger_auto_sync()/the result callbacks deterministically without
    needing a running Qt event loop to pump a real cross-thread QueuedConnection.
    """

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
    queue-full), to verify trigger_auto_sync() releases the lock cleanly."""

    def submit(self, job, on_result=None, on_error=None):
        return None


class MockWebView:
    def page(self):
        return MockPage()


class MockPage:
    def runJavaScript(self, script):
        pass


@unittest.skipUnless(PYQT6_AVAILABLE, "PyQt6 not installed in this environment")
class TestFailureCooldownThresholdAndReset(unittest.TestCase):
    """Pure state — no Qt event loop needed, since these methods don't touch
    QMetaObject/invokeMethod."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test.db"
        self.db = DatabaseManager(self.db_path)
        self.db.set_station_name("TestStation")
        self.sync_service = SyncService(db=self.db, api_url="http://test.example.com", api_key="test-key")
        self.manager = AutoSyncManager(
            sync_service=self.sync_service, web_view=MockWebView(),
            coordinator=SynchronousCoordinator(),
        )

    def tearDown(self):
        self.manager.shutdown_coordinator(timeout=1)
        self.db.close()
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_starts_with_zero_failures_and_no_cooldown(self):
        self.assertEqual(self.manager.consecutive_failures(), 0)
        self.assertFalse(self.manager.is_in_cooldown())

    def test_failures_below_threshold_do_not_trigger_cooldown(self):
        for _ in range(config.AUTO_SYNC_MAX_CONSECUTIVE_FAILURES - 1):
            self.manager._record_auto_sync_outcome(failed=True)
        self.assertEqual(
            self.manager.consecutive_failures(),
            config.AUTO_SYNC_MAX_CONSECUTIVE_FAILURES - 1,
        )
        self.assertFalse(self.manager.is_in_cooldown())

    def test_threshold_failure_triggers_cooldown(self):
        for _ in range(config.AUTO_SYNC_MAX_CONSECUTIVE_FAILURES):
            self.manager._record_auto_sync_outcome(failed=True)
        self.assertEqual(self.manager.consecutive_failures(), config.AUTO_SYNC_MAX_CONSECUTIVE_FAILURES)
        self.assertTrue(self.manager.is_in_cooldown())

    def test_success_resets_counter_and_cooldown(self):
        for _ in range(config.AUTO_SYNC_MAX_CONSECUTIVE_FAILURES):
            self.manager._record_auto_sync_outcome(failed=True)
        self.assertTrue(self.manager.is_in_cooldown())

        self.manager._record_auto_sync_outcome(failed=False)

        self.assertEqual(self.manager.consecutive_failures(), 0)
        self.assertFalse(self.manager.is_in_cooldown())

    def test_success_before_threshold_resets_counter(self):
        for _ in range(config.AUTO_SYNC_MAX_CONSECUTIVE_FAILURES - 1):
            self.manager._record_auto_sync_outcome(failed=True)
        self.manager._record_auto_sync_outcome(failed=False)
        self.assertEqual(self.manager.consecutive_failures(), 0)

    def test_cooldown_expires_after_configured_duration(self):
        for _ in range(config.AUTO_SYNC_MAX_CONSECUTIVE_FAILURES):
            self.manager._record_auto_sync_outcome(failed=True)
        self.assertTrue(self.manager.is_in_cooldown())

        # Simulate elapsed time by moving the cooldown deadline into the past,
        # rather than sleeping for the full (possibly long) configured duration.
        self.manager._cooldown_until = time.time() - 1

        self.assertFalse(self.manager.is_in_cooldown())

    def test_check_and_sync_skips_network_entirely_during_cooldown(self):
        for _ in range(config.AUTO_SYNC_MAX_CONSECUTIVE_FAILURES):
            self.manager._record_auto_sync_outcome(failed=True)

        # Insert a pending scan so check_and_sync would otherwise proceed.
        self.db.record_scan("BADGE001", "TestStation", None)
        self.manager.last_scan_time = time.time() - 3600  # force idle

        coordinator = self.manager._coordinator
        self.manager.check_and_sync()

        self.assertEqual(len(coordinator.submitted), 0, "cooldown must prevent any coordinator submission")


@unittest.skipUnless(PYQT6_AVAILABLE, "PyQt6 not installed in this environment")
class TestMainThreadResultApplication(unittest.TestCase):
    """Verify _on_auto_sync_result() — the slot invoked back on the main thread —
    correctly applies synced_ids/failed_ids to SQLite and never lets the network
    job closure itself touch the DB."""

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

    def _make_manager(self, coordinator):
        return AutoSyncManager(
            sync_service=self.sync_service, web_view=MockWebView(), coordinator=coordinator,
        )

    def test_trigger_auto_sync_network_job_never_touches_db(self):
        """The job closure built by trigger_auto_sync must call
        sync_scan_batch_network_only, not sync_pending_scans — the latter would
        touch self.db from the (simulated) worker thread."""
        self.db.record_scan("EMP001", "TestStation",
                             EmployeeRecord("EMP001", "Test User", "IT", "Engineer"))

        self.sync_service.test_connection = MagicMock(return_value=(True, "ok"))
        self.sync_service.test_authentication = MagicMock(return_value=(True, "ok"))

        touched_db_from_job = []
        original_network_only = self.sync_service.sync_scan_batch_network_only

        def spy(scans, station_name):
            # Confirm this is the method actually invoked, and that no db.*
            # method fires between snapshot (already done on "main thread")
            # and this call — i.e. the job itself is network-only.
            touched_db_from_job.append((len(scans), station_name))
            return {
                "ok": True, "synced_ids": [s.id for s in scans], "failed_ids": [],
                "pending_ids": [], "synced_count": len(scans), "error": None,
            }

        self.sync_service.sync_scan_batch_network_only = spy

        manager = self._make_manager(SynchronousCoordinator())
        manager.trigger_auto_sync()
        _pump_events()  # let the QueuedConnection-dispatched _on_auto_sync_result run

        self.assertEqual(len(touched_db_from_job), 1)
        self.assertEqual(touched_db_from_job[0][1], "TestStation")

        stats = self.db.get_sync_statistics()
        self.assertEqual(stats["synced"], 1)
        self.assertEqual(stats["pending"], 0)

    def test_result_application_marks_synced_and_failed_correctly(self):
        self.db.record_scan("EMP001", "TestStation",
                             EmployeeRecord("EMP001", "Test User", "IT", "Engineer"))
        scans = self.db.fetch_pending_scans()
        scan_id = scans[0].id

        manager = self._make_manager(SynchronousCoordinator())
        manager.is_syncing = True
        manager._sync_lock.acquire()
        manager._pending_outcome = {
            "stage": "batch",
            "ok": True,
            "batch_result": {
                "ok": True, "synced_ids": [scan_id], "failed_ids": [],
                "pending_ids": [], "synced_count": 1, "error": None,
            },
        }

        manager._on_auto_sync_result()

        stats = self.db.get_sync_statistics()
        self.assertEqual(stats["synced"], 1)
        self.assertEqual(stats["pending"], 0)
        self.assertFalse(manager.is_syncing)
        self.assertEqual(manager.consecutive_failures(), 0)

    def test_result_application_marks_failed_and_increments_cooldown_counter(self):
        self.db.record_scan("EMP002", "TestStation", None)
        scans = self.db.fetch_pending_scans()
        scan_id = scans[0].id

        manager = self._make_manager(SynchronousCoordinator())
        manager.is_syncing = True
        manager._sync_lock.acquire()
        manager._pending_outcome = {
            "stage": "batch",
            "ok": True,
            "batch_result": {
                "ok": True, "synced_ids": [], "failed_ids": [scan_id],
                "pending_ids": [], "synced_count": 0, "error": "API error: 400 (non-retryable)",
            },
        }

        manager._on_auto_sync_result()

        stats = self.db.get_sync_statistics()
        self.assertEqual(stats["failed"], 1)
        self.assertEqual(manager.consecutive_failures(), 1)

    def test_connection_stage_failure_increments_cooldown_without_touching_db(self):
        manager = self._make_manager(SynchronousCoordinator())
        manager.is_syncing = True
        manager._sync_lock.acquire()
        manager._pending_outcome = {"stage": "connection", "ok": False, "message": "no network"}

        manager._on_auto_sync_result()

        self.assertEqual(manager.consecutive_failures(), 1)
        self.assertFalse(manager.is_syncing)

    def test_rejected_coordinator_submission_releases_lock(self):
        self.db.record_scan("EMP003", "TestStation", None)
        manager = self._make_manager(RejectingCoordinator())

        manager.trigger_auto_sync()

        self.assertFalse(manager.is_syncing)
        self.assertTrue(manager._sync_lock.acquire(blocking=False))
        manager._sync_lock.release()

        # The snapshotted scan must remain pending — nothing was lost.
        stats = self.db.get_sync_statistics()
        self.assertEqual(stats["pending"], 1)

    def test_reset_after_barrier_clears_stranded_lock_and_flag(self):
        """Simulates a job that's dequeued/in-flight when a barrier fires and
        whose callback will never arrive (issue #65)."""
        manager = self._make_manager(SynchronousCoordinator())
        manager.is_syncing = True
        manager._sync_lock.acquire()

        manager.reset_after_barrier()

        self.assertFalse(manager.is_syncing)
        self.assertTrue(manager._sync_lock.acquire(blocking=False))
        manager._sync_lock.release()

    def test_reset_after_barrier_then_trigger_auto_sync_succeeds(self):
        """The exact 'stuck forever' regression scenario from issue #65: a
        stranded lock/flag must not prevent a subsequent trigger_auto_sync()
        from actually submitting a job."""
        self.db.record_scan("EMP001", "TestStation",
                             EmployeeRecord("EMP001", "Test User", "IT", "Engineer"))
        manager = self._make_manager(SynchronousCoordinator())
        manager.is_syncing = True
        manager._sync_lock.acquire()

        manager.reset_after_barrier()
        manager.trigger_auto_sync()

        coordinator = manager._coordinator
        self.assertEqual(len(coordinator.submitted), 1, "trigger_auto_sync must not hit the stale-lock early-out")

    def test_reset_after_barrier_is_idempotent_when_lock_not_held(self):
        manager = self._make_manager(SynchronousCoordinator())
        manager.reset_after_barrier()  # must not raise
        self.assertFalse(manager.is_syncing)

    def test_unrecognized_stage_treated_as_failure(self):
        """Issue #69: an unrecognized stage must not silently fall through
        into the batch-handling logic and record a false success."""
        manager = self._make_manager(SynchronousCoordinator())
        manager.is_syncing = True
        manager._sync_lock.acquire()
        manager._pending_outcome = {"stage": "bogus"}

        manager._on_auto_sync_result()

        self.assertEqual(manager.consecutive_failures(), 1)
        self.assertFalse(manager.is_syncing)

    def test_db_apply_exception_counts_as_failure_for_cooldown(self):
        """Issue #67: a network-successful upload whose local bookkeeping
        write then fails must not be treated as a success for cooldown
        purposes."""
        manager = self._make_manager(SynchronousCoordinator())
        manager.is_syncing = True
        manager._sync_lock.acquire()
        manager.sync_service.db.mark_scans_as_synced = MagicMock(side_effect=Exception("db write failed"))
        manager._pending_outcome = {
            "stage": "batch",
            "ok": True,
            "batch_result": {
                "ok": True, "synced_ids": [999], "failed_ids": [],
                "pending_ids": [], "synced_count": 1, "error": None,
            },
        }

        manager._on_auto_sync_result()

        self.assertEqual(manager.consecutive_failures(), 1)


def main():
    print("=" * 70)
    print("AUTO SYNC COORDINATOR INTEGRATION TESTS")
    print("=" * 70)
    if not PYQT6_AVAILABLE:
        print("\n[SKIP] PyQt6 is not installed in this environment.")
        print("All tests in this file are skipped — main.py cannot be imported")
        print("without PyQt6 (it does `from PyQt6.QtCore import ...` at module")
        print("level unconditionally). Run this file in a PyQt6-enabled")
        print("environment for real coverage.\n")
    print()

    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    suite.addTests(loader.loadTestsFromTestCase(TestFailureCooldownThresholdAndReset))
    suite.addTests(loader.loadTestsFromTestCase(TestMainThreadResultApplication))

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
