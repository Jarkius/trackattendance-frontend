#!/usr/bin/env python3
"""Regression test: search_employee() must prioritize name-prefix matches over
mid-name substring matches, especially for short/single-character queries.

Bug: Tier 1 in search_employee() (attendance.py) treats `query in name_lower`
as a single bucket — "starts with" and "contains anywhere" are not
distinguished — and the 10-result cap (line ~401) is applied in employee-cache
iteration order. For a common single letter like "c", employees whose name
merely *contains* a "c" (e.g. "Marcus") can fill all 10 slots before an
employee whose name *starts with* "c" (e.g. "Carlos") is ever considered.

Run: python tests/test_search_employee_prefix_priority.py
"""

import os
import sys
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


class FakeEmployee:
    def __init__(self, legacy_id, full_name, email=""):
        self.legacy_id = legacy_id
        self.full_name = full_name
        self.email = email
        self.sl_l1_desc = "IT"


def _make_service(employees):
    """Build an AttendanceService with only _employee_cache populated —
    search_employee() reads nothing else."""
    svc = AttendanceService.__new__(AttendanceService)
    svc._employee_cache = {emp.legacy_id: emp for emp in employees}
    return svc


@unittest.skipUnless(PYQT6_AVAILABLE, "PyQt6 not installed in this environment")
class TestSearchEmployeePrefixPriority(unittest.TestCase):
    def test_prefix_match_not_starved_out_by_mid_name_matches(self):
        """The exact regression: 10 'contains c' names inserted before a
        'starts with c' name must not push it out of the results."""
        employees = [FakeEmployee(f"E{i}", f"Marcus Test{i}") for i in range(10)]
        employees.append(FakeEmployee("E_CARLOS", "Carlos Rodriguez"))
        svc = _make_service(employees)

        results = svc.search_employee("c")
        names = [r["full_name"] for r in results]

        self.assertTrue(
            any("Carlos" in n for n in names),
            f"Prefix match 'Carlos' missing from results, got: {names}",
        )

    def test_prefix_matches_ranked_before_mid_name_matches(self):
        """Even when both fit under the cap, prefix matches should be
        returned ahead of pure substring matches."""
        employees = [
            FakeEmployee("E1", "Marcus Aurelius"),
            FakeEmployee("E2", "Carlos Rodriguez"),
        ]
        svc = _make_service(employees)

        results = svc.search_employee("c")
        names = [r["full_name"] for r in results]

        self.assertEqual(
            names[0], "Carlos Rodriguez",
            f"Expected prefix match first, got order: {names}",
        )

    def test_single_letter_query_still_returns_up_to_ten_prefix_matches(self):
        employees = [FakeEmployee(f"C{i}", f"Carl Person{i}") for i in range(15)]
        svc = _make_service(employees)

        results = svc.search_employee("c")

        self.assertEqual(len(results), 10)

    def test_first_name_prefix_ranked_before_surname_prefix(self):
        """Regression: 'j' matching a first name (e.g. "Jihun Jung") must
        rank above 'j' only matching a surname (e.g. "Parichart Jiravachara"),
        since that's what a user searching by first name expects."""
        employees = [
            FakeEmployee("E1", "Parichart Jiravachara"),
            FakeEmployee("E2", "Jihun Jung"),
        ]
        svc = _make_service(employees)

        results = svc.search_employee("j")
        names = [r["full_name"] for r in results]

        self.assertEqual(
            names[0], "Jihun Jung",
            f"Expected first-name prefix match first, got order: {names}",
        )


def main():
    print("=" * 70)
    print("SEARCH EMPLOYEE PREFIX PRIORITY TESTS")
    print("=" * 70)
    if not PYQT6_AVAILABLE:
        print("\n[SKIP] PyQt6 is not installed in this environment.")
        print("All tests in this file are skipped — attendance.py cannot be")
        print("imported without PyQt6. Run this file in a PyQt6-enabled")
        print("environment for real coverage.\n")
    print()

    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    suite.addTests(loader.loadTestsFromTestCase(TestSearchEmployeePrefixPriority))

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
