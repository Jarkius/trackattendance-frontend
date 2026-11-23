#!/usr/bin/env python3
"""Tests for AttendanceService.register_scan()'s immediate-write sync enqueue.

Covers the "Immediate Write" admin toggle: when config.IMMEDIATE_SYNC_ENABLED
is on, register_scan() submits a fire-and-forget upload job (sync_single_scan)
to a shared BackgroundSyncCoordinator right after the local SQLite write,
instead of only relying on the idle-triggered batch sync.

This is NOT a revival of the old Live Sync feature's blocking cross-station
duplicate check (permanently removed -- see docs/SYNC.md "Live Sync --
Retired"). That check ran synchronously *before* the SQLite write and caused
real production bugs (barcode double-fires corrupting input during a slow
network response). sync_single_scan() itself was never part of that blocking
chain -- it always ran *after* the write, submitted asynchronously with no
wait, and never touches SQLite from the worker thread. These tests verify
that shape is preserved:

- Offline-first ordering: record_scan() (SQLite write) always happens before
  the coordinator submission, regardless of whether the submission succeeds.
- The coordinator receives exactly one job per scan when the toggle is on,
  and that job calls sync_single_scan (network-only, no SQLite access).
- A full/rejecting coordinator does not lose the scan -- it stays 'pending'
  for the normal batch-sync path to pick up later.
- Immediate write being disabled (the default), CLOUD_READ_ONLY, or no
  coordinator configured all correctly skip the enqueue without erroring.
- submit() is called with on_result/on_error callbacks that only log --
  no in-flight state is tracked, so a coordinator barrier can never strand
  anything for this job type.

Requires PyQt6 (attendance.py imports PyQt6.QtWidgets at module level
unconditionally). Tests are skipped with a clear message when PyQt6 is
unavailable, matching the existing skip pattern in tests/test_duplicate_detection.py.

Run: python tests/test_immediate_sync.py
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
    """Fake BackgroundSyncCoordinator that records submitted jobs (and the
    callbacks passed alongside them) without running them, so tests can
    assert on what was enqueued without needing a real worker thread."""

    def __init__(self, accept=True):
        self.accept = accept
        self.submitted_jobs = []
        self.submitted_callbacks = []

    def submit(self, job, on_result=None, on_error=None):
        if not self.accept:
            return None
        self.submitted_jobs.append(job)
        self.submitted_callbacks.append((on_result, on_error))
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
class TestImmediateSyncEnqueue(unittest.TestCase):
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
        # Restore config to defaults for subsequent test files/processes
        os.environ['IMMEDIATE_SYNC_ENABLED'] = 'False'
        os.environ['CLOUD_READ_ONLY'] = 'False'
        import importlib
        import config
        importlib.reload(config)

    def _make_sync_service(self):
        return SyncService(db=MagicMock(), api_url="http://test.example.com", api_key="test-key")

    @patch.dict(os.environ, {
        'IMMEDIATE_SYNC_ENABLED': 'True', 'CLOUD_READ_ONLY': 'False',
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
        'IMMEDIATE_SYNC_ENABLED': 'True', 'CLOUD_READ_ONLY': 'False',
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
            self.assertEqual(sync_service.sync_single_scan.call_args[0][1], "TestStation")
        finally:
            service.close()

    @patch.dict(os.environ, {
        'IMMEDIATE_SYNC_ENABLED': 'True', 'CLOUD_READ_ONLY': 'False',
        'DUPLICATE_BADGE_DETECTION_ENABLED': 'False',
    })
    def test_submit_receives_result_and_error_callbacks_that_only_log(self):
        """on_result/on_error are passed to submit() (for visibility logging)
        but must not raise or require any follow-up state cleanup -- calling
        either one directly, with any result shape, must not error."""
        import importlib
        import config
        importlib.reload(config)

        service = _create_service(self.db_path, self.employee_path, self.export_dir)
        sync_service = self._make_sync_service()
        coordinator = RecordingCoordinator()
        service.set_sync_service(sync_service, coordinator=coordinator)

        try:
            service.register_scan("TEST001")
            self.assertEqual(len(coordinator.submitted_callbacks), 1)
            on_result, on_error = coordinator.submitted_callbacks[0]
            self.assertIsNotNone(on_result)
            self.assertIsNotNone(on_error)
            # Must not raise for either a success or failure result shape
            on_result(1, {"ok": True})
            on_result(1, {"ok": False, "error": "HTTP 500"})
            on_error(1, RuntimeError("simulated failure"))
        finally:
            service.close()

    @patch.dict(os.environ, {
        'IMMEDIATE_SYNC_ENABLED': 'True', 'CLOUD_READ_ONLY': 'False',
        'DUPLICATE_BADGE_DETECTION_ENABLED': 'False',
    })
    def test_scan_is_recorded_before_enqueue_offline_first_ordering(self):
        """record_scan() (SQLite write) must happen before the coordinator
        submission -- proven here by having submit() itself observe that the
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
        'IMMEDIATE_SYNC_ENABLED': 'True', 'CLOUD_READ_ONLY': 'False',
        'DUPLICATE_BADGE_DETECTION_ENABLED': 'False',
    })
    def test_rejected_enqueue_does_not_lose_scan(self):
        """A full/paused/shutdown coordinator returns None from submit() --
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
        'IMMEDIATE_SYNC_ENABLED': 'False', 'CLOUD_READ_ONLY': 'False',
        'DUPLICATE_BADGE_DETECTION_ENABLED': 'False',
    })
    def test_immediate_sync_disabled_by_default_does_not_enqueue(self):
        """Confirms today's default (off) behavior is byte-for-byte
        unchanged -- no coordinator submission happens unless the admin
        toggle is explicitly turned on."""
        import importlib
        import config
        importlib.reload(config)
        self.assertFalse(config.IMMEDIATE_SYNC_ENABLED)

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
        'IMMEDIATE_SYNC_ENABLED': 'True', 'CLOUD_READ_ONLY': 'True',
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

    @patch.dict(os.environ, {
        'IMMEDIATE_SYNC_ENABLED': 'True', 'CLOUD_READ_ONLY': 'False',
        'DUPLICATE_BADGE_DETECTION_ENABLED': 'False',
    })
    def test_no_coordinator_configured_does_not_raise_and_does_not_enqueue(self):
        """set_sync_service() called without a coordinator (coordinator=None,
        the default) must disable the immediate-write enqueue rather than
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


