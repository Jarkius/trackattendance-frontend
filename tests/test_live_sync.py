"""Tests for Live Sync methods: check_duplicate_cloud and sync_single_scan."""

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

# Force test env before config loads
os.environ["CLOUD_READ_ONLY"] = "False"
os.environ["LIVE_SYNC_ENABLED"] = "True"

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sync import SyncService


class FakeScanRecord:
    """Minimal ScanRecord for testing."""

    def __init__(self, **kwargs):
        self.id = kwargs.get("id", 1)
        self.badge_id = kwargs.get("badge_id", "BADGE001")
        self.station_name = kwargs.get("station_name", "Station-A")
        self.scanned_at = kwargs.get("scanned_at", "2026-03-13T10:00:00")
        self.sl_l1_desc = kwargs.get("sl_l1_desc", "Engineering")
        self.scan_source = kwargs.get("scan_source", "qr")


def _make_service():
    db = MagicMock()
    svc = SyncService(db=db, api_url="https://test.api", api_key="test-key")
    return svc, db


# ── check_duplicate_cloud ──


class TestCheckDuplicateCloud:
    def test_returns_duplicate_when_found(self):
        svc, _ = _make_service()
        mock_resp = MagicMock(status_code=200)
        mock_resp.json.return_value = {
            "duplicate": True,
            "station_name": "Station-B",
            "scanned_at": "2026-03-13T09:59:00",
        }
        with patch("sync.requests.get", return_value=mock_resp) as mock_get:
            result = svc.check_duplicate_cloud("BADGE001", "Station-A")
            assert result["duplicate"] is True
            assert result["station_name"] == "Station-B"
            # Verify correct params
            call_kwargs = mock_get.call_args
            assert call_kwargs[1]["params"]["badge_id"] == "BADGE001"
            assert call_kwargs[1]["params"]["exclude_station"] == "Station-A"

    def test_returns_no_duplicate(self):
        svc, _ = _make_service()
        mock_resp = MagicMock(status_code=200)
        mock_resp.json.return_value = {"duplicate": False}
        with patch("sync.requests.get", return_value=mock_resp):
            result = svc.check_duplicate_cloud("BADGE001", "Station-A")
            assert result["duplicate"] is False

    def test_fail_open_on_http_error(self):
        svc, _ = _make_service()
        mock_resp = MagicMock(status_code=500)
        with patch("sync.requests.get", return_value=mock_resp):
            result = svc.check_duplicate_cloud("BADGE001", "Station-A")
            assert result["duplicate"] is False
            assert "HTTP 500" in result["error"]

    def test_fail_open_on_timeout(self):
        svc, _ = _make_service()
        import requests

        with patch("sync.requests.get", side_effect=requests.Timeout("timed out")):
            result = svc.check_duplicate_cloud("BADGE001", "Station-A", timeout=0.1)
            assert result["duplicate"] is False
            assert "timed out" in result["error"]

    def test_fail_open_on_connection_error(self):
        svc, _ = _make_service()
        import requests

        with patch(
            "sync.requests.get",
            side_effect=requests.ConnectionError("no connection"),
        ):
            result = svc.check_duplicate_cloud("BADGE001", "Station-A")
            assert result["duplicate"] is False
            assert "connection" in result["error"].lower()

    @patch.dict(os.environ, {"CLOUD_READ_ONLY": "True"})
    def test_skips_when_read_only(self):
        svc, _ = _make_service()
        # Reimport config to pick up new env
        import importlib
        import config

        importlib.reload(config)
        try:
            result = svc.check_duplicate_cloud("BADGE001", "Station-A")
            assert result["duplicate"] is False
            assert result.get("skipped") is True
        finally:
            os.environ["CLOUD_READ_ONLY"] = "False"
            importlib.reload(config)

    def test_custom_window_minutes(self):
        svc, _ = _make_service()
        mock_resp = MagicMock(status_code=200)
        mock_resp.json.return_value = {"duplicate": False}
        with patch("sync.requests.get", return_value=mock_resp) as mock_get:
            svc.check_duplicate_cloud("BADGE001", "Station-A", window_minutes=10)
            assert mock_get.call_args[1]["params"]["window_minutes"] == "10"


# ── sync_single_scan ──


class TestSyncSingleScan:
    def test_successful_sync(self):
        svc, db = _make_service()
        scan = FakeScanRecord()
        mock_resp = MagicMock(status_code=200)
        with patch("sync.requests.post", return_value=mock_resp):
            result = svc.sync_single_scan(scan)
            assert result["ok"] is True
            # Should NOT call mark_scans_as_synced (threading fix)
            db.mark_scans_as_synced.assert_not_called()

    def test_does_not_mark_synced_on_success(self):
        """Explicit test: sync_single_scan must NOT touch SQLite (threading safety)."""
        svc, db = _make_service()
        scan = FakeScanRecord()
        mock_resp = MagicMock(status_code=200)
        with patch("sync.requests.post", return_value=mock_resp):
            svc.sync_single_scan(scan)
            db.mark_scans_as_synced.assert_not_called()

    def test_http_error_returns_failure(self):
        svc, _ = _make_service()
        scan = FakeScanRecord()
        mock_resp = MagicMock(status_code=502)
        with patch("sync.requests.post", return_value=mock_resp):
            result = svc.sync_single_scan(scan)
            assert result["ok"] is False
            assert "502" in result["error"]

    def test_network_error_returns_failure(self):
        svc, _ = _make_service()
        scan = FakeScanRecord()
        import requests

        with patch(
            "sync.requests.post", side_effect=requests.ConnectionError("offline")
        ):
            result = svc.sync_single_scan(scan)
            assert result["ok"] is False
            assert "offline" in result["error"]

    def test_sends_correct_payload(self):
        svc, _ = _make_service()
        scan = FakeScanRecord(
            badge_id="B123", station_name="S1", scanned_at="2026-01-01T00:00:00"
        )
        mock_resp = MagicMock(status_code=200)
        with patch("sync.requests.post", return_value=mock_resp) as mock_post:
            svc.sync_single_scan(scan)
            payload = mock_post.call_args[1]["json"]
            event = payload["events"][0]
            assert event["badge_id"] == "B123"
            assert event["station_name"] == "S1"
            assert "idempotency_key" in event

    @patch.dict(os.environ, {"CLOUD_READ_ONLY": "True"})
    def test_skips_when_read_only(self):
        svc, _ = _make_service()
        import importlib
        import config

        importlib.reload(config)
        try:
            result = svc.sync_single_scan(FakeScanRecord())
            assert result["ok"] is False
            assert result.get("skipped") is True
        finally:
            os.environ["CLOUD_READ_ONLY"] = "False"
            importlib.reload(config)
