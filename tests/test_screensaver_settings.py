"""Idle-screensaver admin settings: real Api slots + load_saved_settings()."""
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("CLOUD_API_KEY", "test-api-key")
os.environ.setdefault("CLOUD_API_URL", "http://test.example.com")

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import config
from database import DatabaseManager
from main import Api


class ScreensaverSettingsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.db = DatabaseManager(Path(self.tmp) / "t.db")
        self.db.set_station_name("T")
        self.api = SimpleNamespace(_service=SimpleNamespace(_db=self.db))
        self.api._save_setting = lambda k, v: self.db.set_meta(f"setting:{k}", v)
        self._orig = (config.SCREENSAVER_ENABLED, config.SCREENSAVER_IDLE_SECONDS,
                      config.SCREENSAVER_MUTED, config.SCREENSAVER_CONTENT, config.SCREENSAVER_CAMERA,
                      config.HOLD_ENABLED, config.HOLD_CONTENT, config.HOLD_SCANS)

    def tearDown(self):
        (config.SCREENSAVER_ENABLED, config.SCREENSAVER_IDLE_SECONDS,
         config.SCREENSAVER_MUTED, config.SCREENSAVER_CONTENT, config.SCREENSAVER_CAMERA,
         config.HOLD_ENABLED, config.HOLD_CONTENT, config.HOLD_SCANS) = self._orig
        self.db.close()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _restart(self):
        """Reset config to defaults then reload from SQLite, like an app restart."""
        config.SCREENSAVER_ENABLED = False
        config.SCREENSAVER_IDLE_SECONDS = 60
        config.SCREENSAVER_MUTED = False
        config.SCREENSAVER_CONTENT = "video"
        config.SCREENSAVER_CAMERA = "wake"
        config.HOLD_ENABLED = False
        config.HOLD_CONTENT = "image"
        config.HOLD_SCANS = "accept"
        Api.load_saved_settings(self.api)

    def test_all_settings_survive_restart(self):
        Api.admin_set_screensaver(self.api, True)
        Api.admin_set_screensaver_idle(self.api, 90)
        Api.admin_set_screensaver_muted(self.api, True)
        Api.admin_set_screensaver_content(self.api, "image")
        Api.admin_set_screensaver_camera(self.api, "sound")
        Api.admin_set_hold(self.api, True)
        Api.admin_set_hold_content(self.api, "video")
        Api.admin_set_hold_scans(self.api, "block")
        self._restart()
        self.assertTrue(config.SCREENSAVER_ENABLED)
        self.assertEqual(config.SCREENSAVER_IDLE_SECONDS, 90)
        self.assertTrue(config.SCREENSAVER_MUTED)
        self.assertEqual(config.SCREENSAVER_CONTENT, "image")
        self.assertEqual(config.SCREENSAVER_CAMERA, "sound")
        self.assertTrue(config.HOLD_ENABLED)
        self.assertEqual(config.HOLD_CONTENT, "video")
        self.assertEqual(config.HOLD_SCANS, "block")

    def test_idle_seconds_is_clamped(self):
        self.assertEqual(Api.admin_set_screensaver_idle(self.api, 1)["value"], 5)
        self.assertEqual(Api.admin_set_screensaver_idle(self.api, 99999)["value"], 600)

    def test_corrupt_saved_idle_value_is_ignored(self):
        self.db.set_meta("setting:screensaver_idle_seconds", "banana")
        self._restart()
        self.assertEqual(config.SCREENSAVER_IDLE_SECONDS, 60)

    def test_invalid_choices_are_rejected(self):
        self.assertFalse(Api.admin_set_screensaver_content(self.api, "party")["ok"])
        self.assertFalse(Api.admin_set_screensaver_camera(self.api, "loud")["ok"])
        self.assertFalse(Api.admin_set_hold_content(self.api, "gif")["ok"])
        self.assertFalse(Api.admin_set_hold_scans(self.api, "maybe")["ok"])
        self.assertIsNone(self.db.get_meta("setting:screensaver_content"))
        self.assertIsNone(self.db.get_meta("setting:hold_scans"))

    def test_corrupt_saved_choices_are_ignored(self):
        for k in ("screensaver_content", "screensaver_camera", "hold_content", "hold_scans"):
            self.db.set_meta(f"setting:{k}", "garbage")
        self._restart()
        self.assertEqual(config.SCREENSAVER_CONTENT, "video")
        self.assertEqual(config.SCREENSAVER_CAMERA, "wake")
        self.assertEqual(config.HOLD_CONTENT, "image")
        self.assertEqual(config.HOLD_SCANS, "accept")

    def test_released_hold_stays_released_after_restart(self):
        """Esc saves hold=False; a restart must not bring the hold screen back."""
        config.HOLD_ENABLED = True
        Api.admin_set_hold(self.api, True)
        Api.admin_set_hold(self.api, False)
        config.HOLD_ENABLED = True          # e.g. .env says HOLD_ENABLED=True
        Api.load_saved_settings(self.api)
        self.assertFalse(config.HOLD_ENABLED)

    def test_hold_survives_restart_until_released(self):
        Api.admin_set_hold(self.api, True)
        self._restart()
        self.assertTrue(config.HOLD_ENABLED)

    def test_defaults_when_nothing_saved(self):
        self._restart()
        self.assertFalse(config.SCREENSAVER_ENABLED)
        self.assertFalse(config.SCREENSAVER_MUTED)
        self.assertEqual(config.SCREENSAVER_CONTENT, "video")
        self.assertEqual(config.SCREENSAVER_CAMERA, "wake")
        self.assertFalse(config.HOLD_ENABLED)
        self.assertEqual(config.HOLD_CONTENT, "image")
        self.assertEqual(config.HOLD_SCANS, "accept")


if __name__ == "__main__":
    unittest.main()
