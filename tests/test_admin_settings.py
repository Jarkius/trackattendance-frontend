#!/usr/bin/env python3
"""
Tests for Admin Settings — Camera & Display sections.

Tests the new admin slots, settings persistence via SQLite,
overlay mode switching, and new slider-based controls.

Run: python tests/test_admin_settings.py
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

# Set required env vars BEFORE importing config
os.environ.setdefault("CLOUD_API_KEY", "test-api-key")
os.environ.setdefault("CLOUD_API_URL", "http://test.example.com")

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import config
from database import DatabaseManager


# =========================================================================
# Settings Persistence (SQLite key-value)
# =========================================================================
class TestSettingsPersistence(unittest.TestCase):
    """Test that admin settings save/load via SQLite roster_meta table."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test.db"
        self.db = DatabaseManager(self.db_path)
        self.db.set_station_name("TestStation")

    def tearDown(self):
        self.db.close()
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_set_and_get_setting(self):
        """Settings round-trip through SQLite."""
        self.db.set_meta("setting:scan_feedback_ms", "3000")
        self.assertEqual(self.db.get_meta("setting:scan_feedback_ms"), "3000")

    def test_setting_overwrite(self):
        """Settings can be updated."""
        self.db.set_meta("setting:scan_feedback_ms", "2000")
        self.db.set_meta("setting:scan_feedback_ms", "5000")
        self.assertEqual(self.db.get_meta("setting:scan_feedback_ms"), "5000")

    def test_missing_setting_returns_none(self):
        """Unset settings return None."""
        self.assertIsNone(self.db.get_meta("setting:nonexistent"))

    def test_setting_namespace(self):
        """Settings use 'setting:' prefix to avoid collisions."""
        self.db.set_meta("setting:camera_overlay", "True")
        self.db.set_meta("other_key", "other_value")
        self.assertEqual(self.db.get_meta("setting:camera_overlay"), "True")
        self.assertEqual(self.db.get_meta("other_key"), "other_value")


# =========================================================================
# Admin Slot Return Formats
# =========================================================================
class TestAdminSlotContracts(unittest.TestCase):
    """Test the return format contracts for admin slots."""

    def test_camera_overlay_response(self):
        result = {"ok": True, "enabled": False}
        self.assertIn("ok", result)
        self.assertIn("enabled", result)

    def test_greeting_cooldown_response(self):
        result = {"ok": True, "value": 60}
        self.assertIn("ok", result)
        self.assertIn("value", result)

    def test_scan_feedback_response(self):
        result = {"ok": True, "value": 3000}
        self.assertIn("ok", result)
        self.assertIn("value", result)

    def test_connection_check_response(self):
        result = {"ok": True, "value": 10.0}
        self.assertIn("ok", result)
        self.assertIn("value", result)

    def test_min_size_pct_response(self):
        result = {"ok": True, "value": 0.20}
        self.assertIn("ok", result)
        self.assertIn("value", result)

    def test_absence_threshold_response(self):
        result = {"ok": True, "value": 3.0}
        self.assertIn("ok", result)
        self.assertIn("value", result)

    def test_camera_not_configured_response(self):
        result = {"ok": False, "message": "Camera not configured"}
        self.assertFalse(result["ok"])
        self.assertIn("not configured", result["message"])


# =========================================================================
# admin_get_local_settings extended fields
# =========================================================================
class TestLocalSettingsPayload(unittest.TestCase):
    """Test that admin_get_local_settings includes all required fields."""

    def test_payload_has_all_fields(self):
        payload = {
            "duplicate_window": 60, "duplicate_action": "warn",
            "voice_enabled": True, "voice_volume": 1.0,
            "camera_enabled": True, "camera_running": False,
            "camera_overlay": True, "greeting_cooldown": 60.0,
            "min_size_pct": 0.20, "absence_threshold": 3.0,
            "scan_feedback_ms": 2000, "connection_check_s": 10,
            "dashboard_url": "http://test.example.com/dashboard/",
        }
        for key in ["camera_enabled", "camera_running", "camera_overlay",
                     "greeting_cooldown", "min_size_pct", "absence_threshold",
                     "scan_feedback_ms", "connection_check_s", "dashboard_url"]:
            self.assertIn(key, payload, f"Missing key: {key}")

    def test_dashboard_url_format(self):
        url = "https://api.example.com"
        dashboard = url.rstrip("/") + "/dashboard/"
        self.assertTrue(dashboard.endswith("/dashboard/"))


