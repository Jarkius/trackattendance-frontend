#!/usr/bin/env python3
"""
Tests for DashboardService in dashboard.py.

Tests the dashboard data fetching, error handling, and export functionality.

Run: python tests/test_dashboard.py
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

# Set required environment variables BEFORE importing config
os.environ.setdefault("CLOUD_API_KEY", "test-api-key-for-testing")
os.environ.setdefault("CLOUD_API_URL", "http://test.example.com")

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from database import DatabaseManager, EmployeeRecord
from dashboard import DashboardService


class TestDashboardDataFetching(unittest.TestCase):
    """Test get_dashboard_data() method."""

    def setUp(self):
        """Set up test database and dashboard service."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test.db"
        self.db = DatabaseManager(self.db_path)
        self.db.set_station_name("TestStation")

        # Add test employees
        self.db.bulk_insert_employees([
            EmployeeRecord("TEST001", "Alice Smith", "IT", "Engineer"),
            EmployeeRecord("TEST002", "Bob Jones", "HR", "Manager"),
            EmployeeRecord("TEST003", "Carol White", "IT", "Developer"),
        ])

        self.export_dir = Path(self.temp_dir) / "exports"
        self.service = DashboardService(
            self.db,
            "http://test.example.com",
            "test-api-key",
            self.export_dir
        )

    def tearDown(self):
        """Clean up."""
        self.db.close()
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @patch('dashboard.requests.get')
    def test_successful_data_fetch(self, mock_get):
        """Test successful dashboard data fetch."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "total_scans": 100,
            "unique_badges": 50,
            "matched_unique": 50,
            "walkin_unique": 0,
            "unknown_badge_unique": 0,
            "stations": [
                {"name": "Station1", "scans": 60, "unique": 30, "last_scan": "2024-01-01T10:30:00Z"},
                {"name": "Station2", "scans": 40, "unique": 20, "last_scan": "2024-01-01T11:00:00Z"},
            ]
        }
        mock_get.return_value = mock_response

        result = self.service.get_dashboard_data()

        self.assertEqual(result["registered"], 3)
        self.assertEqual(result["total_scans"], 100)
        self.assertEqual(result["scanned"], 50)
        self.assertEqual(len(result["stations"]), 2)
        self.assertIsNone(result["error"])

    def test_local_snapshot_returns_registered_count_with_no_network_call(self):
        """get_local_snapshot() must return the registered count instantly,
        without touching requests.get at all -- it's meant to populate the
        dashboard the moment it opens, ahead of the cloud fetch."""
        with patch('dashboard.requests.get') as mock_get:
            result = self.service.get_local_snapshot()
            mock_get.assert_not_called()
        self.assertEqual(result["registered"], 3)
        self.assertIsNone(result["error"])
        self.assertIn("last_updated", result)

    def test_local_snapshot_reports_error_on_db_failure(self):
        """A SQLite failure must be caught and reported, not raised --
        get_local_snapshot() runs before/independently of the cloud fetch
        and shouldn't be able to crash the dashboard open."""
        broken_db = Mock()
        broken_db.count_employees.side_effect = Exception("db exploded")
        service = DashboardService(broken_db, "http://test.example.com", "test-api-key")

        result = service.get_local_snapshot()

        self.assertEqual(result["registered"], 0)
        self.assertIn("db exploded", result["error"])

    @patch('dashboard.requests.get')
    def test_api_connection_error(self, mock_get):
        """Test handling of connection error."""
        import requests
        mock_get.side_effect = requests.exceptions.ConnectionError()

        result = self.service.get_dashboard_data()

        self.assertEqual(result["error"], "Cannot connect to cloud API")
        self.assertEqual(result["registered"], 3)  # Local data still works

    @patch('dashboard.requests.get')
    def test_api_timeout(self, mock_get):
        """Test handling of timeout."""
        import requests
        mock_get.side_effect = requests.exceptions.Timeout()

        result = self.service.get_dashboard_data()

        self.assertEqual(result["error"], "Cloud API timeout")

    @patch('dashboard.requests.get')
    def test_api_401_unauthorized(self, mock_get):
        """Test handling of 401 unauthorized."""
        mock_response = Mock()
        mock_response.status_code = 401
        mock_get.return_value = mock_response

        result = self.service.get_dashboard_data()

        self.assertEqual(result["error"], "Authentication failed - check API key")

    @patch('dashboard.requests.get')
    def test_api_503_unavailable(self, mock_get):
        """Test handling of 503 service unavailable."""
        mock_response = Mock()
        mock_response.status_code = 503
        mock_get.return_value = mock_response

        result = self.service.get_dashboard_data()

        self.assertEqual(result["error"], "Cloud database unavailable")

    @patch('dashboard.requests.get')
    def test_attendance_rate_calculation(self, mock_get):
        """Test attendance rate is calculated correctly."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "total_scans": 10,
            "unique_badges": 2,
            "matched_unique": 2,
            "walkin_unique": 0,
            "unknown_badge_unique": 0,
            "stations": []
        }
        mock_get.return_value = mock_response

        result = self.service.get_dashboard_data()

        # 2 out of 3 employees = 66.7%
        self.assertAlmostEqual(result["attendance_rate"], 66.7, places=1)

    @patch('dashboard.requests.get')
    def test_zero_registered_no_division_error(self, mock_get):
        """Test no division by zero when no employees registered."""
        # Clear employees
        self.db._connection.execute("DELETE FROM employees")
        self.db._connection.commit()

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "total_scans": 5,
            "unique_badges": 3,
            "stations": []
        }
        mock_get.return_value = mock_response

        result = self.service.get_dashboard_data()

        self.assertEqual(result["attendance_rate"], 0.0)
        self.assertEqual(result["registered"], 0)


def _stats_response(payload):
    response = Mock()
    response.status_code = 200
    response.json.return_value = payload
    return response


class TestAttendanceBuckets(unittest.TestCase):
    """#109: rate = registered attended / registered; walk-ins and unknown
    badge scans are reported separately and never inflate the rate."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db = DatabaseManager(Path(self.temp_dir) / "test.db")
        self.db.set_station_name("TestStation")
        self.employees = [
            EmployeeRecord(f"E{i:03d}", f"Emp {i}", "IT" if i % 2 else "HR", "Staff")
            for i in range(10)
        ]
        self.db.bulk_insert_employees(self.employees)
        self.service = DashboardService(self.db, "http://test.example.com", "k")

    def tearDown(self):
        self.db.close()
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _record_ten_matched_two_walkins_one_garbled(self):
        for emp in self.employees:
            self.db.record_scan(emp.legacy_id, "TestStation", emp, scan_source="badge")
        self.db.record_scan("Somchai", "TestStation", None, scan_source="manual")
        self.db.record_scan("somchai ", "TestStation", None, scan_source="manual")
        self.db.record_scan("Malee  Sook", "TestStation", None, scan_source="manual")
        self.db.record_scan("#GARBLED", "TestStation", None, scan_source="badge")

    @patch('dashboard.requests.get')
    def test_cloud_fields_used(self, mock_get):
        mock_get.return_value = _stats_response({
            "total_scans": 40, "unique_badges": 13,
            "matched_unique": 10, "walkin_unique": 2, "unknown_badge_unique": 1,
            "stations": [], "business_units": [],
        })
        result = self.service.get_dashboard_data()
        self.assertEqual(result["scanned"], 10)
        self.assertEqual(result["attendance_rate"], 100.0)
        self.assertEqual(result["walkins"], 2)
        self.assertEqual(result["unknown_badges"], 1)
        self.assertEqual(result["total_present"], 12)
        self.assertEqual(result["source"], "cloud")

    @patch('dashboard.requests.get')
    def test_old_server_falls_back_to_bu_sum(self, mock_get):
        mock_get.return_value = _stats_response({
            "total_scans": 40, "unique_badges": 13,
            "stations": [],
            "business_units": [
                {"name": "IT", "registered": 5, "unique": 5},
                {"name": "HR", "registered": 5, "unique": 5},
                {"name": "Unmatched", "registered": 0, "unique": 3},
            ],
        })
        result = self.service.get_dashboard_data()
        self.assertEqual(result["scanned"], 10)
        self.assertEqual(result["attendance_rate"], 100.0)
        self.assertIsNone(result["walkins"])
        self.assertIsNone(result["unknown_badges"])
        self.assertEqual(result["total_present"], 10)

    @patch('dashboard.requests.get')
    def test_old_server_without_business_units_does_not_crash(self, mock_get):
        mock_get.return_value = _stats_response({"total_scans": 5, "unique_badges": 5})
        result = self.service.get_dashboard_data()
        self.assertEqual(result["scanned"], 0)
        self.assertIsNone(result["walkins"])

    @patch('dashboard.requests.get')
    def test_rate_capped_at_100_with_warning(self, mock_get):
        mock_get.return_value = _stats_response({
            "total_scans": 50, "matched_unique": 12, "walkin_unique": 0,
            "unknown_badge_unique": 0, "stations": [], "business_units": [],
        })
        with self.assertLogs('dashboard', level='WARNING') as logs:
            result = self.service.get_dashboard_data()
        self.assertEqual(result["attendance_rate"], 100.0)
        self.assertTrue(any("capping" in m for m in logs.output))

    @patch('dashboard.requests.get')
    def test_local_fallback_when_cloud_unavailable(self, mock_get):
        import requests
        mock_get.side_effect = requests.exceptions.ConnectionError()
        self._record_ten_matched_two_walkins_one_garbled()

        result = self.service.get_dashboard_data()

        self.assertEqual(result["scanned"], 10)
        self.assertEqual(result["attendance_rate"], 100.0)
        self.assertEqual(result["walkins"], 2)  # Somchai/"somchai " collapse; Malee Sook
        self.assertEqual(result["source"], "local")  # UI labels it "This station only"
        self.assertEqual(result["unknown_badges"], 1)
        self.assertEqual(result["total_present"], 12)

    def test_local_buckets_badge_and_lookup_same_person_once(self):
        emp = self.employees[0]
        self.db.record_scan("105193T", "TestStation", emp, scan_source="badge")
        self.db.record_scan(emp.legacy_id.lower(), "TestStation", emp, scan_source="manual")
        buckets = self.db.get_attendance_buckets()
        self.assertEqual(buckets["registered_attended"], 1)

    def test_local_walkin_dedupe_case_and_spaces(self):
        self.db.record_scan("Somchai", "TestStation", None, scan_source="manual")
        self.db.record_scan("somchai ", "TestStation", None, scan_source="manual")
        self.db.record_scan("SOMCHAI", "TestStation", None, scan_source="manual")
        self.assertEqual(self.db.get_attendance_buckets()["walkins"], 1)


