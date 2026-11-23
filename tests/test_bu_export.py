#!/usr/bin/env python3
"""
Tests for the export's BU breakdown (dashboard.compute_bu_breakdown).

The breakdown is computed from enriched scan rows (local employee cache), not
stale cloud BU data (#52), and counts each employee once by normalised
legacy_id (#109): a badge scan and a lookup of the same person are one person,
walk-ins are excluded, unknown badges form the trailing "(Unmatched)" row.

Run: python tests/test_bu_export.py
"""

import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("CLOUD_API_KEY", "test-api-key-for-testing")
os.environ.setdefault("CLOUD_API_URL", "http://test.example.com")
sys.path.insert(0, str(Path(__file__).parent.parent))

from dashboard import compute_bu_breakdown


def _emp(legacy_id, bu):
    return SimpleNamespace(legacy_id=legacy_id, sl_l1_desc=bu)


def _reg(legacy_id, bu, scan_value=None):
    return {"_kind": "registered", "Legacy ID": legacy_id, "SL L1 Desc": bu,
            "Scan Value": scan_value or legacy_id}


def _unknown(value):
    return {"_kind": "unknown", "Legacy ID": "", "SL L1 Desc": "--", "Scan Value": value}


def _walkin(name):
    return {"_kind": "walkin", "Legacy ID": "", "SL L1 Desc": "--", "Scan Value": name}


class TestBUExportComputation(unittest.TestCase):

    def test_basic_bu_breakdown(self):
        scans = [_reg("001", "Engineering"), _reg("002", "Engineering"), _reg("003", "Sales")]
        cache = {"001": _emp("001", "Engineering"), "002": _emp("002", "Engineering"),
                 "003": _emp("003", "Sales"), "004": _emp("004", "Sales")}

        result = compute_bu_breakdown(scans, cache)

        eng = next(r for r in result if r["bu_name"] == "Engineering")
        self.assertEqual((eng["registered"], eng["scanned"], eng["attendance_rate"]), (2, 2, 100.0))
        sales = next(r for r in result if r["bu_name"] == "Sales")
        self.assertEqual((sales["registered"], sales["scanned"], sales["attendance_rate"]), (2, 1, 50.0))

    def test_unknown_badges_grouped_separately_last(self):
        scans = [_reg("001", "Engineering"), _unknown("999")]
        result = compute_bu_breakdown(scans, {"001": _emp("001", "Engineering")})

        self.assertEqual(len(result), 2)
        self.assertEqual(result[-1]["bu_name"], "(Unmatched)")
        self.assertEqual(result[-1]["scanned"], 1)
        self.assertEqual(result[-1]["registered"], 0)

    def test_walkins_not_in_any_bu_row(self):
        scans = [_reg("001", "Engineering"), _walkin("Somchai")]
        result = compute_bu_breakdown(scans, {"001": _emp("001", "Engineering")})

        self.assertEqual([r["bu_name"] for r in result], ["Engineering"])

    def test_badge_and_lookup_of_same_person_counted_once(self):
        """Badge scan (raw value differs) and lookup scan, same legacy_id."""
        scans = [_reg("E001", "Engineering", scan_value="105193T"),
                 _reg("e001", "Engineering", scan_value="E001")]
        result = compute_bu_breakdown(scans, {"E001": _emp("E001", "Engineering")})

        self.assertEqual(result[0]["scanned"], 1)

    def test_duplicate_unknown_badge_counted_once(self):
        result = compute_bu_breakdown([_unknown("zz9"), _unknown("ZZ9 ")], {})
        self.assertEqual(result[-1]["scanned"], 1)

    def test_bu_with_no_scans_still_appears(self):
        scans = [_reg("001", "Engineering")]
        cache = {"001": _emp("001", "Engineering"), "002": _emp("002", "HR")}
        hr = next(r for r in compute_bu_breakdown(scans, cache) if r["bu_name"] == "HR")
        self.assertEqual((hr["registered"], hr["scanned"], hr["attendance_rate"]), (1, 0, 0.0))

    def test_empty_scans_and_cache(self):
        self.assertEqual(compute_bu_breakdown([], {}), [])

    def test_bus_sorted_alphabetically_unmatched_last(self):
        scans = [_reg("001", "Zebra"), _reg("002", "Alpha"), _unknown("003")]
        cache = {"001": _emp("001", "Zebra"), "002": _emp("002", "Alpha")}
        names = [r["bu_name"] for r in compute_bu_breakdown(scans, cache)]
        self.assertEqual(names, ["Alpha", "Zebra", "(Unmatched)"])


if __name__ == "__main__":
    unittest.main()
