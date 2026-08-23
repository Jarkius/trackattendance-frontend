#!/usr/bin/env python3
"""End-to-end test for issue #65: pause_barrier() during an in-flight auto-sync
job, followed by reset_after_barrier() + resume() + a fresh trigger_auto_sync(),
must not leave the system stuck forever.

Uses a REAL BackgroundSyncCoordinator (not the SynchronousCoordinator fake used
elsewhere) so the test genuinely exercises the dequeue-then-still-running window
and the coordinator's generation-check-skips-the-callback behavior.

Requires PyQt6 (AutoSyncManager subclasses QObject and main.py imports PyQt6 at
module level unconditionally). Tests are skipped with a clear message when
PyQt6 is unavailable, matching the existing skip pattern in this test suite.

Run: python tests/test_barrier_reset_integration.py
"""

import os
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import MagicMock

os.environ.setdefault("CLOUD_API_KEY", "test-api-key-for-testing")
os.environ.setdefault("CLOUD_API_URL", "http://test.example.com")

sys.path.insert(0, str(Path(__file__).parent.parent))

from database import DatabaseManager, EmployeeRecord

try:
    from PyQt6.QtCore import QCoreApplication  # noqa: F401
    PYQT6_AVAILABLE = True
except ImportError:
    PYQT6_AVAILABLE = False

if PYQT6_AVAILABLE:
    from main import AutoSyncManager
    from sync import SyncService, BackgroundSyncCoordinator

    _APP = QCoreApplication.instance() or QCoreApplication([])

    def _pump_events(iterations: int = 20) -> None:
        for _ in range(iterations):
            _APP.processEvents()


class MockWebView:
    def page(self):
        return MockPage()


class MockPage:
    def runJavaScript(self, script):
        pass


@unittest.skipUnless(PYQT6_AVAILABLE, "PyQt6 not installed in this environment")
class TestBarrierResetIntegration(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test.db"
        self.db = DatabaseManager(self.db_path)
        self.db.set_station_name("TestStation")
        self.db.bulk_insert_employees([EmployeeRecord("EMP001", "Test User", "IT", "Engineer")])
        self.sync_service = SyncService(db=self.db, api_url="http://test.example.com", api_key="test-key")
        self.coordinator = BackgroundSyncCoordinator(max_queue_size=8)
        self.manager = AutoSyncManager(
            sync_service=self.sync_service, web_view=MockWebView(), coordinator=self.coordinator,
        )

    def tearDown(self):
        self.coordinator.shutdown(timeout=5)
        self.db.close()
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_barrier_during_in_flight_job_does_not_strand_state_forever(self):
        self.db.record_scan("EMP001", "TestStation",
                             EmployeeRecord("EMP001", "Test User", "IT", "Engineer"))

        job_started = threading.Event()
        release_job = threading.Event()

        def blocking_test_connection():
            job_started.set()
            release_job.wait(timeout=5)
            return (True, "ok")

        self.sync_service.test_connection = blocking_test_connection
        self.sync_service.test_authentication = MagicMock(return_value=(True, "ok"))

        def _fake_network_only(scans, station_name):
            ids = [s.id for s in scans]
            return {
                "ok": True, "synced_ids": ids, "failed_ids": [], "pending_ids": [],
                "synced_count": len(ids), "error": None,
            }

        self.sync_service.sync_scan_batch_network_only = _fake_network_only

        # 1. Trigger the first auto-sync — this submits a real job to the real
        #    coordinator's worker thread, which will block inside test_connection().
        self.manager.trigger_auto_sync()

        # 2. Wait for the job to actually be dequeued and start running.
        self.assertTrue(job_started.wait(timeout=5), "job did not start on the worker thread")

        # 3. Raise the barrier while the job is still blocked/running — simulates
        #    what admin_clear_cloud_data()/admin_clear_station_data() do.
        self.coordinator.pause_barrier()

        # 4. Reset the manager's guard state (the fix under test for issue #65).
        self.manager.reset_after_barrier()
        self.assertFalse(self.manager.is_syncing)
        self.assertTrue(self.manager._sync_lock.acquire(blocking=False))
        self.manager._sync_lock.release()

        # 5. Release the blocking job so it finishes; its callback must be
        #    skipped by the coordinator's generation check (existing barrier
        #    semantics) and must not clobber the state reset_after_barrier()
        #    already applied.
        release_job.set()
        _pump_events()
        self.assertFalse(self.manager.is_syncing)
        self.assertTrue(self.manager._sync_lock.acquire(blocking=False))
        self.manager._sync_lock.release()

        # 6. Resume the coordinator and confirm the system is NOT stuck forever:
        #    a fresh trigger_auto_sync() must actually submit and complete.
        self.coordinator.resume()

        self.sync_service.test_connection = MagicMock(return_value=(True, "ok"))
        self.manager.trigger_auto_sync()
        _pump_events()

        self.assertFalse(self.manager.is_syncing)
        stats = self.db.get_sync_statistics()
        self.assertEqual(stats["pending"], 0)
        self.assertEqual(stats["synced"], 1)


def main():
    print("=" * 70)
    print("BARRIER RESET INTEGRATION TEST")
    print("=" * 70)
    if not PYQT6_AVAILABLE:
        print("\n[SKIP] PyQt6 is not installed in this environment.")
        print("This test is skipped — main.py cannot be imported without PyQt6.")
        print("Run this file in a PyQt6-enabled environment for real coverage.\n")
    print()

    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    suite.addTests(loader.loadTestsFromTestCase(TestBarrierResetIntegration))

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