class TestDashboardRunNetworkCallInjection(unittest.TestCase):
    """Regression test for the v2.1.1 freeze-fix bug: wrapping the entire
    get_dashboard_data()/export_to_excel() call in a worker-thread runner
    (as main.py's Api slots did before this fix) breaks the local SQLite
    reads inside those methods, since SQLite connections are thread-affine.
    The fix injects run_network_call so ONLY the requests.get() calls run
    through it — SQLite reads always stay on the calling thread."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test.db"
        self.db = DatabaseManager(self.db_path)
        self.db.set_station_name("TestStation")
        self.db.bulk_insert_employees([
            EmployeeRecord("TEST001", "Alice Smith", "IT", "Engineer"),
        ])

    def tearDown(self):
        self.db.close()
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @patch('dashboard.requests.get')
    def test_only_network_call_goes_through_run_network_call(self, mock_get):
        """run_network_call must be invoked exactly once (for the HTTP call)
        and never wrap the SQLite reads — proven by making run_network_call
        itself raise if handed anything other than the expected request."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"total_scans": 1, "unique_badges": 1, "stations": []}
        mock_get.return_value = mock_response

        calls = []

        def tracking_runner(fn):
            calls.append(fn)
            return fn()

        service = DashboardService(
            self.db, "http://test.example.com", "test-key",
            run_network_call=tracking_runner,
        )
        result = service.get_dashboard_data()

        self.assertEqual(len(calls), 1, "run_network_call should wrap exactly one call (the HTTP request)")
        self.assertEqual(result["registered"], 1, "SQLite read (count_employees) must succeed regardless of run_network_call")

    @patch('dashboard.requests.get')
    def test_default_run_network_call_is_synchronous_passthrough(self, mock_get):
        """No run_network_call supplied (the tests-without-PyQt6 case, and
        the pre-v2.1.1 behavior) must still work exactly as before."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"total_scans": 1, "unique_badges": 1, "stations": []}
        mock_get.return_value = mock_response

        service = DashboardService(self.db, "http://test.example.com", "test-key")
        result = service.get_dashboard_data()

        self.assertEqual(result["registered"], 1)
        self.assertIsNone(result["error"])


class TestDashboardFormatTime(unittest.TestCase):
    """Test _format_time() helper method."""

    def setUp(self):
        """Set up test service."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test.db"
        self.db = DatabaseManager(self.db_path)

        self.service = DashboardService(
            self.db,
            "http://test.example.com",
            "test-api-key"
        )

    def tearDown(self):
        """Clean up."""
        self.db.close()
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_format_valid_iso_timestamp(self):
        """Test formatting valid ISO timestamp."""
        result = self.service._format_time("2024-01-15T10:30:45Z")
        # Should return HH:MM:SS format in local timezone
        self.assertRegex(result, r'^\d{2}:\d{2}:\d{2}$')

    def test_format_none_returns_dash(self):
        """Test None timestamp returns '--'."""
        result = self.service._format_time(None)
        self.assertEqual(result, "--")

    def test_format_empty_string_returns_dash(self):
        """Test empty string returns '--'."""
        result = self.service._format_time("")
        self.assertEqual(result, "--")

    def test_format_invalid_timestamp_returns_dash(self):
        """Test invalid timestamp returns '--'."""
        result = self.service._format_time("not-a-timestamp")
        self.assertEqual(result, "--")


