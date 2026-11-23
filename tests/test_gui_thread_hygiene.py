#!/usr/bin/env python3
"""Tests for GUI-thread hygiene (#111): single enumerate_cameras, camera probe
and backup-export workbook write routed through call_without_freezing_ui, the
bounded shutdown sync loop, and the indexed get_sync_statistics.

Run: python tests/test_gui_thread_hygiene.py
"""

import ast
import os
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

os.environ.setdefault("CLOUD_API_KEY", "test-api-key-for-testing")
os.environ.setdefault("CLOUD_API_URL", "http://test.example.com")

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from database import DatabaseManager

try:
    from PyQt6.QtCore import QObject  # noqa: F401
    PYQT6_AVAILABLE = True
except ImportError:
    PYQT6_AVAILABLE = False

if PYQT6_AVAILABLE:
    import main as main_module
    from main import Api, sync_pending_until_deadline


@unittest.skipUnless(PYQT6_AVAILABLE, "PyQt6 not available")
class TestEnumerateCameras(unittest.TestCase):
    def test_defined_exactly_once(self):
        tree = ast.parse((ROOT / "main.py").read_text(encoding="utf-8"))
        api = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "Api")
        defs = [n for n in api.body if isinstance(n, ast.FunctionDef) and n.name == "enumerate_cameras"]
        self.assertEqual(len(defs), 1)

    def test_probe_runs_through_call_without_freezing_ui(self):
        fake_cv2 = MagicMock()
        cap = MagicMock()
        cap.isOpened.return_value = False
        fake_cv2.VideoCapture.return_value = cap
        calls = []

        def recorder(fn):
            calls.append("wrapped")
            # Nothing must have been probed before the wrapper ran.
            self.assertEqual(fake_cv2.VideoCapture.call_count, 0)
            return fn()

        api = Api.__new__(Api)
        api._proximity_manager = None
        with patch.dict(sys.modules, {"cv2": fake_cv2}), \
                patch.object(main_module, "call_without_freezing_ui", recorder):
            result = Api.enumerate_cameras(api)
        self.assertEqual(calls, ["wrapped"])
        self.assertTrue(result["ok"])
        self.assertEqual(fake_cv2.VideoCapture.call_count, 11)


class _FakeDb:
    def __init__(self, n):
        self.pending = list(range(n))
        self.synced = []

    def fetch_pending_scans(self, limit):
        return list(self.pending[:limit])

    def get_station_name(self):
        return "S"

    def mark_scans_as_synced(self, ids):
        self.synced.extend(ids)
        done = set(ids)
        self.pending = [p for p in self.pending if p not in done]

    def mark_scans_as_failed(self, ids, msg):
        done = set(ids)
        self.pending = [p for p in self.pending if p not in done]


@unittest.skipUnless(PYQT6_AVAILABLE, "PyQt6 not available")
class TestShutdownSyncDeadline(unittest.TestCase):
    def _service(self, n):
        svc = MagicMock()
        svc.db = _FakeDb(n)
        svc.batch_size = 10
        svc.sync_scan_batch_network_only.side_effect = (
            lambda scans, station: {"synced_ids": list(scans), "failed_ids": []}
        )
        return svc

    def test_stops_when_deadline_passes_and_leaves_rest_pending(self):
        svc = self._service(100)
        ticks = iter([0, 1, 2, 3, 31, 40, 50, 60])  # start, then per-batch checks
        result = sync_pending_until_deadline(
            svc, 30, run_network_call=lambda fn: fn(), clock=lambda: next(ticks)
        )
        self.assertTrue(result["deadline_hit"])
        self.assertEqual(result["synced"], 30)  # checks at t=1,2,3 run a batch each; t=31 stops
        self.assertEqual(len(svc.db.pending), 100 - result["synced"])

    def test_completes_without_deadline(self):
        svc = self._service(25)
        result = sync_pending_until_deadline(
            svc, 30, run_network_call=lambda fn: fn(), clock=lambda: 0
        )
        self.assertFalse(result["deadline_hit"])
        self.assertEqual(result["synced"], 25)
        self.assertEqual(svc.db.pending, [])

    def test_no_progress_batch_stops_loop(self):
        svc = self._service(5)
        svc.sync_scan_batch_network_only.side_effect = lambda s, st: {"synced_ids": [], "failed_ids": []}
        result = sync_pending_until_deadline(
            svc, 30, run_network_call=lambda fn: fn(), clock=lambda: 0
        )
        self.assertEqual(result["synced"], 0)
        self.assertFalse(result["deadline_hit"])


