#!/usr/bin/env python3
"""Regression tests for #106: one badge/Legacy ID normalisation rule.

Run: python -m pytest tests/test_badge_id_normalisation.py
"""

import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("CLOUD_API_KEY", "test-api-key-for-testing")
os.environ.setdefault("CLOUD_API_URL", "http://test.example.com")

sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from openpyxl import Workbook
    import PyQt6  # noqa: F401  (attendance.py needs it)
    AVAILABLE = True
except ImportError:
    AVAILABLE = False

if AVAILABLE:
    # Not guarded: if these break, the tests must fail, not silently skip.
    from attendance import AttendanceService
    from database import normalize_badge_id

HEADERS = ["Legacy ID", "Full Name", "SL L1 Desc", "Position Desc"]


@unittest.skipUnless(AVAILABLE, "PyQt6/openpyxl not installed")
class TestNormalizeBadgeId(unittest.TestCase):
    def test_strips_whitespace_nbsp_zero_width_and_uppercases(self):
        self.assertEqual(normalize_badge_id(" 12345a "), "12345A")
        self.assertEqual(normalize_badge_id("​12345a﻿"), "12345A")
        self.assertEqual(normalize_badge_id(None), "")


@unittest.skipUnless(AVAILABLE, "PyQt6/openpyxl not installed")
class TestBadgeIdNormalisation(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test.db"
        self.workbook_path = Path(self.temp_dir) / "employee.xlsx"
        self.export_dir = Path(self.temp_dir) / "exports"
        self.services = []

    def tearDown(self):
        for svc in self.services:
            try:
                svc.close()
            except Exception:
                pass
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _write(self, rows, number_format=None):
        wb = Workbook()
        ws = wb.active
        ws.append(HEADERS)
        for row in rows:
            ws.append(row)
            if number_format and isinstance(row[0], (int, float)):
                ws.cell(row=ws.max_row, column=1).number_format = number_format
        wb.save(self.workbook_path)
        wb.close()

    def _service(self):
        svc = AttendanceService(
            database_path=self.db_path,
            employee_workbook_path=self.workbook_path,
            export_directory=self.export_dir,
        )
        self.services.append(svc)
        svc._db.set_station_name("T")
        svc._station_name = "T"
        return svc

    def test_case_insensitive_match_and_employee_duplicate_check(self):
        self._write([["12345A", "Alice", "BU1", "P"]])
        svc = self._service()
        first = svc.register_scan("Alice", scan_source="lookup", lookup_legacy_id="12345a")
        self.assertEqual(first.get("fullName"), "Alice", first)
        # Different raw badge_id than the stored scan, so only the
        # employee-level check can flag this one.
        second = svc.register_scan("12345a")
        self.assertEqual(second.get("fullName"), "Alice", second)
        self.assertTrue(second.get("is_duplicate"), second)

    def test_stored_badge_id_keeps_raw_scan(self):
        self._write([["12345A", "Alice", "BU1", "P"]])
        svc = self._service()
        svc.register_scan("12345a")
        row = svc._db._connection.execute("SELECT badge_id, legacy_id FROM scans").fetchone()
        self.assertEqual(row["badge_id"], "12345a")
        self.assertEqual(row["legacy_id"], "12345A")

    def test_numeric_cell_with_zero_format_is_padded(self):
        self._write([[123, "Alice", "BU1", "P"]], number_format="00000")
        svc = self._service()
        self.assertIsNone(svc._roster_error)
        self.assertIn("00123", svc._employee_cache)
        self.assertEqual(svc.register_scan("00123").get("fullName"), "Alice")
        self.assertFalse(svc._roster_warning)

    def test_numeric_cell_general_format_adds_warning_with_count(self):
        self._write([[123, "Alice", "BU1", "P"], [456, "Bob", "BU1", "P"], ["789", "Cy", "BU1", "P"]])
        svc = self._service()
        self.assertIsNone(svc._roster_error)  # a warning, not an error
        self.assertIn("123", svc._employee_cache)  # import still happens
        self.assertIsNotNone(svc._roster_warning)
        self.assertIn("2 numeric", svc._roster_warning)

    def test_warning_persists_when_roster_unchanged(self):
        self._write([[123, "Alice", "BU1", "P"]])
        self._service()
        self.services.pop().close()
        svc = self._service()  # cached path, no reimport
        self.assertIn("1 numeric", svc._roster_warning)

    def test_integral_float_is_int(self):
        self._write([[12345.0, "Alice", "BU1", "P"]])
        svc = self._service()
        self.assertIn("12345", svc._employee_cache)

    def test_roster_ids_differing_only_by_case_are_duplicates(self):
        self._write([["abc1", "Alice", "BU1", "P"], ["ABC1", "Bob", "BU1", "P"]])
        svc = self._service()
        self.assertIsNotNone(svc._roster_error)
        self.assertIn("duplicate", svc._roster_error)

    def test_get_scans_by_bu_counts_lookup_scan_under_legacy_id_case_insensitive(self):
        self._write([["12345A", "Alice", "BU1", "P"], ["999", "Bob", "BU2", "P"]])
        svc = self._service()
        # Lookup scan: typed name, raw badge_id differs from the employee's ID.
        svc.register_scan("Alice", scan_source="lookup", lookup_legacy_id="12345a")
        bu = {r["bu_name"]: r for r in svc._db.get_scans_by_bu()}
        self.assertEqual(bu["BU1"]["scanned"], 1)
        self.assertEqual(bu["BU2"]["scanned"], 0)
        # Name typed for the lookup must not count as an unmatched badge.
        self.assertEqual(svc._db.count_unmatched_scanned_badges(), 0)

    def test_badge_scan_case_variants_count_once(self):
        self._write([["12345A", "Alice", "BU1", "P"]])
        svc = self._service()
        svc._db._connection.execute("PRAGMA foreign_keys=OFF")
        svc.register_scan("12345a")
        svc.register_scan("12345A")
        bu = {r["bu_name"]: r for r in svc._db.get_scans_by_bu()}
        self.assertEqual(bu["BU1"]["scanned"], 1)

    def test_unknown_badge_counts_as_unmatched_case_insensitively(self):
        self._write([["12345A", "Alice", "BU1", "P"]])
        svc = self._service()
        svc.register_scan("zz9")
        svc.register_scan("ZZ9")
        self.assertEqual(svc._db.count_unmatched_scanned_badges(), 1)


if __name__ == "__main__":
    unittest.main()