class TestDashboardBusinessUnits(unittest.TestCase):
    """Test BU breakdown functionality."""

    def setUp(self):
        """Set up test database with BU data."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test.db"
        self.db = DatabaseManager(self.db_path)
        self.db.set_station_name("TestStation")

        # Add employees in different BUs
        self.db.bulk_insert_employees([
            EmployeeRecord("IT001", "Alice", "IT", "Engineer"),
            EmployeeRecord("IT002", "Bob", "IT", "Developer"),
            EmployeeRecord("HR001", "Carol", "HR", "Manager"),
        ])

        # Record scans
        self.db.record_scan("IT001", "TestStation",
                           EmployeeRecord("IT001", "Alice", "IT", "Engineer"))

        self.service = DashboardService(
            self.db,
            "http://test.example.com",
            "test-api-key"
        )

    def tearDown(self):
        """Clean up."""
        self.db.close()
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @patch('dashboard.requests.get')
    def test_bu_breakdown_included(self, mock_get):
        """Test BU breakdown is included in dashboard data."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "total_scans": 1,
            "unique_badges": 1,
            "stations": []
        }
        mock_get.return_value = mock_response

        result = self.service.get_dashboard_data()

        self.assertIn("business_units", result)
        self.assertIsInstance(result["business_units"], list)

    @patch('dashboard.requests.get')
    def test_unmatched_badges_counted(self, mock_get):
        """Test unmatched badges are counted separately."""
        # Record unmatched scan
        self.db.record_scan("UNKNOWN001", "TestStation", None)

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "total_scans": 2,
            "unique_badges": 2,
            "stations": []
        }
        mock_get.return_value = mock_response

        result = self.service.get_dashboard_data()

        # Should have "(Unmatched)" entry
        unmatched = next(
            (bu for bu in result["business_units"] if bu["bu_name"] == "(Unmatched)"),
            None
        )
        self.assertIsNotNone(unmatched)
        self.assertEqual(unmatched["scanned"], 1)