class TestExportWorkbookOffThread(unittest.TestCase):
    def test_db_read_on_caller_thread_write_via_run_blocking(self):
        from attendance import AttendanceService
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            service = AttendanceService(
                database_path=d / "t.db",
                employee_workbook_path=d / "employee.xlsx",
                export_directory=d,
            )
            service._db.set_station_name("S")
            service._station_name = "S"
            try:
                service.register_scan("ABC123")
                main_thread = threading.get_ident()
                seen = {}
                real_fetch = service._db.fetch_all_scans

                def fetch():
                    seen["fetch_thread"] = threading.get_ident()
                    return real_fetch()

                service._db.fetch_all_scans = fetch

                def run_blocking(fn):
                    seen["wrapped"] = True
                    t = threading.Thread(target=fn)
                    t.start()
                    t.join()

                result = service.export_scans(run_blocking=run_blocking)
                self.assertTrue(result["ok"])
                self.assertTrue(seen["wrapped"])
                self.assertEqual(seen["fetch_thread"], main_thread)
                self.assertTrue(Path(result["absolutePath"]).exists())
            finally:
                service.close()


class TestSyncStatistics(unittest.TestCase):
    def test_counts_last_sync_and_index_use(self):
        with tempfile.TemporaryDirectory() as d:
            db = DatabaseManager(Path(d) / "t.db")
            try:
                empty = db.get_sync_statistics()
                self.assertEqual((empty["pending"], empty["synced"], empty["failed"]), (0, 0, 0))
                self.assertIsNone(empty["last_sync_time"])
                c = db._connection
                with c:
                    c.executemany(
                        "INSERT INTO scans(badge_id,scanned_at,station_name,sync_status,synced_at) VALUES(?,?,?,?,?)",
                        [("a", "t", "S", "pending", None), ("b", "t", "S", "synced", "2026-01-01"),
                         ("c", "t", "S", "synced", "2026-02-01"), ("d", "t", "S", "failed", None)],
                    )
                stats = db.get_sync_statistics()
                self.assertEqual((stats["pending"], stats["synced"], stats["failed"]), (1, 2, 1))
                self.assertEqual(stats["last_sync_time"], "2026-02-01")
                plan = " ".join(r[3] for r in c.execute(
                    "EXPLAIN QUERY PLAN SELECT sync_status, COUNT(*) FROM scans GROUP BY sync_status"))
                self.assertIn("idx_scans_sync_status", plan)
                plan = " ".join(r[3] for r in c.execute(
                    "EXPLAIN QUERY PLAN SELECT MAX(synced_at) FROM scans"))
                self.assertIn("idx_scans_synced_at", plan)
            finally:
                db.close()


if __name__ == "__main__":
    unittest.main()


class TestClearBackupExportStaysSynchronous(unittest.TestCase):
    """Backups taken right before a clear must not pump a nested event loop.

    If they did, submit_scan could run mid-clear and record a scan after the
    backup snapshot, which clear_all_scans() would then delete with no copy.
    """

    def test_no_backup_export_routed_through_nested_event_loop(self):
        source = (Path(__file__).resolve().parent.parent / "main.py").read_text(encoding="utf-8")
        self.assertNotIn("export_scans(run_blocking=call_without_freezing_ui)", source)
