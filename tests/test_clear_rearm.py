"""Clear ALL / remote clear: re-arm the hold screen, stay reliable.

- A clear returns the station to the event-ready state from .env: hold screen up with
  .env's HOLD_SCANS (an Esc release saved during testing is overridden).
- No upload while the cloud has a newer clear epoch than this station (an offline
  station must not re-upload pre-clear test scans when it reconnects).
- A failing local clear never leaves sync paused.
- The roster summary is re-sent after a clear.
"""
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from types import MethodType, SimpleNamespace
from unittest.mock import MagicMock, patch

os.environ.setdefault("CLOUD_API_KEY", "test-api-key")
os.environ.setdefault("CLOUD_API_URL", "http://test.example.com")

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import pytest  # noqa: E402
pytest.importorskip("PyQt6")  # CI installs no Qt; these run locally

import requests  # noqa: E402

import config  # noqa: E402
from database import DatabaseManager, ScanRecord  # noqa: E402
from main import Api  # noqa: E402
from sync import SyncService  # noqa: E402


def make_api(db, hold_enabled_default=True, hold_scans_default="block", sync_service=None):
    """A stand-in carrying just what the clear paths use, with Api's real methods bound."""
    api = SimpleNamespace(
        _service=SimpleNamespace(_db=db, export_scans=lambda: {"ok": True}),
        _config_defaults={"hold_enabled": hold_enabled_default, "hold_scans": hold_scans_default},
        _roster_synced=True,
        _sync_service=sync_service,
        _sync_coordinator=MagicMock(),
        _auto_sync_manager=MagicMock(),
        hold_rearmed=MagicMock(),
        _notify_remote_clear=MagicMock(),
        _reset_manual_sync_state=MagicMock(),
    )
    api._save_setting = lambda k, v: db.set_meta(f"setting:{k}", v)
    for name in ("_after_clear", "_rearm_hold_after_clear", "_set_local_clear_epoch"):
        setattr(api, name, MethodType(getattr(Api, name), api))
    return api


class _Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.db = DatabaseManager(Path(self.tmp) / "t.db")
        self.db.set_station_name("Gate A")
        self._orig = (config.HOLD_ENABLED, config.HOLD_SCANS, config.CLOUD_READ_ONLY)
        config.CLOUD_READ_ONLY = False
        # During testing the hold was released with Esc and switched to accept
        config.HOLD_ENABLED, config.HOLD_SCANS = False, "accept"
        self.db.set_meta("setting:hold_enabled", "False")
        self.db.set_meta("setting:hold_scans", "accept")

    def tearDown(self):
        config.HOLD_ENABLED, config.HOLD_SCANS, config.CLOUD_READ_ONLY = self._orig
        self.db.close()
        shutil.rmtree(self.tmp, ignore_errors=True)


class RearmHoldTests(_Base):
    def test_clear_rearms_hold_from_env_and_saves_it(self):
        api = make_api(self.db)
        self.assertTrue(Api._after_clear(api))
        self.assertEqual((config.HOLD_ENABLED, config.HOLD_SCANS), (True, "block"))
        # Saved, so a restart keeps the hold up
        self.assertEqual(self.db.get_meta("setting:hold_enabled"), "True")
        self.assertEqual(self.db.get_meta("setting:hold_scans"), "block")
        api.hold_rearmed.emit.assert_called_once_with({"hold": True, "holdScans": "block"})

    def test_no_hold_in_env_leaves_hold_alone(self):
        api = make_api(self.db, hold_enabled_default=False)
        self.assertFalse(Api._after_clear(api))
        self.assertEqual((config.HOLD_ENABLED, config.HOLD_SCANS), (False, "accept"))
        self.assertEqual(self.db.get_meta("setting:hold_enabled"), "False")
        api.hold_rearmed.emit.assert_not_called()

    def test_clear_resends_roster_summary(self):
        api = make_api(self.db, hold_enabled_default=False)
        Api._after_clear(api)
        self.assertFalse(api._roster_synced)