class TestDashboardExport(unittest.TestCase):
    """Test export_to_excel() method."""

    def setUp(self):
        """Set up test database and service."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test.db"
        self.db = DatabaseManager(self.db_path)
        self.db.set_station_name("TestStation")

        self.db.bulk_insert_employees([
            EmployeeRecord("TEST001", "Alice", "IT", "Engineer"),
            EmployeeRecord("TEST002", "Bob", "Sales", "Associate"),
        ])

        self.export_dir = Path(self.temp_dir) / "exports"
        self.service = DashboardService(
            self.db,
            "http://test.example.com",
            "test-api-key",
            self.export_dir
        )

    def tearDown(self):
        """Clean up."""
        self.db.close()
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @patch('dashboard.requests.get')
    def test_not_yet_scanned_uses_legacy_id_not_badge_id(self, mock_get):
        """Regression: an employee scanned via a badge_id that differs from
        their actual legacy_id (manual lookup, or a reprinted-badge suffix)
        must NOT show up on the "Not Yet Scanned" sheet -- they scanned, just
        under a badge_id that isn't their legacy_id. The bug compared
        emp.legacy_id against a set of raw badge_ids instead of legacy_ids."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "scans": [
                {
                    "badge_id": "105193T",  # raw scanned value != legacy_id
                    "legacy_id": "TEST001",  # employee's actual ID
                    "station_name": "TestStation",
                    "scanned_at": "2026-01-01T08:00:00Z",
                    "matched": True,
                    "scan_source": "badge",
                },
            ],
        }
        mock_get.return_value = mock_response

        result = self.service.export_to_excel()
        self.assertTrue(result["ok"], result.get("message"))

        from openpyxl import load_workbook
        wb = load_workbook(result["file_path"])
        ws = wb["Not Yet Scanned"]
        not_scanned_ids = [row[0] for row in ws.iter_rows(min_row=2, max_row=ws.max_row - 1, values_only=True)]
        self.assertNotIn("TEST001", not_scanned_ids)

    @patch('dashboard.requests.get')
    def test_unique_sheets_exclude_unmatched_scans(self, mock_get):
        """A scan with no legacy_id match (garbled/unrecognized badge) must
        not appear in the dedup sheet at all -- it's not a real attendee."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "scans": [
                {
                    "badge_id": "GARBLED123", "legacy_id": None,
                    "station_name": "StationA", "scanned_at": "2026-01-01T08:00:00Z",
                    "matched": False, "scan_source": "badge",
                },
            ],
        }
        mock_get.return_value = mock_response

        result = self.service.export_to_excel()
        self.assertTrue(result["ok"], result.get("message"))

        from openpyxl import load_workbook
        wb = load_workbook(result["file_path"])
        self.assertNotIn("Deduplicated Attendance", wb.sheetnames)
        for name in ("Unique Scans (Per Day)", "Lucky Draw"):
            ws = wb[name]
            data_rows = [
                row for row in ws.iter_rows(min_row=2, max_row=ws.max_row, values_only=True)
                if row[0] and not str(row[0]).endswith(":")
            ]
            self.assertEqual(len(data_rows), 0, name)

    @patch('dashboard.requests.get')
    def test_career_level_unique_per_day_and_lucky_draw_sheets(self, mock_get):
        """Career Level flows into the report; "Unique Scans (Per Day)" keeps
        each employee's first scan per day; "Lucky Draw" is one row per
        rostered attendee, no Email, excluding Partner (9) and Intern (0).
        Raw duplicates stay in "All Scans"."""
        self.db.clear_employees()
        self.db.bulk_insert_employees([
            EmployeeRecord("E5", "Alice", "IT", "Manager", "a@x.com", "5"),
            EmployeeRecord("E9", "Pat", "IT", "Partner", "p@x.com", "9"),
            EmployeeRecord("E0", "Ivy", "IT", "Intern", "i@x.com", "0"),
        ])

        def scan(lid, station, ts):
            return {"badge_id": lid, "legacy_id": lid, "station_name": station,
                    "scanned_at": ts, "matched": True, "scan_source": "badge"}

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"scans": [
            scan("E5", "A", "2026-01-01T03:00:00Z"),
            scan("E5", "B", "2026-01-01T04:00:00Z"),   # same day, other station
            scan("E5", "A", "2026-01-02T03:00:00Z"),   # next day
            scan("E9", "A", "2026-01-01T03:00:00Z"),
            scan("E0", "A", "2026-01-01T03:00:00Z"),
        ]}
        mock_get.return_value = mock_response

        result = self.service.export_to_excel()
        self.assertTrue(result["ok"], result.get("message"))

        from openpyxl import load_workbook
        wb = load_workbook(result["file_path"])

        def data(name, key):
            ws = wb[name]
            h = [c.value for c in ws[1]]
            rows = [dict(zip(h, r)) for r in ws.iter_rows(min_row=2, values_only=True)
                    if r[h.index(key)] and not str(r[h.index(key)]).endswith(":")]
            return h, rows

        h, raw = data("All Scans", "Legacy ID")
        self.assertEqual(len(raw), 5)  # raw duplicates preserved
        self.assertIn("Career Level", h)

        _, per_day = data("Unique Scans (Per Day)", "Date")
        e5 = [r for r in per_day if r["Legacy ID"] == "E5"]
        self.assertEqual(len(e5), 2)  # one per day
        self.assertEqual(len(per_day), 4)

        h, draw = data("Lucky Draw", "Legacy ID")
        self.assertEqual([r["Legacy ID"] for r in draw], ["E5"])
        self.assertNotIn("Email", h)
        self.assertEqual(draw[0]["Career Level"], "5")

    def _export_sheets(self, scans):
        with patch('dashboard.requests.get') as mock_get:
            mock_get.return_value = _stats_response({"scans": scans})
            result = self.service.export_to_excel(dashboard_data={
                "registered": 2, "scanned": 0, "total_scans": len(scans),
                "attendance_rate": 0.0, "stations": [], "business_units": [],
            })
        self.assertTrue(result["ok"], result.get("message"))
        from openpyxl import load_workbook
        return load_workbook(result["file_path"])

    @staticmethod
    def _scan(badge, legacy, source, matched, at="2026-01-01T08:00:00Z", station="StationA"):
        return {"badge_id": badge, "legacy_id": legacy, "station_name": station,
                "scanned_at": at, "matched": matched, "scan_source": source}

    def test_export_buckets_agree_across_sheets(self):
        """Badge + lookup of TEST001 = 1 person on Summary, BU and Unique Scans;
        walk-ins ("Somchai"/"somchai ") = 1 and are not in Not Yet Scanned;
        the garbled badge is unknown, not a person."""
        wb = self._export_sheets([
            self._scan("105193T", "TEST001", "badge", True),
            self._scan("test001", "test001", "manual", True, at="2026-01-01T08:10:00Z", station="StationB"),
            self._scan("Somchai", None, "manual", False, at="2026-01-01T09:00:00Z"),
            self._scan("somchai ", None, "manual", False, at="2026-01-01T09:05:00Z", station="StationB"),
            self._scan("#GARBLED", None, "badge", False),
        ])

        summary = {r[0]: r[1] for r in wb["Summary"].iter_rows(min_row=2, values_only=True)}
        self.assertEqual(summary["Registered Attended"], 1)
        self.assertEqual(summary["Walk-ins"], 1)
        self.assertEqual(summary["Unknown Badge Scans (needs review)"], 1)
        self.assertEqual(summary["Total Present"], 2)
        self.assertEqual(summary["Attendance Rate"], "50.0%")

        bu = {r[0]: r for r in wb["By Business Unit"].iter_rows(min_row=2, values_only=True)}
        self.assertEqual(bu["IT"][2], 1)
        self.assertEqual(sum(r[2] for n, r in bu.items() if n != "(Unmatched)"), 1)
        self.assertEqual(bu["(Unmatched)"][2], 1)

        ws = wb["Unique Scans (Per Day)"]
        ids = [r[1] for r in ws.iter_rows(min_row=2, values_only=True)
               if r[0] not in (None, "Unique Employee-Days:")]
        self.assertEqual(ids, ["TEST001"])

        not_scanned = list(wb["Not Yet Scanned"].iter_rows(min_row=2, values_only=True))
        self.assertNotIn("TEST001", [r[0] for r in not_scanned])
        self.assertIn("TEST002", [r[0] for r in not_scanned])
        self.assertNotIn("Somchai", [r[1] for r in not_scanned])

        walk = list(wb["Walk-ins"].iter_rows(min_row=2, values_only=True))
        self.assertEqual(len(walk), 1)
        self.assertEqual(walk[0][0], "Somchai")  # as typed, earliest scan
        self.assertEqual(walk[0][1], "StationA")

    def test_export_rate_never_exceeds_100(self):
        wb = self._export_sheets([
            self._scan("TEST001", "TEST001", "badge", True),
            self._scan("TEST002", "TEST002", "badge", True),
            self._scan("Walk In", None, "manual", False),
            self._scan("BAD1", None, "badge", False),
        ])
        summary = {r[0]: r[1] for r in wb["Summary"].iter_rows(min_row=2, values_only=True)}
        self.assertEqual(summary["Attendance Rate"], "100.0%")
        self.assertEqual(summary["Total Present"], 3)

    @patch('dashboard.requests.get')
    def test_export_connection_error(self, mock_get):
        """Test export handles connection error."""
        import requests
        mock_get.side_effect = requests.exceptions.ConnectionError()

        result = self.service.export_to_excel()

        self.assertFalse(result["ok"])
        self.assertEqual(result["message"], "Cannot connect to cloud API")

    @patch('dashboard.requests.get')
    def test_export_timeout(self, mock_get):
        """Test export handles timeout."""
        import requests
        mock_get.side_effect = requests.exceptions.Timeout()

        result = self.service.export_to_excel()

        self.assertFalse(result["ok"])
        self.assertEqual(result["message"], "Cloud API timeout")

    @patch('dashboard.requests.get')
    def test_export_no_data(self, mock_get):
        """Test export handles no data case."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"scans": []}
        mock_get.return_value = mock_response

        result = self.service.export_to_excel()

        self.assertFalse(result["ok"])
        self.assertEqual(result["message"], "No scan data to export")
        self.assertTrue(result.get("noData", False))

    def _export_with_total(self, mock_get, total):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "total_records": total,
            "scans": [{
                "badge_id": "TEST001", "legacy_id": "TEST001",
                "station_name": "TestStation",
                "scanned_at": "2026-01-01T08:00:00Z",
                "matched": True, "scan_source": "badge",
            }],
        }
        mock_get.return_value = mock_response
        return self.service.export_to_excel()

    @patch('dashboard.requests.get')
    def test_export_warns_when_possibly_truncated(self, mock_get):
        """total_records at the server's 100000 cap logs a truncation warning."""
        with self.assertLogs('dashboard', level='WARNING') as cm:
            self._export_with_total(mock_get, 100000)
        self.assertTrue(any("truncated" in m for m in cm.output))

    @patch('dashboard.requests.get')
    def test_export_no_truncation_warning_below_cap(self, mock_get):
        """total_records just below the cap logs no truncation warning."""
        with self.assertLogs('dashboard', level='WARNING') as cm:
            import logging
            logging.getLogger('dashboard').warning("sentinel")
            self._export_with_total(mock_get, 99999)
        self.assertFalse(any("truncated" in m for m in cm.output))

    @patch('dashboard.requests.get')
    def test_export_api_error(self, mock_get):
        """Test export handles API error status."""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_get.return_value = mock_response

        result = self.service.export_to_excel()

        self.assertFalse(result["ok"])
        self.assertIn("API error: 500", result["message"])


