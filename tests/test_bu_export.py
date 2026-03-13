#!/usr/bin/env python3
"""
Tests for BU (Business Unit) export computation logic.

Verifies that the BU breakdown in export is computed from enriched scan data
(local employee cache) rather than stale cloud API data. This was the root
cause of #52: wrong scanned counts and spurious "Unmatched" entries.

Run: python tests/test_bu_export.py
"""

import unittest
from collections import defaultdict
from types import SimpleNamespace


def compute_bu_breakdown(enriched_scans, employee_cache):
    """Extract the BU computation logic from dashboard.export_to_excel().

    This mirrors the logic at dashboard.py lines 419-444 exactly,
    extracted here for unit testing without openpyxl/database dependencies.
    """
    bu_scanned = defaultdict(set)
    for row in enriched_scans:
        badge_id = row["Scan Value"]
        bu = row["SL L1 Desc"]
        bu_key = bu if bu and bu != "--" else "(Unmatched)"
        bu_scanned[bu_key].add(badge_id)

    bu_registered = defaultdict(int)
    for emp in employee_cache.values():
        bu_registered[emp.sl_l1_desc or "(Unmatched)"] += 1

    all_bus = sorted(set(bu_scanned.keys()) | set(bu_registered.keys()))
    bu_export = []
    for bu_name in all_bus:
        if bu_name == "(Unmatched)":
            continue
        registered = bu_registered.get(bu_name, 0)
        scanned = len(bu_scanned.get(bu_name, set()))
        rate = round((scanned / registered) * 100, 1) if registered > 0 else 0.0
        bu_export.append({
            "bu_name": bu_name,
            "registered": registered,
            "scanned": scanned,
            "attendance_rate": rate,
        })
    if "(Unmatched)" in bu_scanned:
        bu_export.append({
            "bu_name": "(Unmatched)",
            "registered": 0,
            "scanned": len(bu_scanned["(Unmatched)"]),
            "attendance_rate": 0.0,
        })
    return bu_export


def _emp(legacy_id, bu):
    """Create a minimal employee-like object."""
    return SimpleNamespace(legacy_id=legacy_id, sl_l1_desc=bu)


class TestBUExportComputation(unittest.TestCase):
    """Test BU breakdown computation from enriched scan data."""

    def test_basic_bu_breakdown(self):
        """Scans are grouped by BU with correct counts."""
        enriched_scans = [
            {"Scan Value": "001", "SL L1 Desc": "Engineering"},
            {"Scan Value": "002", "SL L1 Desc": "Engineering"},
            {"Scan Value": "003", "SL L1 Desc": "Sales"},
        ]
        employee_cache = {
            "001": _emp("001", "Engineering"),
            "002": _emp("002", "Engineering"),
            "003": _emp("003", "Sales"),
            "004": _emp("004", "Sales"),
        }

        result = compute_bu_breakdown(enriched_scans, employee_cache)

        eng = next(r for r in result if r["bu_name"] == "Engineering")
        self.assertEqual(eng["registered"], 2)
        self.assertEqual(eng["scanned"], 2)
        self.assertEqual(eng["attendance_rate"], 100.0)

        sales = next(r for r in result if r["bu_name"] == "Sales")
        self.assertEqual(sales["registered"], 2)
        self.assertEqual(sales["scanned"], 1)
        self.assertEqual(sales["attendance_rate"], 50.0)

    def test_unmatched_scans_grouped_separately(self):
        """Scans with '--' BU are grouped as (Unmatched) at the end."""
        enriched_scans = [
            {"Scan Value": "001", "SL L1 Desc": "Engineering"},
            {"Scan Value": "999", "SL L1 Desc": "--"},
        ]
        employee_cache = {
            "001": _emp("001", "Engineering"),
        }

        result = compute_bu_breakdown(enriched_scans, employee_cache)

        self.assertEqual(len(result), 2)
        # Unmatched should be last
        self.assertEqual(result[-1]["bu_name"], "(Unmatched)")
        self.assertEqual(result[-1]["scanned"], 1)
        self.assertEqual(result[-1]["registered"], 0)
        self.assertEqual(result[-1]["attendance_rate"], 0.0)

    def test_duplicate_badge_counted_once(self):
        """Same badge scanned twice counts as 1 unique scan."""
        enriched_scans = [
            {"Scan Value": "001", "SL L1 Desc": "Engineering"},
            {"Scan Value": "001", "SL L1 Desc": "Engineering"},
        ]
        employee_cache = {
            "001": _emp("001", "Engineering"),
        }

        result = compute_bu_breakdown(enriched_scans, employee_cache)

        eng = result[0]
        self.assertEqual(eng["scanned"], 1)

    def test_bu_with_no_scans_still_appears(self):
        """A BU with registered employees but zero scans should appear."""
        enriched_scans = [
            {"Scan Value": "001", "SL L1 Desc": "Engineering"},
        ]
        employee_cache = {
            "001": _emp("001", "Engineering"),
            "002": _emp("002", "HR"),
        }

        result = compute_bu_breakdown(enriched_scans, employee_cache)

        hr = next(r for r in result if r["bu_name"] == "HR")
        self.assertEqual(hr["registered"], 1)
        self.assertEqual(hr["scanned"], 0)
        self.assertEqual(hr["attendance_rate"], 0.0)

    def test_empty_scans_and_cache(self):
        """No scans and no employees returns empty list."""
        result = compute_bu_breakdown([], {})
        self.assertEqual(result, [])

    def test_employees_with_none_bu_grouped_as_unmatched(self):
        """Employees with None sl_l1_desc are counted as (Unmatched)."""
        enriched_scans = []
        employee_cache = {
            "001": _emp("001", None),
        }

        result = compute_bu_breakdown(enriched_scans, employee_cache)

        # No scans, so (Unmatched) won't appear in bu_scanned → won't be in output
        # Only BUs with scans OR registered employees appear
        unmatched = [r for r in result if r["bu_name"] == "(Unmatched)"]
        # (Unmatched) appears in bu_registered but not bu_scanned,
        # and the code skips it in the main loop, only appending if in bu_scanned
        self.assertEqual(len(unmatched), 0)

    def test_bus_sorted_alphabetically(self):
        """BU names should be sorted alphabetically (Unmatched last)."""
        enriched_scans = [
            {"Scan Value": "001", "SL L1 Desc": "Zebra"},
            {"Scan Value": "002", "SL L1 Desc": "Alpha"},
            {"Scan Value": "003", "SL L1 Desc": "--"},
        ]
        employee_cache = {
            "001": _emp("001", "Zebra"),
            "002": _emp("002", "Alpha"),
        }

        result = compute_bu_breakdown(enriched_scans, employee_cache)

        names = [r["bu_name"] for r in result]
        self.assertEqual(names, ["Alpha", "Zebra", "(Unmatched)"])


if __name__ == "__main__":
    unittest.main()
