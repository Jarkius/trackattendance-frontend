#!/usr/bin/env python3
"""Regression test: a corrupt/malformed employee.xlsx must not crash the app
at startup — it should degrade gracefully via AttendanceService._roster_error,
the same path already used for the duplicate-Legacy-ID case.

Bug: AttendanceService._bootstrap_employee_directory() called load_workbook()
with no try/except around it. validate_roster_headers() catches file-open
errors and returns early when ROSTER_STRICT_VALIDATION is enabled (the
default), but with ROSTER_STRICT_VALIDATION=False or
ROSTER_VALIDATION_ENABLED=False, execution falls through to the unguarded
load_workbook() call, which raises BadZipFile/InvalidFileException/etc. on a
corrupt file — none of which are ValueError, so they bypass __init__'s
`except ValueError` and crash the whole app instead of setting
self._roster_error like every other roster problem does.

Run: python tests/test_roster_bootstrap_corrupt_file.py
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path

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


@unittest.skipUnless(PYQT6_AVAILABLE, "PyQt6 not installed in this environment")
class TestRosterBootstrapCorruptFile(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test.db"
        self.workbook_path = Path(self.temp_dir) / "employee.xlsx"
        self.export_dir = Path(self.temp_dir) / "exports"
        with open(self.workbook_path, "wb") as f:
            f.write(b"this is not a real xlsx file, just garbage bytes")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _make_service(self):
        return AttendanceService(
            database_path=self.db_path,
            employee_workbook_path=self.workbook_path,
            export_directory=self.export_dir,
        )

    @staticmethod
    def _reload_config():
        import importlib
        import config
        importlib.reload(config)

    def test_corrupt_file_with_strict_validation_does_not_crash(self):
        """The default path (ROSTER_STRICT_VALIDATION=True) already catches
        this via validate_roster_headers() — confirms it stays that way."""
        os.environ["ROSTER_STRICT_VALIDATION"] = "True"
        self._reload_config()
        try:
            service = self._make_service()
            self.assertIsNone(service._roster_error)  # caught+skipped before raising
            service.close()
        finally:
            os.environ.pop("ROSTER_STRICT_VALIDATION", None)
            self._reload_config()

    def test_corrupt_file_with_strict_validation_disabled_does_not_crash(self):
        """The actual regression: without strict validation, execution used
        to fall through to an unguarded load_workbook() call and crash."""
        os.environ["ROSTER_STRICT_VALIDATION"] = "False"
        self._reload_config()
        try:
            service = self._make_service()  # must not raise
            self.assertIsNotNone(service._roster_error)
            self.assertIn("employee.xlsx", service._roster_error)
            service.close()
        finally:
            os.environ.pop("ROSTER_STRICT_VALIDATION", None)
            self._reload_config()

    def test_corrupt_file_with_validation_entirely_disabled_does_not_crash(self):
        os.environ["ROSTER_VALIDATION_ENABLED"] = "False"
        self._reload_config()
        try:
            service = self._make_service()  # must not raise
            self.assertIsNotNone(service._roster_error)
            service.close()
        finally:
            os.environ.pop("ROSTER_VALIDATION_ENABLED", None)
            self._reload_config()


def main():
    print("=" * 70)
    print("ROSTER BOOTSTRAP CORRUPT FILE TESTS")
    print("=" * 70)
    if not PYQT6_AVAILABLE:
        print("\n[SKIP] PyQt6 is not installed in this environment.")
        print("All tests in this file are skipped — attendance.py cannot be")
        print("imported without PyQt6. Run this file in a PyQt6-enabled")
        print("environment for real coverage.\n")
    print()

    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    suite.addTests(loader.loadTestsFromTestCase(TestRosterBootstrapCorruptFile))

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
