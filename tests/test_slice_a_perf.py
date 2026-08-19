#!/usr/bin/env python3
"""Focused regression/performance tests for Slice A (database.py).

Covers:
- Case-insensitive duplicate-check behavior is preserved after index rework.
- The new duplicate-check indexes (COLLATE NOCASE) are actually used by the
  query planner (EXPLAIN QUERY PLAN), and the old mismatched indexes are gone.
- count_scans_today() local-day boundary semantics match the previous
  DATE(scanned_at, 'localtime') behavior, using a sargable range query.
- count_scans_today() resolves each local-midnight boundary independently
  (via _local_midnight_to_utc), so DST transitions (23h/25h local days) are
  handled correctly instead of assuming a fixed 24h delta.
- count_scans_total() caching is correct across record_scan()/clear_all_scans()
  and can be forced to resync via invalidate_scan_count_cache().

Run: python tests/test_slice_a_perf.py
"""

import os
import sqlite3
import sys
import tempfile
import time
import unittest
from pathlib import Path
from datetime import date, datetime, timezone, timedelta

os.environ.setdefault("CLOUD_API_KEY", "test-api-key-for-testing")
os.environ.setdefault("CLOUD_API_URL", "http://test.example.com")

sys.path.insert(0, str(Path(__file__).parent.parent))

from database import DatabaseManager, EmployeeRecord, ISO_TIMESTAMP_FORMAT


def _make_employee(legacy_id="EMP001"):
    return EmployeeRecord(legacy_id, "Test User", "IT", "Engineer")


class TestDuplicateIndexUsage(unittest.TestCase):
    """Verify the NOCASE duplicate-check indexes exist and are actually used."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test.db"
        self.db = DatabaseManager(self.db_path)
        self.db.set_station_name("Gate A")

    def tearDown(self):
        self.db.close()
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_nocase_indexes_exist(self):
        cursor = self.db._connection.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='scans'"
        )
        names = {row["name"] for row in cursor.fetchall()}
        self.assertIn("idx_scans_badge_station_time_nocase", names)
        self.assertIn("idx_scans_legacy_station_time_nocase", names)
        self.assertIn("idx_scans_scanned_at", names)
        # Old mismatched-collation indexes should be dropped, not left dangling.
        self.assertNotIn("idx_scans_badge_station_time", names)
        self.assertNotIn("idx_scans_legacy_station_time", names)

    def test_duplicate_badge_query_uses_nocase_index(self):
        self.db.record_scan("ABC123", "Gate A", _make_employee())
        plan = self.db._connection.execute(
            """
            EXPLAIN QUERY PLAN
            SELECT id FROM scans
            WHERE badge_id = ? COLLATE NOCASE
            AND station_name = ? COLLATE NOCASE
            AND scanned_at >= ?
            ORDER BY scanned_at DESC
            LIMIT 1
            """,
            ("ABC123", "Gate A", "2020-01-01T00:00:00Z"),
        ).fetchall()
        plan_text = " ".join(row["detail"] for row in plan)
        self.assertIn("idx_scans_badge_station_time_nocase", plan_text)
        self.assertIn("USING COVERING INDEX", plan_text.upper())

    def test_duplicate_employee_query_uses_nocase_index(self):
        self.db.record_scan("ABC123", "Gate A", _make_employee("EMP999"))
        plan = self.db._connection.execute(
            """
            EXPLAIN QUERY PLAN
            SELECT id FROM scans
            WHERE legacy_id = ? COLLATE NOCASE
            AND station_name = ? COLLATE NOCASE
            AND scanned_at >= ?
            ORDER BY scanned_at DESC
            LIMIT 1
            """,
            ("EMP999", "Gate A", "2020-01-01T00:00:00Z"),
        ).fetchall()
        plan_text = " ".join(row["detail"] for row in plan)
        self.assertIn("idx_scans_legacy_station_time_nocase", plan_text)

    def test_count_scans_today_query_uses_scanned_at_index(self):
        plan = self.db._connection.execute(
            "EXPLAIN QUERY PLAN SELECT COUNT(1) FROM scans WHERE scanned_at >= ? AND scanned_at < ?",
            ("2020-01-01T00:00:00Z", "2020-01-02T00:00:00Z"),
        ).fetchall()
        plan_text = " ".join(row["detail"] for row in plan)
        self.assertIn("idx_scans_scanned_at", plan_text)


class TestCaseInsensitiveDuplicateBehavior(unittest.TestCase):
    """Case-insensitive duplicate detection must behave exactly as before."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test.db"
        self.db = DatabaseManager(self.db_path)
        self.db.set_station_name("Gate A")

    def tearDown(self):
        self.db.close()
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_badge_duplicate_case_insensitive(self):
        self.db.record_scan("abc123", "Gate A", None)
        is_dup, _ = self.db.check_if_duplicate_badge("ABC123", "GATE A", time_window_seconds=60)
        self.assertTrue(is_dup)

    def test_badge_duplicate_mixed_case_variants(self):
        self.db.record_scan("AbC123", "gate a", None)
        for badge_variant, station_variant in [
            ("abc123", "Gate A"),
            ("ABC123", "GATE A"),
            ("aBc123", "gAtE a"),
        ]:
            is_dup, _ = self.db.check_if_duplicate_badge(
                badge_variant, station_variant, time_window_seconds=60
            )
            self.assertTrue(is_dup, f"expected duplicate for {badge_variant}/{station_variant}")

    def test_employee_duplicate_case_insensitive(self):
        emp = _make_employee("EMP001")
        self.db.record_scan("badge1", "Gate A", emp)
        is_dup, _ = self.db.check_if_duplicate_employee("emp001", "gate a", time_window_seconds=60)
        self.assertTrue(is_dup)

    def test_different_badge_not_duplicate(self):
        self.db.record_scan("abc123", "Gate A", None)
        is_dup, _ = self.db.check_if_duplicate_badge("xyz999", "Gate A", time_window_seconds=60)
        self.assertFalse(is_dup)

    def test_different_station_not_duplicate(self):
        self.db.record_scan("abc123", "Gate A", None)
        is_dup, _ = self.db.check_if_duplicate_badge("abc123", "Gate B", time_window_seconds=60)
        self.assertFalse(is_dup)

    def test_outside_time_window_not_duplicate(self):
        past = (datetime.now(timezone.utc) - timedelta(seconds=120)).strftime(ISO_TIMESTAMP_FORMAT)
        self.db.record_scan("abc123", "Gate A", None, scanned_at=past)
        is_dup, _ = self.db.check_if_duplicate_badge("abc123", "Gate A", time_window_seconds=60)
        self.assertFalse(is_dup)