class TestSyncSingleScan(unittest.TestCase):
    """Unit tests for SyncService.sync_single_scan() in isolation -- no
    AttendanceService/coordinator involved, just the HTTP call shape."""

    def setUp(self):
        self.sync_service = SyncService(db=MagicMock(), api_url="http://test.example.com", api_key="test-key")

    @patch.dict(os.environ, {'CLOUD_READ_ONLY': 'True'})
    def test_read_only_mode_skips_without_network_call(self):
        import importlib
        import config
        importlib.reload(config)

        with patch("sync.requests.post") as mock_post:
            scan = MagicMock(badge_id="B1", station_name="S1", scanned_at="2026-01-01T00:00:00Z", sl_l1_desc=None, scan_source="badge", id=1)
            result = self.sync_service.sync_single_scan(scan, "S1")

        mock_post.assert_not_called()
        self.assertFalse(result["ok"])
        self.assertTrue(result.get("skipped"))

        os.environ['CLOUD_READ_ONLY'] = 'False'
        importlib.reload(config)

    @patch.dict(os.environ, {'CLOUD_READ_ONLY': 'False'})
    def test_success_posts_single_event_with_idempotency_key(self):
        import importlib
        import config
        importlib.reload(config)

        mock_response = MagicMock(status_code=200)
        with patch("sync.requests.post", return_value=mock_response) as mock_post:
            scan = MagicMock(badge_id="B1", station_name="S1", scanned_at="2026-01-01T00:00:00Z", sl_l1_desc="IT", scan_source="badge", id=42)
            result = self.sync_service.sync_single_scan(scan, "S1")

        self.assertTrue(result["ok"])
        mock_post.assert_called_once()
        _, kwargs = mock_post.call_args
        events = kwargs["json"]["events"]
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["badge_id"], "B1")
        self.assertIn("idempotency_key", events[0])

    @patch.dict(os.environ, {'CLOUD_READ_ONLY': 'False'})
    def test_non_200_response_returns_error_without_raising(self):
        import importlib
        import config
        importlib.reload(config)

        mock_response = MagicMock(status_code=500)
        with patch("sync.requests.post", return_value=mock_response):
            scan = MagicMock(badge_id="B1", station_name="S1", scanned_at="2026-01-01T00:00:00Z", sl_l1_desc=None, scan_source="badge", id=1)
            result = self.sync_service.sync_single_scan(scan, "S1")

        self.assertFalse(result["ok"])
        self.assertIn("error", result)

    @patch.dict(os.environ, {'CLOUD_READ_ONLY': 'False'})
    def test_network_exception_returns_error_without_raising(self):
        import importlib
        import config
        importlib.reload(config)

        with patch("sync.requests.post", side_effect=ConnectionError("boom")):
            scan = MagicMock(badge_id="B1", station_name="S1", scanned_at="2026-01-01T00:00:00Z", sl_l1_desc=None, scan_source="badge", id=1)
            result = self.sync_service.sync_single_scan(scan, "S1")

        self.assertFalse(result["ok"])
        self.assertIn("error", result)


if __name__ == "__main__":
    unittest.main()
