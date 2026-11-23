#!/usr/bin/env python3
"""Regression tests for findings from the audit-fixes-2026-11 system review."""

import os
import sys
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("CLOUD_API_KEY", "test-api-key-for-testing")
os.environ.setdefault("CLOUD_API_URL", "http://test.example.com")

sys.path.insert(0, str(Path(__file__).parent.parent))

from openpyxl import Workbook, load_workbook  # noqa: E402

from excel_safety import neutralize_formulas  # noqa: E402
from dashboard import classify_export_scan  # noqa: E402


class TestNeutralizeFormulas(unittest.TestCase):
    def test_typed_formula_is_saved_as_text(self):
        wb = Workbook()
        ws = wb.active
        ws.append(["Somchai", '=HYPERLINK("http://example.invalid","x")', "=1+1"])
        self.assertEqual(neutralize_formulas(wb), 2)
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "out.xlsx"
            wb.save(path)
            reloaded = load_workbook(path).active
            values = [c.value for c in reloaded[1]]
            types = [c.data_type for c in reloaded[1]]
        self.assertEqual(values[2], "=1+1")
        self.assertNotIn("f", types)


class TestClassifyExportScan(unittest.TestCase):
    def test_cloud_matched_counts_as_registered_without_local_roster_row(self):
        self.assertEqual(classify_export_scan(False, "badge", cloud_matched=True), "registered")

    def test_missing_or_null_scan_source_is_manual(self):
        self.assertEqual(classify_export_scan(False, None), "walkin")
        self.assertEqual(classify_export_scan(False, ""), "walkin")

    def test_badge_source_unmatched_is_unknown(self):
        self.assertEqual(classify_export_scan(False, "badge"), "unknown")


try:
    import PyQt6  # noqa: F401
    HAVE_QT = True
except ImportError:
    HAVE_QT = False


@unittest.skipUnless(HAVE_QT, "PyQt6 not installed")
class TestNumericIdWarning(unittest.TestCase):
    """Warn only when a numeric Legacy ID could actually have lost leading zeros."""

    def _import(self, rows):
        from attendance import AttendanceService
        d = Path(tempfile.mkdtemp())
        wb = Workbook()
        ws = wb.active
        ws.append(["Legacy ID", "Full Name", "SL L1 Desc", "Position Desc"])
        for r in rows:
            ws.append(r)
        wb.save(d / "employee.xlsx")
        svc = AttendanceService(
            database_path=d / "db.db",
            employee_workbook_path=d / "employee.xlsx",
            export_directory=d / "exp",
        )
        return svc

    def test_same_width_numeric_ids_do_not_warn(self):
        svc = self._import([[101117, "A", "BU", "P"], [102345, "B", "BU", "P"]])
        self.assertFalse(svc._roster_warning)

    def test_local_export_stores_typed_formula_as_text(self):
        svc = self._import([["101117", "A", "BU", "P"]])
        svc._db.set_station_name("T")
        svc._station_name = "T"
        svc.register_scan("=1+1", scan_source="manual")
        result = svc.export_scans()
        self.assertTrue(result.get("ok"), result)
        sheet = load_workbook(result["absolutePath"]).active
        formula_cells = [c.coordinate for row in sheet.iter_rows() for c in row if c.data_type == "f"]
        self.assertEqual(formula_cells, [])

    def test_shorter_numeric_id_among_wider_ids_warns(self):
        svc = self._import([[123, "A", "BU", "P"], ["00456", "B", "BU", "P"]])
        self.assertTrue(svc._roster_warning)
        self.assertIn("1 numeric", svc._roster_warning)


if __name__ == "__main__":
    unittest.main()


# --- sync: bisection halts, deadline, error attribution (review findings A1/A3/A4/A7) ---

from unittest.mock import Mock, patch  # noqa: E402

os.environ["CLOUD_READ_ONLY"] = "False"
sys.path.insert(0, str(Path(__file__).parent))
from tests_support_sync import make_scan, mock_response, service_without_db  # noqa: E402,F401