class TestCountScansTodayBoundary(unittest.TestCase):
    """count_scans_today() must preserve local-day semantics with the new range query."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test.db"
        self.db = DatabaseManager(self.db_path)
        self.db.set_station_name("Gate A")

    def tearDown(self):
        self.db.close()
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _legacy_count_today(self) -> int:
        """Recompute using the original DATE(scanned_at,'localtime') logic for comparison."""
        cursor = self.db._connection.execute(
            "SELECT COUNT(1) FROM scans WHERE DATE(scanned_at, 'localtime') = DATE('now', 'localtime')"
        )
        return int(cursor.fetchone()[0])

    def test_matches_legacy_query_for_current_scans(self):
        for i in range(5):
            self.db.record_scan(f"BADGE{i}", "Gate A", None)
        self.assertEqual(self.db.count_scans_today(), self._legacy_count_today())
        self.assertEqual(self.db.count_scans_today(), 5)

    def test_matches_legacy_query_with_mixed_days(self):
        now = datetime.now(timezone.utc)
        today_str = now.strftime("%Y-%m-%d")
        yesterday_str = (now - timedelta(days=1)).strftime("%Y-%m-%d")

        for i in range(3):
            self.db.record_scan(
                f"TODAY{i}", "Gate A", None,
                scanned_at=f"{today_str}T12:00:{i:02d}Z",
            )
        for i in range(2):
            self.db.record_scan(
                f"YEST{i}", "Gate A", None,
                scanned_at=f"{yesterday_str}T12:00:{i:02d}Z",
            )

        self.assertEqual(self.db.count_scans_today(), self._legacy_count_today())

    def test_matches_legacy_query_near_midnight_boundary(self):
        now = datetime.now(timezone.utc)
        today_str = now.strftime("%Y-%m-%d")

        self.db.record_scan("LATE", "Gate A", None, scanned_at=f"{today_str}T23:30:00Z")
        self.db.record_scan("EARLY", "Gate A", None, scanned_at=f"{today_str}T00:05:00Z")
        self.db.record_scan("NOON", "Gate A", None, scanned_at=f"{today_str}T12:00:00Z")

        self.assertEqual(self.db.count_scans_today(), self._legacy_count_today())
        self.assertEqual(self.db.count_scans_total(), 3)

    def test_zero_when_no_scans(self):
        self.assertEqual(self.db.count_scans_today(), 0)


class TestLocalMidnightDstSafety(unittest.TestCase):
    """_local_midnight_to_utc() must resolve each local midnight independently,
    matching the OS's own DST rules for that specific calendar date — the same
    guarantee SQLite's DATE(x, 'localtime') modifier provides, and the exact
    property a naive "add a fixed 24h offset" implementation would violate.
    """

    def test_round_trip_gives_exact_local_midnight_for_every_day_of_year(self):
        """For every day in a full year, converting local midnight to UTC and back
        via the OS's own localtime() must land exactly on that date at 00:00:00.
        This holds regardless of the system's timezone or its DST rules (if any),
        and would fail if the helper used a fixed-offset/fixed-24h assumption
        instead of resolving each date's offset independently.
        """
        from database import _local_midnight_to_utc

        start = date(2026, 1, 1)
        for offset in range(0, 366):
            d = start + timedelta(days=offset)
            utc_dt = _local_midnight_to_utc(d)
            local_struct = time.localtime(utc_dt.timestamp())
            self.assertEqual(
                (local_struct.tm_year, local_struct.tm_mon, local_struct.tm_mday),
                (d.year, d.month, d.day),
                f"local midnight round-trip failed for {d.isoformat()}",
            )
            self.assertEqual(
                (local_struct.tm_hour, local_struct.tm_min, local_struct.tm_sec),
                (0, 0, 0),
                f"local midnight round-trip not exactly 00:00:00 for {d.isoformat()}",
            )

    def test_consecutive_local_midnights_differ_by_23_24_or_25_hours(self):
        """The gap between two consecutive local midnights is always 23h, 24h, or 25h
        (23/25 only on a DST transition day). A fixed-24h-delta bug would still pass
        on non-transition days, so this alone doesn't prove DST-safety — combined with
        the round-trip test above, it guards against regressions in either direction.
        """
        from database import _local_midnight_to_utc

        start = date(2026, 1, 1)
        for offset in range(0, 365):
            d0 = start + timedelta(days=offset)
            d1 = d0 + timedelta(days=1)
            delta_hours = (_local_midnight_to_utc(d1) - _local_midnight_to_utc(d0)).total_seconds() / 3600
            self.assertIn(delta_hours, (23.0, 24.0, 25.0), f"unexpected gap {delta_hours}h between {d0} and {d1}")

    @unittest.skipUnless(hasattr(time, "tzset"), "time.tzset() unavailable on this platform (Windows)")
    def test_dst_transition_boundary_matches_sqlite_localtime(self):
        """On platforms that support tzset(), force a DST-observing timezone and verify
        _local_midnight_to_utc() resolves the exact same UTC instant for a local midnight
        that SQLite's own DATE(x, 'localtime') modifier would consider midnight — checked
        directly across the US spring-forward transition (2026-03-08), the scenario a
        fixed-offset/fixed-24h-delta implementation gets wrong.
        """
        import os as _os
        from database import _local_midnight_to_utc

        old_tz = _os.environ.get("TZ")
        try:
            _os.environ["TZ"] = "America/New_York"
            time.tzset()

            conn = sqlite3.connect(":memory:")
            try:
                for d in (date(2026, 3, 7), date(2026, 3, 8), date(2026, 3, 9)):
                    midnight_utc = _local_midnight_to_utc(d)
                    ts = midnight_utc.strftime(ISO_TIMESTAMP_FORMAT)
                    sqlite_local_date = conn.execute(
                        "SELECT DATE(?, 'localtime')", (ts,)
                    ).fetchone()[0]
                    self.assertEqual(
                        sqlite_local_date, d.isoformat(),
                        f"_local_midnight_to_utc({d}) -> {ts} does not resolve to local date {d} in SQLite",
                    )
            finally:
                conn.close()
        finally:
            if old_tz is None:
                _os.environ.pop("TZ", None)
            else:
                _os.environ["TZ"] = old_tz
            time.tzset()


class TestScanCountCache(unittest.TestCase):
    """count_scans_total() caching must stay correct across writes and resets."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test.db"
        self.db = DatabaseManager(self.db_path)
        self.db.set_station_name("Gate A")

    def tearDown(self):
        self.db.close()
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_cache_starts_correct_on_fresh_db(self):
        self.assertEqual(self.db.count_scans_total(), 0)

    def test_cache_increments_on_record_scan(self):
        self.assertEqual(self.db.count_scans_total(), 0)
        self.db.record_scan("B1", "Gate A", None)
        self.assertEqual(self.db.count_scans_total(), 1)
        self.db.record_scan("B2", "Gate A", None)
        self.db.record_scan("B3", "Gate A", None)
        self.assertEqual(self.db.count_scans_total(), 3)

    def test_cache_resets_on_clear_all_scans(self):
        for i in range(4):
            self.db.record_scan(f"B{i}", "Gate A", None)
        self.assertEqual(self.db.count_scans_total(), 4)
        deleted = self.db.clear_all_scans()
        self.assertEqual(deleted, 4)
        self.assertEqual(self.db.count_scans_total(), 0)

    def test_cache_correct_across_multiple_clear_cycles(self):
        for _ in range(3):
            self.db.record_scan("B1", "Gate A", None)
            self.db.record_scan("B2", "Gate A", None)
            self.assertEqual(self.db.count_scans_total(), 2)
            self.db.clear_all_scans()
            self.assertEqual(self.db.count_scans_total(), 0)

    def test_cache_seeded_correctly_on_reopen(self):
        """A fresh DatabaseManager instance (e.g. after restart) must seed from real data."""
        for i in range(7):
            self.db.record_scan(f"B{i}", "Gate A", None)
        self.db.close()

        reopened = DatabaseManager(self.db_path)
        try:
            self.assertEqual(reopened.count_scans_total(), 7)
        finally:
            reopened.close()

    def test_invalidate_forces_resync_after_external_write(self):
        self.db.record_scan("B1", "Gate A", None)
        self.assertEqual(self.db.count_scans_total(), 1)

        # Simulate an out-of-band write that bypasses record_scan().
        with self.db._connection:
            self.db._connection.execute(
                "INSERT INTO scans (badge_id, scanned_at, station_name) VALUES ('X', '2020-01-01T00:00:00Z', 'Gate A')"
            )

        # Cache is now stale by design (out-of-band write) until invalidated.
        self.assertEqual(self.db.count_scans_total(), 1)
        self.db.invalidate_scan_count_cache()
        self.assertEqual(self.db.count_scans_total(), 2)