class TestDashboardHeaders(unittest.TestCase):
    """Test HTTP header generation."""

    def setUp(self):
        """Set up test service."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test.db"
        self.db = DatabaseManager(self.db_path)

        self.service = DashboardService(
            self.db,
            "http://test.example.com",
            "my-secret-api-key"
        )

    def tearDown(self):
        """Clean up."""
        self.db.close()
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_authorization_header(self):
        """Test Bearer token is included in headers."""
        headers = self.service._get_headers()

        self.assertIn("Authorization", headers)
        self.assertEqual(headers["Authorization"], "Bearer my-secret-api-key")

    def test_content_type_header(self):
        """Test Content-Type is set to JSON."""
        headers = self.service._get_headers()

        self.assertIn("Content-Type", headers)
        self.assertEqual(headers["Content-Type"], "application/json")


def main():
    """Run tests with summary."""
    print("=" * 70)
    print("DASHBOARD SERVICE TESTS")
    print("=" * 70)
    print()

    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    suite.addTests(loader.loadTestsFromTestCase(TestDashboardDataFetching))
    suite.addTests(loader.loadTestsFromTestCase(TestDashboardRunNetworkCallInjection))
    suite.addTests(loader.loadTestsFromTestCase(TestDashboardFormatTime))
    suite.addTests(loader.loadTestsFromTestCase(TestDashboardBusinessUnits))
    suite.addTests(loader.loadTestsFromTestCase(TestDashboardExport))
    suite.addTests(loader.loadTestsFromTestCase(TestDashboardHeaders))

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