class RemoteClearHandlerTests(_Base):
    def _sync(self, cloud_epoch):
        svc = SyncService(self.db, "http://test.example.com", "k")
        svc.last_clear_epoch = cloud_epoch
        svc.send_heartbeat = MagicMock()
        return svc

    def test_remote_clear_clears_rearms_and_skips_alert(self):
        svc = self._sync("epoch-2")
        api = make_api(self.db, sync_service=svc)
        Api._set_local_clear_epoch(api, "epoch-1")
        self.db.record_scan("B1", "Gate A", None, "2026-11-26T08:00:00Z")

        Api._handle_clear_epoch_and_heartbeat_slot(api)

        self.assertEqual(self.db.count_scans_total(), 0)
        self.assertEqual(self.db.get_meta("last_clear_epoch"), "epoch-2")
        self.assertEqual(svc.local_clear_epoch, "epoch-2")
        self.assertTrue(config.HOLD_ENABLED)
        api._notify_remote_clear.assert_called_once_with(show_alert=False)
        api._sync_coordinator.resume.assert_called_once()
        api._auto_sync_manager.start.assert_called_once()

    def test_alert_shown_when_hold_not_rearmed(self):
        api = make_api(self.db, hold_enabled_default=False, sync_service=self._sync("epoch-2"))
        Api._set_local_clear_epoch(api, "epoch-1")
        Api._handle_clear_epoch_and_heartbeat_slot(api)
        api._notify_remote_clear.assert_called_once_with(show_alert=True)

    def test_failed_local_clear_still_resumes_sync(self):
        api = make_api(self.db, sync_service=self._sync("epoch-2"))
        Api._set_local_clear_epoch(api, "epoch-1")
        api._service._db = MagicMock(wraps=self.db)
        api._service._db.clear_all_scans.side_effect = RuntimeError("disk full")

        with self.assertRaises(RuntimeError):
            Api._handle_clear_epoch_and_heartbeat_slot(api)

        api._sync_coordinator.resume.assert_called_once()
        api._auto_sync_manager.start.assert_called_once()
        # Not marked as cleared, so the next health check tries again
        self.assertEqual(self.db.get_meta("last_clear_epoch"), "epoch-1")

    def test_first_connection_adopts_cloud_epoch(self):
        svc = self._sync("epoch-1")
        api = make_api(self.db, sync_service=svc)
        Api._handle_clear_epoch_and_heartbeat_slot(api)
        self.assertEqual(svc.local_clear_epoch, "epoch-1")
        api._notify_remote_clear.assert_not_called()


class UploadGuardTests(_Base):
    def _scans(self):
        return [ScanRecord(id=i, badge_id=f"B{i}", station_name="Gate A",
                           scanned_at="2026-11-26T08:00:00Z", employee_full_name=None,
                           legacy_id=None, sl_l1_desc=None, position_desc=None)
                for i in (1, 2)]

    def _svc(self, local, cloud):
        svc = SyncService(self.db, "http://test.example.com", "k")
        svc.local_clear_epoch, svc.last_clear_epoch = local, cloud
        return svc

    def test_no_upload_while_remote_clear_pending(self):
        svc = self._svc("epoch-1", "epoch-2")
        with patch("sync.requests.post") as post:
            result = svc.sync_scan_batch_network_only(self._scans(), "Gate A")
        post.assert_not_called()
        self.assertEqual(result["pending_ids"], [1, 2])
        self.assertEqual((result["synced_ids"], result["failed_ids"]), ([], []))

    def test_uploads_when_epochs_match_or_unknown(self):
        for local, cloud in (("epoch-1", "epoch-1"), (None, "epoch-1"), ("epoch-1", None)):
            svc = self._svc(local, cloud)
            with patch("sync.requests.post") as post, patch("sync.time.sleep"):
                post.side_effect = requests.exceptions.ConnectionError("offline")
                svc.sync_scan_batch_network_only(self._scans(), "Gate A")
            self.assertTrue(post.called, f"local={local} cloud={cloud}")


if __name__ == "__main__":
    unittest.main()