class TestPerScanQueryPerformance(unittest.TestCase):
    """Sanity check: repeated count_scans_total() calls stay cheap after caching."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test.db"
        self.db = DatabaseManager(self.db_path)
        self.db.set_station_name("Gate A")

    def tearDown(self):
        self.db.close()
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_repeated_count_scans_total_is_fast(self):
        for i in range(500):
            self.db.record_scan(f"B{i}", "Gate A", None)

        start = time.time()
        for _ in range(2000):
            self.db.count_scans_total()
        elapsed = time.time() - start

        self.assertLess(elapsed, 0.05, f"2000 cached count_scans_total() calls took {elapsed*1000:.2f}ms")


def main():
    print("=" * 70)
    print("SLICE A REGRESSION / PERFORMANCE / QUERY-PLAN TESTS")
    print("=" * 70)
    print()

    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    suite.addTests(loader.loadTestsFromTestCase(TestDuplicateIndexUsage))
    suite.addTests(loader.loadTestsFromTestCase(TestCaseInsensitiveDuplicateBehavior))
    suite.addTests(loader.loadTestsFromTestCase(TestCountScansTodayBoundary))
    suite.addTests(loader.loadTestsFromTestCase(TestLocalMidnightDstSafety))
    suite.addTests(loader.loadTestsFromTestCase(TestScanCountCache))
    suite.addTests(loader.loadTestsFromTestCase(TestPerScanQueryPerformance))

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