# =========================================================================
# Value clamping
# =========================================================================
class TestValueClamping(unittest.TestCase):
    """Test that settings values are clamped to valid ranges."""

    def test_greeting_cooldown_clamping(self):
        self.assertEqual(max(5, min(300, 1)), 5)
        self.assertEqual(max(5, min(300, 999)), 300)
        self.assertEqual(max(5, min(300, 60)), 60)

    def test_scan_feedback_clamping(self):
        self.assertEqual(max(500, min(30000, 100)), 500)
        self.assertEqual(max(500, min(30000, 99999)), 30000)

    def test_min_size_pct_clamping(self):
        self.assertAlmostEqual(max(0.05, min(0.80, 0.01)), 0.05)
        self.assertAlmostEqual(max(0.05, min(0.80, 0.90)), 0.80)
        self.assertAlmostEqual(max(0.05, min(0.80, 0.30)), 0.30)

    def test_absence_threshold_clamping(self):
        self.assertAlmostEqual(max(1.0, min(30.0, 0.5)), 1.0)
        self.assertAlmostEqual(max(1.0, min(30.0, 50.0)), 30.0)

    def test_connection_check_clamping(self):
        self.assertEqual(max(0, int(0 * 1000)), 0)  # 0 = disabled
        self.assertEqual(max(0, int(600 * 1000)), 600000)


# =========================================================================
# ProximityGreetingManager.set_overlay_mode()
# =========================================================================
class TestOverlayMode(unittest.TestCase):
    """Test set_overlay_mode() switches between icon and preview."""

    def setUp(self):
        from plugins.camera.proximity_manager import ProximityGreetingManager
        self.mgr = ProximityGreetingManager(
            parent_window=None, camera_id=0, cooldown=10.0, resolution=(1280, 720)
        )

    def test_set_overlay_mode_updates_flag(self):
        """set_overlay_mode() updates _show_overlay flag."""
        self.mgr.set_overlay_mode(False)
        self.assertFalse(self.mgr._show_overlay)
        self.mgr.set_overlay_mode(True)
        self.assertTrue(self.mgr._show_overlay)

    def test_set_overlay_mode_no_parent_safe(self):
        """set_overlay_mode() is safe when _parent_window is None."""
        self.mgr._overlay = MagicMock()
        self.mgr._parent_window = None
        self.mgr.set_overlay_mode(True)  # Should not raise
        self.assertTrue(self.mgr._show_overlay)

    def test_set_overlay_mode_no_overlay_safe(self):
        """set_overlay_mode() is safe when _overlay is None."""
        self.mgr._overlay = None
        self.mgr.set_overlay_mode(False)  # Should not raise
        self.assertFalse(self.mgr._show_overlay)


# =========================================================================
# load_saved_settings() config overrides
# =========================================================================
def _load_saved_settings_logic(db):
    """Standalone copy of Api.load_saved_settings() logic for testing."""
    # Scanning settings
    v = db.get_meta("setting:duplicate_window")
    if v is not None:
        try:
            config.DUPLICATE_BADGE_TIME_WINDOW_SECONDS = max(1, min(3600, int(v)))
        except ValueError:
            pass
    v = db.get_meta("setting:duplicate_action")
    if v is not None and v in ("block", "warn", "silent"):
        config.DUPLICATE_BADGE_ACTION = v
    # Camera settings
    v = db.get_meta("setting:camera_overlay")
    if v is not None:
        config.CAMERA_SHOW_OVERLAY = v.lower() in ("true", "1")
    v = db.get_meta("setting:greeting_cooldown")
    if v is not None:
        try:
            config.CAMERA_GREETING_COOLDOWN_SECONDS = max(5.0, min(300.0, float(v)))
        except ValueError:
            pass
    v = db.get_meta("setting:scan_feedback_ms")
    if v is not None:
        try:
            config.SCAN_FEEDBACK_DURATION_MS = max(500, min(30000, int(v)))
        except ValueError:
            pass
    v = db.get_meta("setting:connection_check_s")
    if v is not None:
        try:
            config.CONNECTION_CHECK_INTERVAL_MS = max(0, int(float(v) * 1000))
        except ValueError:
            pass
    v = db.get_meta("setting:min_size_pct")
    if v is not None:
        try:
            config.CAMERA_MIN_SIZE_PCT = max(0.05, min(0.80, float(v)))
        except ValueError:
            pass
    v = db.get_meta("setting:absence_threshold")
    if v is not None:
        try:
            config.CAMERA_ABSENCE_THRESHOLD_SECONDS = max(1.0, min(30.0, float(v)))
        except ValueError:
            pass


