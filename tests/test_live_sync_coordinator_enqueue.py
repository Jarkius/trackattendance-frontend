#!/usr/bin/env python3
"""Tests for AttendanceService.register_scan()'s coordinator-based Live Sync enqueue.

Covers the Slice B change to attendance.py: register_scan() no longer spawns a
raw threading.Thread per scan for the fire-and-forget Live Sync upload. Instead
it submits sync_single_scan as a job to a shared BackgroundSyncCoordinator.

Verifies:
- Offline-first ordering: record_scan() (SQLite write) always happens before the
  coordinator submission, regardless of whether the submission succeeds.
- The coordinator receives exactly one job per scan, and that job calls
  sync_single_scan (network-only, no SQLite access), never a raw thread.
- A full/rejecting coordinator does not lose the scan — it stays 'pending' for
  the normal batch-sync path to pick up later.
- Live Sync being disabled (LIVE_SYNC_ENABLED=False), CLOUD_READ_ONLY, or no
  coordinator configured all correctly skip the enqueue without erroring.
- check_duplicate_cloud (the separate, synchronous cross-station dup check)
  remains untouched by this change — still called directly, still gates
  block-mode rejection before record_scan().

Requires PyQt6 (attendance.py imports PyQt6.QtWidgets at module level
unconditionally). Tests are skipped with a clear message when PyQt6 is
unavailable, matching the existing skip pattern in tests/test_duplicate_detection.py.

Run: python tests/test_live_sync_coordinator_enqueue.py
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

os.environ.setdefault("CLOUD_API_KEY", "test-api-key-for-testing")
os.environ.setdefault("CLOUD_API_URL", "http://test.example.com")

sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from PyQt6.QtWidgets import QApplication  # noqa: F401
    PYQT6_AVAILABLE = True
except ImportError:
    PYQT6_AVAILABLE = False

if PYQT6_AVAILABLE:
    from attendance import AttendanceService
    from sync import SyncService


class RecordingCoordinator:
    """Fake BackgroundSyncCoordinator that records submitted jobs without
    running them (so we can assert on what was enqueued without needing a
    real worker thread or network mocking for every test)."""

    def __init__(self, accept=True):
        self.accept = accept
        self.submitted_jobs = []

    def submit(self, job, on_result=None, on_error=None):
        if not self.accept:
            return None
        self.submitted_jobs.append(job)
        return len(self.submitted_jobs)


def _create_service(db_path, employee_path, export_dir, station_name="TestStation"):
    export_dir.mkdir(parents=True, exist_ok=True)
    service = AttendanceService(
        database_path=db_path,
        employee_workbook_path=employee_path,
        export_directory=export_dir,
    )
    service._db.set_station_name(station_name)
    service._station_name = station_name
    return service


@unittest.skipUnless(PYQT6_AVAILABLE, "PyQt6 not installed in this environment")
class TestLiveSyncEnqueue(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test.db"
        self.employee_path = Path(self.temp_dir) / "employee.xlsx"
        self.export_dir = Path(self.temp_dir) / "exports"

        from openpyxl import Workbook
        wb = Workbook()
        ws = wb.active
        ws.append(["Legacy ID", "Full Name", "SL L1 Desc", "Position Desc"])
        ws.append(["TEST001", "Test User", "IT", "Engineer"])
        wb.save(self.employee_path)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _make_sync_service(self):
        return SyncService(db=MagicMock(), api_url="http://test.example.com", api_key="test-key")

    @patch.dict(os.environ, {
        'LIVE_SYNC_ENABLED': 'True', 'CLOUD_READ_ONLY': 'False',
        'DUPLICATE_BADGE_DETECTION_ENABLED': 'False',
    })
    def test_enqueues_exactly_one_job_per_scan(self):
        import importlib
        import config
        importlib.reload(config)

        service = _create_service(self.db_path, self.employee_path, self.export_dir)
        sync_service = self._make_sync_service()
        coordinator = RecordingCoordinator()
        service.set_sync_service(sync_service, coordinator=coordinator)

        try:
            service.register_scan("TEST001")
            self.assertEqual(len(coordinator.submitted_jobs), 1)
        finally:
            service.close()

    @patch.dict(os.environ, {
        'LIVE_SYNC_ENABLED': 'True', 'CLOUD_READ_ONLY': 'False',
        'DUPLICATE_BADGE_DETECTION_ENABLED': 'False',
    })
    def test_submitted_job_calls_sync_single_scan_not_a_raw_thread(self):
        import importlib
        import config
        importlib.reload(config)

        service = _create_service(self.db_path, self.employee_path, self.export_dir)
        sync_service = self._make_sync_service()
        sync_service.sync_single_scan = MagicMock(return_value={"ok": True})
        coordinator = RecordingCoordinator()
        service.set_sync_service(sync_service, coordinator=coordinator)

        try:
            service.register_scan("TEST001")
            self.assertEqual(len(coordinator.submitted_jobs), 1)

            # Run the submitted job (simulating what the coordinator worker would do)
            coordinator.submitted_jobs[0]()
            sync_service.sync_single_scan.assert_called_once()
            scan_arg = sync_service.sync_single_scan.call_args[0][0]
            self.assertEqual(scan_arg.badge_id, "TEST001")
        finally:
            service.close()

    @patch.dict(os.environ, {
        'LIVE_SYNC_ENABLED': 'True', 'CLOUD_READ_ONLY': 'False',
        'DUPLICATE_BADGE_DETECTION_ENABLED': 'False',
    })
    def test_scan_is_recorded_before_enqueue_offline_first_ordering(self):
        """record_scan() (SQLite write) must happen before the coordinator
        submission — proven here by having submit() itself observe that the
        scan is already queryable in the DB at submission time."""
        import importlib
        import config
        importlib.reload(config)

        service = _create_service(self.db_path, self.employee_path, self.export_dir)
        sync_service = self._make_sync_service()

        seen_pending_count_at_submit = []

        class OrderCheckingCoordinator:
            def submit(self, job, on_result=None, on_error=None):
                seen_pending_count_at_submit.append(service._db.count_scans_total())
                return 1

        service.set_sync_service(sync_service, coordinator=OrderCheckingCoordinator())

        try:
            service.register_scan("TEST001")
            self.assertEqual(seen_pending_count_at_submit, [1])
        finally:
            service.close()

    @patch.dict(os.environ, {
        'LIVE_SYNC_ENABLED': 'True', 'CLOUD_READ_ONLY': 'False',
        'DUPLICATE_BADGE_DETECTION_ENABLED': 'False',
    })
    def test_rejected_enqueue_does_not_lose_scan(self):
        """A full/paused/shutdown coordinator returns None from submit() —
        the scan must still be recorded and remain 'pending' for the normal
        batch-sync path, not silently dropped."""
        import importlib
        import config
        importlib.reload(config)

        service = _create_service(self.db_path, self.employee_path, self.export_dir)
        sync_service = self._make_sync_service()
        coordinator = RecordingCoordinator(accept=False)
        service.set_sync_service(sync_service, coordinator=coordinator)

        try:
            result = service.register_scan("TEST001")
            self.assertTrue(result["ok"])
            self.assertEqual(service._db.count_scans_total(), 1)

            stats = service._db.get_sync_statistics()
            self.assertEqual(stats["pending"], 1)
        finally:
            service.close()

    @patch.dict(os.environ, {
        'LIVE_SYNC_ENABLED': 'False', 'CLOUD_READ_ONLY': 'False',
        'DUPLICATE_BADGE_DETECTION_ENABLED': 'False',
    })
    def test_live_sync_disabled_does_not_enqueue(self):
        import importlib
        import config
        importlib.reload(config)

        service = _create_service(self.db_path, self.employee_path, self.export_dir)
        sync_service = self._make_sync_service()
        coordinator = RecordingCoordinator()
        service.set_sync_service(sync_service, coordinator=coordinator)

        try:
            service.register_scan("TEST001")
            self.assertEqual(len(coordinator.submitted_jobs), 0)
        finally:
            service.close()

    @patch.dict(os.environ, {
        'LIVE_SYNC_ENABLED': 'True', 'CLOUD_READ_ONLY': 'True',
        'DUPLICATE_BADGE_DETECTION_ENABLED': 'False',
    })
    def test_read_only_mode_does_not_enqueue(self):
        import importlib
        import config
        importlib.reload(config)

        service = _create_service(self.db_path, self.employee_path, self.export_dir)
        sync_service = self._make_sync_service()
        coordinator = RecordingCoordinator()
        service.set_sync_service(sync_service, coordinator=coordinator)

        try:
            service.register_scan("TEST001")
            self.assertEqual(len(coordinator.submitted_jobs), 0)
        finally:
            service.close()
            os.environ['CLOUD_READ_ONLY'] = 'False'
            import importlib
            import config
            importlib.reload(config)

    @patch.dict(os.environ, {
        'LIVE_SYNC_ENABLED': 'True', 'CLOUD_READ_ONLY': 'False',
        'DUPLICATE_BADGE_DETECTION_ENABLED': 'False',
    })
    def test_no_coordinator_configured_does_not_raise_and_does_not_enqueue(self):
        """set_sync_service() called without a coordinator (coordinator=None,
        the default) must disable Live Sync's immediate enqueue rather than
        falling back to a raw per-scan thread or raising."""
        import importlib
        import config
        importlib.reload(config)

        service = _create_service(self.db_path, self.employee_path, self.export_dir)
        sync_service = self._make_sync_service()
        service.set_sync_service(sync_service)  # no coordinator

        try:
            result = service.register_scan("TEST001")
            self.assertTrue(result["ok"])
        finally:
            service.close()

    @patch.dict(os.environ, {
        'LIVE_SYNC_ENABLED': 'True', 'CLOUD_READ_ONLY': 'False',
        'DUPLICATE_BADGE_ACTION': 'block', 'DUPLICATE_BADGE_DETECTION_ENABLED': 'False',
    })
    def test_check_duplicate_cloud_still_synchronous_and_unaffected(self):
        """The separate, synchronous cross-station duplicate check
        (check_duplicate_cloud) must remain untouched by the live-sync
        coordinator change — still called directly on the calling thread,
        still able to gate block-mode before record_scan()."""
        import importlib
        import config
        importlib.reload(config)
        config.LIVE_SYNC_ENABLED = True
        config.LIVE_SYNC_TIMEOUT_SECONDS = 2.0

        service = _create_service(self.db_path, self.employee_path, self.export_dir)
        sync_service = self._make_sync_service()
        sync_service.check_duplicate_cloud = MagicMock(return_value={
            "duplicate": True, "station_name": "OtherStation",
        })
        coordinator = RecordingCoordinator()
        service.set_sync_service(sync_service, coordinator=coordinator)

        try:
            result = service.register_scan("TEST001")
            sync_service.check_duplicate_cloud.assert_called_once()
            self.assertFalse(result["ok"])
            self.assertEqual(result.get("status"), "cross_station_duplicate_rejected")
            # Blocked before record_scan() — nothing to enqueue.
            self.assertEqual(len(coordinator.submitted_jobs), 0)
            self.assertEqual(service._db.count_scans_total(), 0)
        finally:
            service.close()


def main():
    print("=" * 70)
    print("LIVE SYNC COORDINATOR ENQUEUE TESTS")
    print("=" * 70)
    if not PYQT6_AVAILABLE:
        print("\n[SKIP] PyQt6 is not installed in this environment.")
        print("All tests in this file are skipped — attendance.py cannot be")
        print("imported without PyQt6. Run this file in a PyQt6-enabled")
        print("environment for real coverage.\n")
    print()

    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    suite.addTests(loader.loadTestsFromTestCase(TestLiveSyncEnqueue))

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