@patch("sync.time.sleep")
class TestBisectionHalts(unittest.TestCase):
    def test_transient_failure_mid_split_stops_further_posts(self, _sleep):
        calls = []

        def post(url, json=None, **kwargs):
            calls.append(len(json["events"]))
            if len(calls) == 1:
                return mock_response(400)        # whole batch rejected -> split
            return mock_response(503)            # server falls over mid-split

        scans = [make_scan(i) for i in range(1, 9)]
        with patch("sync.requests.post", side_effect=post), \
                patch("config.SYNC_RETRY_ENABLED", False):
            result = service_without_db().sync_scan_batch_network_only(scans, "S")
        self.assertEqual(calls, [8, 4])          # the second half is never posted
        self.assertEqual(sorted(result["pending_ids"]), list(range(1, 9)))
        self.assertEqual(result["failed_ids"], [])

    def test_should_stop_leaves_remaining_parts_pending(self, _sleep):
        calls = []

        def post(url, json=None, **kwargs):
            calls.append(len(json["events"]))
            return mock_response(400)

        scans = [make_scan(i) for i in range(1, 9)]
        with patch("sync.requests.post", side_effect=post):
            result = service_without_db().sync_scan_batch_network_only(
                scans, "S", should_stop=lambda: len(calls) >= 1
            )
        self.assertEqual(calls, [8])
        self.assertEqual(sorted(result["pending_ids"]), list(range(1, 9)))

    def test_failed_rows_get_the_rejection_error(self, _sleep):
        def post(url, json=None, **kwargs):
            badges = [e["badge_id"] for e in json["events"]]
            if badges == ["B1"]:
                raise __import__("requests").exceptions.ChunkedEncodingError("cut")
            if "B2" in badges:
                return mock_response(422)
            return mock_response(200, {"saved": len(badges), "duplicates": 0})

        scans = [make_scan(2), make_scan(1)]
        with patch("sync.requests.post", side_effect=post):
            result = service_without_db().sync_scan_batch_network_only(scans, "S")
        self.assertEqual(result["failed_ids"], [2])
        self.assertTrue(result["error"].startswith("API error: 422"), result["error"])


class TestShutdownLoopStopsOnUnresolvedBatch(unittest.TestCase):
    @unittest.skipUnless(HAVE_QT, "PyQt6 not installed")
    def test_partial_pending_batch_is_not_reposted(self):
        from main import sync_pending_until_deadline

        class Db:
            pending = list(range(10))
            def fetch_pending_scans(self, limit): return list(self.pending[:limit])
            def get_station_name(self): return "S"
            def mark_scans_as_synced(self, ids): self.pending = [p for p in self.pending if p not in ids]
            def mark_scans_as_failed(self, ids, msg): self.pending = [p for p in self.pending if p not in ids]

        svc = Mock()
        svc.db = Db()
        svc.batch_size = 10
        svc.sync_scan_batch_network_only.side_effect = lambda scans, st, should_stop=None: {
            "synced_ids": scans[:5], "failed_ids": [], "pending_ids": scans[5:], "error": "API error: 503",
        }
        result = sync_pending_until_deadline(svc, 30, run_network_call=lambda fn: fn(), clock=lambda: 0)
        self.assertEqual(svc.sync_scan_batch_network_only.call_count, 1)
        self.assertEqual(result["synced"], 5)


# --- reporting joins must be index probes, not scans x employees (review finding A2) ---

class TestReportingJoinsUseIndex(unittest.TestCase):
    def test_employee_probe_is_an_index_search(self):
        from database import DatabaseManager
        db = DatabaseManager(Path(tempfile.mkdtemp()) / "db.db")
        queries = [
            "SELECT e.sl_l1_desc, COUNT(DISTINCT e.legacy_id) FROM scans s CROSS JOIN employees e "
            "ON e.legacy_id = COALESCE(s.legacy_id, s.badge_id) COLLATE NOCASE GROUP BY e.sl_l1_desc",
            "SELECT COUNT(DISTINCT UPPER(s.badge_id)) FROM scans s LEFT JOIN employees e "
            "ON e.legacy_id = COALESCE(s.legacy_id, s.badge_id) COLLATE NOCASE WHERE e.legacy_id IS NULL",
        ]
        for sql in queries:
            plan = " | ".join(r[-1] for r in db._connection.execute("EXPLAIN QUERY PLAN " + sql))
            self.assertIn("SEARCH e USING", plan, plan)