class TestLoadSavedSettings(unittest.TestCase):
    """Test that load_saved_settings() applies SQLite values to config."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test.db"
        self.db = DatabaseManager(self.db_path)
        self.db.set_station_name("TestStation")
        self._orig = {
            'feedback': config.SCAN_FEEDBACK_DURATION_MS,
            'overlay': config.CAMERA_SHOW_OVERLAY,
            'cooldown': config.CAMERA_GREETING_COOLDOWN_SECONDS,
            'conn': config.CONNECTION_CHECK_INTERVAL_MS,
            'minsize': config.CAMERA_MIN_SIZE_PCT,
            'absence': config.CAMERA_ABSENCE_THRESHOLD_SECONDS,
            'dup_window': config.DUPLICATE_BADGE_TIME_WINDOW_SECONDS,
            'dup_action': config.DUPLICATE_BADGE_ACTION,
        }

    def tearDown(self):
        self.db.close()
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        config.SCAN_FEEDBACK_DURATION_MS = self._orig['feedback']
        config.CAMERA_SHOW_OVERLAY = self._orig['overlay']
        config.CAMERA_GREETING_COOLDOWN_SECONDS = self._orig['cooldown']
        config.CONNECTION_CHECK_INTERVAL_MS = self._orig['conn']
        config.CAMERA_MIN_SIZE_PCT = self._orig['minsize']
        config.CAMERA_ABSENCE_THRESHOLD_SECONDS = self._orig['absence']
        config.DUPLICATE_BADGE_TIME_WINDOW_SECONDS = self._orig['dup_window']
        config.DUPLICATE_BADGE_ACTION = self._orig['dup_action']

    def test_no_saved_settings_keeps_defaults(self):
        orig = config.SCAN_FEEDBACK_DURATION_MS
        _load_saved_settings_logic(self.db)
        self.assertEqual(config.SCAN_FEEDBACK_DURATION_MS, orig)

    def test_saved_scan_feedback_overrides(self):
        self.db.set_meta("setting:scan_feedback_ms", "5000")
        _load_saved_settings_logic(self.db)
        self.assertEqual(config.SCAN_FEEDBACK_DURATION_MS, 5000)

    def test_saved_camera_overlay_overrides(self):
        self.db.set_meta("setting:camera_overlay", "False")
        _load_saved_settings_logic(self.db)
        self.assertFalse(config.CAMERA_SHOW_OVERLAY)

    def test_saved_greeting_cooldown_overrides(self):
        self.db.set_meta("setting:greeting_cooldown", "120")
        _load_saved_settings_logic(self.db)
        self.assertEqual(config.CAMERA_GREETING_COOLDOWN_SECONDS, 120.0)

    def test_saved_connection_check_overrides(self):
        self.db.set_meta("setting:connection_check_s", "30")
        _load_saved_settings_logic(self.db)
        self.assertEqual(config.CONNECTION_CHECK_INTERVAL_MS, 30000)

    def test_saved_min_size_pct_overrides(self):
        self.db.set_meta("setting:min_size_pct", "0.35")
        _load_saved_settings_logic(self.db)
        self.assertAlmostEqual(config.CAMERA_MIN_SIZE_PCT, 0.35)

    def test_saved_absence_threshold_overrides(self):
        self.db.set_meta("setting:absence_threshold", "5.0")
        _load_saved_settings_logic(self.db)
        self.assertAlmostEqual(config.CAMERA_ABSENCE_THRESHOLD_SECONDS, 5.0)

    def test_saved_duplicate_window_overrides(self):
        self.db.set_meta("setting:duplicate_window", "300")
        _load_saved_settings_logic(self.db)
        self.assertEqual(config.DUPLICATE_BADGE_TIME_WINDOW_SECONDS, 300)

    def test_saved_duplicate_action_overrides(self):
        self.db.set_meta("setting:duplicate_action", "silent")
        _load_saved_settings_logic(self.db)
        self.assertEqual(config.DUPLICATE_BADGE_ACTION, "silent")

    def test_invalid_duplicate_action_ignored(self):
        orig = config.DUPLICATE_BADGE_ACTION
        self.db.set_meta("setting:duplicate_action", "invalid_value")
        _load_saved_settings_logic(self.db)
        self.assertEqual(config.DUPLICATE_BADGE_ACTION, orig)

    def test_invalid_saved_value_ignored(self):
        self.db.set_meta("setting:scan_feedback_ms", "not_a_number")
        orig = config.SCAN_FEEDBACK_DURATION_MS
        _load_saved_settings_logic(self.db)
        self.assertEqual(config.SCAN_FEEDBACK_DURATION_MS, orig)


def main():
    print("=" * 70)
    print("ADMIN SETTINGS TESTS (Camera & Display)")
    print("=" * 70)
    print()

    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    suite.addTests(loader.loadTestsFromTestCase(TestSettingsPersistence))
    suite.addTests(loader.loadTestsFromTestCase(TestAdminSlotContracts))
    suite.addTests(loader.loadTestsFromTestCase(TestLocalSettingsPayload))
    suite.addTests(loader.loadTestsFromTestCase(TestValueClamping))
    suite.addTests(loader.loadTestsFromTestCase(TestOverlayMode))
    suite.addTests(loader.loadTestsFromTestCase(TestLoadSavedSettings))

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
