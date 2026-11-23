#!/usr/bin/env python3
"""Regression tests for #105: roster header normalisation and surfaced import aborts.

Run: python -m pytest tests/test_roster_header_normalisation.py
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
    from attendance import AttendanceService
    AVAILABLE = True
except ImportError:
    AVAILABLE = False

GOOD_HEADERS = ["Legacy ID", "Full Name", "SL L1 Desc", "Position Desc"]


@unittest.skipUnless(AVAILABLE, "PyQt6/openpyxl not installed")
class TestRosterHeaderNormalisation(unittest.TestCase):
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

    def _write(self, headers, rows):
        wb = Workbook()
        ws = wb.active
        ws.append(headers)
        for row in rows:
            ws.append(row)
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

    def _assert_alice_matches(self, svc):
        self.assertIsNone(svc._roster_error)
        result = svc.register_scan("00123")
        self.assertEqual(result.get("fullName"), "Alice", result)

    def _legacy_header_case(self, header):
        self._write([header] + GOOD_HEADERS[1:], [["00123", "Alice", "BU1", "P"]])
        self._assert_alice_matches(self._service())

    def test_trailing_space_header(self):
        self._legacy_header_case("Legacy ID ")

    def test_lowercase_header(self):
        self._legacy_header_case("legacy id")

    def test_nbsp_header(self):
        self._legacy_header_case("Legacy ID")

    def test_trailing_nbsp_and_zero_width_header(self):
        self._legacy_header_case("​Legacy ID ")

    def test_other_columns_and_email_normalised(self):
        self._write(
            ["Legacy ID", " full name", "SL L1 DESC ", "Position Desc", "EMAIL "],
            [["00123", "Alice", "BU1", "P", "a@example.com"]],
        )
        svc = self._service()
        self.assertIsNone(svc._roster_error)
        emp = svc._employee_cache["00123"]
        self.assertEqual(
            (emp.full_name, emp.sl_l1_desc, emp.position_desc, emp.email),
            ("Alice", "BU1", "P", "a@example.com"),
        )

    def test_validate_roster_headers_accepts_cosmetic_variants(self):
        self._write(["legacy id ", "Full Name", "SL L1 Desc", "Position Desc"], [])
        svc = self._service()
        ok, msg = svc.validate_roster_headers(self.workbook_path)
        self.assertTrue(ok, msg)

    def test_missing_column_sets_error_naming_it(self):
        self._write(["Legacy ID", "Full Name", "Position Desc"], [["00123", "Alice", "P"]])
        svc = self._service()
        self.assertIsNotNone(svc._roster_error)
        self.assertIn("SL L1 Desc", svc._roster_error)

    def test_missing_column_without_validation_still_sets_error(self):
        import importlib
        import config
        os.environ["ROSTER_VALIDATION_ENABLED"] = "False"
        importlib.reload(config)
        try:
            self._write(["Legacy ID", "Full Name", "Position Desc"], [["00123", "Alice", "P"]])
            svc = self._service()
            self.assertIsNotNone(svc._roster_error)
            self.assertIn("SL L1 Desc", svc._roster_error)
        finally:
            os.environ.pop("ROSTER_VALIDATION_ENABLED", None)
            importlib.reload(config)

    def test_missing_column_keeps_previous_roster_and_shows_error(self):
        self._write(GOOD_HEADERS, [["00123", "Alice", "BU1", "P"]])
        self._assert_alice_matches(self._service())
        self.services.pop().close()

        self._write(["Legacy ID", "Full Name", "Position Desc"], [["00999", "Bob", "P"]])
        svc = self._service()
        self.assertIsNotNone(svc._roster_error)
        self.assertIn("SL L1 Desc", svc._roster_error)
        self.assertIn("00123", svc._employee_cache)
        self.assertNotIn("00999", svc._employee_cache)

    def test_zero_valid_rows_sets_error(self):
        self._write(GOOD_HEADERS, [[None, "Ghost", "BU1", "P"], ["  ", "Ghost2", "BU1", "P"]])
        svc = self._service()
        self.assertIsNotNone(svc._roster_error)
        self.assertIn("no valid", svc._roster_error)

    def test_header_only_sheet_sets_error(self):
        self._write(GOOD_HEADERS, [])
        svc = self._service()
        self.assertIsNotNone(svc._roster_error)

    def test_failed_import_does_not_cache_hash_so_fixed_file_reimports(self):
        self._write(["Legacy ID", "Full Name", "Position Desc"], [["00123", "Alice", "P"]])
        svc = self._service()
        self.assertIsNotNone(svc._roster_error)
        self.assertIsNone(svc._db.get_roster_hash())
        self.services.pop().close()

        self._write(GOOD_HEADERS, [["00123", "Alice", "BU1", "P"]])
        self._assert_alice_matches(self._service())

    def test_duplicate_legacy_id_still_raises(self):
        self._write(GOOD_HEADERS, [["00123", "Alice", "BU1", "P"], ["00123", "Bob", "BU1", "P"]])
        svc = self._service()
        self.assertIsNotNone(svc._roster_error)
        self.assertIn("duplicate", svc._roster_error)


if __name__ == "__main__":
    unittest.main()
