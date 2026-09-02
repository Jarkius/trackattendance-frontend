#!/usr/bin/env python3
"""Tests that admin_clear_station_data()/admin_clear_cloud_data() raise the
sync coordinator's barrier BEFORE calling the cloud delete, not after.

Regression coverage for a real race found during pre-event review: auto-sync
(always on) and Live Sync (when enabled) submit their batch/single-scan
uploads through the same shared BackgroundSyncCoordinator used here. If the
barrier were raised only after the cloud delete's own network round-trip (as
it originally was), a batch job already queued/in-flight during that
round-trip could land on the server afterward, resurrecting rows this call
just reported as cleared. Raising the barrier first closes that window down
to the same narrow "already dequeued and executing" edge case pause_barrier()
itself documents as unavoidable.

Requires PyQt6 (Api subclasses QObject). Skipped with a clear message when
PyQt6 is unavailable, matching the existing skip pattern in
tests/test_sync_now_async.py.

Run: python tests/test_admin_clear_barrier_ordering.py
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

from database import DatabaseManager

try:
    from PyQt6.QtCore import QObject  # noqa: F401
    PYQT6_AVAILABLE = True
except ImportError:
    PYQT6_AVAILABLE = False

if PYQT6_AVAILABLE:
    import config
    from main import Api


class _RecordingCoordinator:
    """Fake BackgroundSyncCoordinator that records when pause_barrier()/resume()
    are called relative to other mocked calls, via a shared call_order list."""

    def __init__(self, call_order):
        self._call_order = call_order

    def pause_barrier(self):
        self._call_order.append("pause_barrier")
        return 1

    def resume(self):
        self._call_order.append("resume")

    def submit(self, job, on_result=None, on_error=None):
        return None


def _make_api(call_order, sync_service):
    """Build a real Api instance wired to a recording coordinator + given sync_service."""
    service = MagicMock()
    service.export_scans.return_value = {"ok": True, "absolutePath": "/tmp/backup.xlsx"}
    service._db.clear_all_scans.side_effect = lambda: (
        call_order.append("clear_all_scans") or 0
    )
    service._db.get_station_name.return_value = "TestStation"
    service._db.set_meta.return_value = None
    service._db.count_scans_total.return_value = 0

    api = Api(
        service=service,
        quit_callback=lambda: None,
        sync_service=sync_service,
        sync_coordinator=_RecordingCoordinator(call_order),
    )
    return api


@unittest.skipUnless(PYQT6_AVAILABLE, "PyQt6 not installed in this environment")
class TestAdminClearBarrierOrdering(unittest.TestCase):
    def setUp(self):
        self._pin_patch = patch.object(config, "ADMIN_PIN", "1234")
        self._enabled_patch = patch.object(config, "ADMIN_FEATURES_ENABLED", True)
        self._pin_patch.start()
        self._enabled_patch.start()

    def tearDown(self):
        self._pin_patch.stop()
        self._enabled_patch.stop()

    def test_clear_cloud_data_pauses_barrier_before_cloud_delete(self):
        call_order = []
        sync_service = MagicMock()
        sync_service.clear_cloud_scans.side_effect = lambda: (
            call_order.append("clear_cloud_scans") or {"ok": True, "deleted": 0, "clear_epoch": ""}
        )
        sync_service.send_heartbeat.return_value = True

        api = _make_api(call_order, sync_service)
        result = api.admin_clear_cloud_data("1234")

        self.assertTrue(result["ok"])
        self.assertEqual(
            call_order,
            ["pause_barrier", "clear_cloud_scans", "clear_all_scans", "resume"],
        )

    def test_clear_station_data_pauses_barrier_before_cloud_delete(self):
        call_order = []
        sync_service = MagicMock()
        sync_service.clear_station_scans.side_effect = lambda station: (
            call_order.append("clear_station_scans") or {"ok": True, "deleted": 0}
        )

        api = _make_api(call_order, sync_service)
        result = api.admin_clear_station_data("1234")

        self.assertTrue(result["ok"])
        self.assertEqual(
            call_order,
            ["pause_barrier", "clear_station_scans", "clear_all_scans", "resume"],
        )

    def test_clear_cloud_data_resumes_barrier_when_cloud_delete_fails(self):
        call_order = []
        sync_service = MagicMock()
        sync_service.clear_cloud_scans.side_effect = lambda: (
            call_order.append("clear_cloud_scans") or {"ok": False, "message": "network error"}
        )

        api = _make_api(call_order, sync_service)
        result = api.admin_clear_cloud_data("1234")

        self.assertFalse(result["ok"])
        # Barrier must still be resumed on failure — otherwise every future
        # sync attempt at this station is permanently paused.
        self.assertEqual(call_order, ["pause_barrier", "clear_cloud_scans", "resume"])

    def test_clear_station_data_resumes_barrier_when_cloud_delete_fails(self):
        call_order = []
        sync_service = MagicMock()
        sync_service.clear_station_scans.side_effect = lambda station: (
            call_order.append("clear_station_scans") or {"ok": False, "message": "network error"}
        )

        api = _make_api(call_order, sync_service)
        result = api.admin_clear_station_data("1234")

        self.assertFalse(result["ok"])
        self.assertEqual(call_order, ["pause_barrier", "clear_station_scans", "resume"])

    def test_wrong_pin_never_touches_coordinator(self):
        call_order = []
        sync_service = MagicMock()
        api = _make_api(call_order, sync_service)

        result = api.admin_clear_cloud_data("0000")

        self.assertFalse(result["ok"])
        self.assertEqual(call_order, [])
        sync_service.clear_cloud_scans.assert_not_called()


if __name__ == "__main__":
    unittest.main()
