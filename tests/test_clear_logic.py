#!/usr/bin/env python3
"""
Tests for multi-station clear logic.

Validates:
- clear_all_scans() preserves station name
- get_meta / set_meta key-value storage
- count_scans_total()
- clear_epoch detection scenarios (first-time, mismatch, match, no epoch)
- sync.py clear/heartbeat/status API calls

Run: python tests/test_clear_logic.py
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Set required environment variables BEFORE importing config
os.environ.setdefault("CLOUD_API_KEY", "test-api-key-for-testing")
os.environ.setdefault("CLOUD_API_URL", "http://test.example.com")

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from database import DatabaseManager, EmployeeRecord, ISO_TIMESTAMP_FORMAT
from datetime import datetime, timezone


def _make_employee(name="Test User"):
    return EmployeeRecord(
        legacy_id="L001",
        full_name=name,
        sl_l1_desc="Engineering",
        position_desc="Engineer",
        email="test@example.com",
    )


def _now_ts():
    return datetime.now(timezone.utc).strftime(ISO_TIMESTAMP_FORMAT)


class TestClearPreservesStationName(unittest.TestCase):
    """Verify clear_all_scans() keeps station name intact."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test.db"
        self.db = DatabaseManager(self.db_path)
        self.db.set_station_name("Gate A")

    def tearDown(self):
        self.db.close()

    def test_station_name_survives_clear(self):
        """Station name must persist after clear_all_scans()."""
        self.db.record_scan("BADGE001", "Gate A", _make_employee(), _now_ts())
        self.db.record_scan("BADGE002", "Gate A", _make_employee(), _now_ts())
        assert self.db.count_scans_total() == 2

        deleted = self.db.clear_all_scans()
        assert deleted == 2
        assert self.db.get_station_name() == "Gate A"
        assert self.db.count_scans_total() == 0

    def test_clear_empty_db_preserves_station(self):
        """Clearing with zero scans still preserves station name."""
        deleted = self.db.clear_all_scans()
        assert deleted == 0
        assert self.db.get_station_name() == "Gate A"

    def test_multiple_clears_preserve_station(self):
        """Multiple successive clears don't corrupt station name."""
        for _ in range(3):
            self.db.record_scan("BADGE001", "Gate A", _make_employee(), _now_ts())
            self.db.clear_all_scans()
        assert self.db.get_station_name() == "Gate A"


class TestMetaStorage(unittest.TestCase):
    """Test local key-value meta storage for clear_epoch tracking."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test.db"
        self.db = DatabaseManager(self.db_path)

    def tearDown(self):
        self.db.close()

    def test_get_meta_nonexistent_returns_none(self):
        assert self.db.get_meta("last_clear_epoch") is None

    def test_set_and_get_meta(self):
        self.db.set_meta("last_clear_epoch", "2026-03-01T10:00:00Z")
        assert self.db.get_meta("last_clear_epoch") == "2026-03-01T10:00:00Z"

    def test_set_meta_overwrites(self):
        self.db.set_meta("last_clear_epoch", "old")
        self.db.set_meta("last_clear_epoch", "new")
        assert self.db.get_meta("last_clear_epoch") == "new"

    def test_meta_survives_clear(self):
        """clear_all_scans() does NOT wipe roster_meta."""
        self.db.set_meta("last_clear_epoch", "2026-03-01T10:00:00Z")
        self.db.clear_all_scans()
        assert self.db.get_meta("last_clear_epoch") == "2026-03-01T10:00:00Z"

    def test_multiple_keys(self):
        self.db.set_meta("key_a", "value_a")
        self.db.set_meta("key_b", "value_b")
        assert self.db.get_meta("key_a") == "value_a"
        assert self.db.get_meta("key_b") == "value_b"


class TestCountScansTotal(unittest.TestCase):
    """Test count_scans_total() method."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test.db"
        self.db = DatabaseManager(self.db_path)
        self.db.set_station_name("TestStation")

    def tearDown(self):
        self.db.close()

    def test_empty_db_returns_zero(self):
        assert self.db.count_scans_total() == 0

    def test_counts_all_scans(self):
        emp = _make_employee()
        self.db.record_scan("B001", "TestStation", emp, _now_ts())
        self.db.record_scan("B002", "TestStation", emp, _now_ts())
        self.db.record_scan("B003", "TestStation", emp, _now_ts())
        assert self.db.count_scans_total() == 3

    def test_count_after_clear(self):
        self.db.record_scan("B001", "TestStation", _make_employee(), _now_ts())
        self.db.clear_all_scans()
        assert self.db.count_scans_total() == 0


class TestClearEpochDetection(unittest.TestCase):
    """
    Test the clear_epoch comparison logic that runs on every health check.
    Simulates _handle_clear_epoch_and_heartbeat scenarios without Qt.
    """

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test.db"
        self.db = DatabaseManager(self.db_path)
        self.db.set_station_name("Gate B")

    def tearDown(self):
        self.db.close()

    def _simulate_epoch_check(self, cloud_epoch):
        """
        Reproduce the logic from _handle_clear_epoch_and_heartbeat
        without needing Qt or network. Returns action taken.
        """
        local_epoch = self.db.get_meta("last_clear_epoch")

        if local_epoch is None and cloud_epoch:
            self.db.set_meta("last_clear_epoch", cloud_epoch)
            return "initialized"
        elif cloud_epoch and local_epoch and cloud_epoch != local_epoch:
            self.db.clear_all_scans()
            self.db.set_meta("last_clear_epoch", cloud_epoch)
            return "cleared"
        else:
            return "no_action"

    def test_first_time_station_initializes_no_clear(self):
        """First-time station with no local epoch initializes without clearing."""
        self.db.record_scan("B001", "Gate B", _make_employee(), _now_ts())

        action = self._simulate_epoch_check("2026-03-01T10:00:00Z")

        assert action == "initialized"
        assert self.db.get_meta("last_clear_epoch") == "2026-03-01T10:00:00Z"
        assert self.db.count_scans_total() == 1  # NOT cleared
        assert self.db.get_station_name() == "Gate B"

    def test_matching_epoch_no_action(self):
        """When epochs match, nothing happens."""
        self.db.set_meta("last_clear_epoch", "2026-03-01T10:00:00Z")
        self.db.record_scan("B001", "Gate B", _make_employee(), _now_ts())

        action = self._simulate_epoch_check("2026-03-01T10:00:00Z")

        assert action == "no_action"
        assert self.db.count_scans_total() == 1  # Scans preserved

    def test_epoch_mismatch_triggers_clear(self):
        """When cloud epoch changes, local data is cleared."""
        self.db.set_meta("last_clear_epoch", "2026-03-01T10:00:00Z")
        self.db.record_scan("B001", "Gate B", _make_employee(), _now_ts())
        self.db.record_scan("B002", "Gate B", _make_employee(), _now_ts())

        action = self._simulate_epoch_check("2026-03-01T15:00:00Z")

        assert action == "cleared"
        assert self.db.count_scans_total() == 0
        assert self.db.get_meta("last_clear_epoch") == "2026-03-01T15:00:00Z"
        assert self.db.get_station_name() == "Gate B"

    def test_no_cloud_epoch_no_action(self):
        """When cloud has no epoch (never cleared), nothing happens."""
        assert self._simulate_epoch_check(None) == "no_action"
        assert self._simulate_epoch_check("") == "no_action"

    def test_no_accidental_double_clear(self):
        """After clearing, same epoch on next check does nothing."""
        self.db.set_meta("last_clear_epoch", "old")
        self.db.record_scan("B001", "Gate B", _make_employee(), _now_ts())

        action1 = self._simulate_epoch_check("new_epoch")
        assert action1 == "cleared"
        assert self.db.count_scans_total() == 0

        # Add new scan after clear
        self.db.record_scan("B002", "Gate B", _make_employee(), _now_ts())
        assert self.db.count_scans_total() == 1

        # Second check with same epoch: no action
        action2 = self._simulate_epoch_check("new_epoch")
        assert action2 == "no_action"
        assert self.db.count_scans_total() == 1  # New scan preserved

    def test_station_name_survives_remote_clear(self):
        """Remote clear via epoch detection preserves station name."""
        self.db.set_meta("last_clear_epoch", "epoch_1")
        self.db.record_scan("B001", "Gate B", _make_employee(), _now_ts())
        self._simulate_epoch_check("epoch_2")
        assert self.db.get_station_name() == "Gate B"

    def test_meta_survives_remote_clear(self):
        """Other meta keys survive remote clear."""
        self.db.set_meta("last_clear_epoch", "old")
        self.db.set_meta("custom_key", "custom_value")
        self._simulate_epoch_check("new")
        assert self.db.get_meta("last_clear_epoch") == "new"
        assert self.db.get_meta("custom_key") == "custom_value"

    def test_rapid_epoch_changes(self):
        """Multiple rapid epoch changes don't corrupt state."""
        self.db.set_meta("last_clear_epoch", "epoch_0")
        for i in range(1, 6):
            self.db.record_scan(f"B{i:03}", "Gate B", _make_employee(), _now_ts())
            action = self._simulate_epoch_check(f"epoch_{i}")
            assert action == "cleared"
            assert self.db.count_scans_total() == 0
        assert self.db.get_meta("last_clear_epoch") == "epoch_5"
        assert self.db.get_station_name() == "Gate B"


class TestSyncClearStation(unittest.TestCase):
    """Test sync.py clear_station_scans(), heartbeat, and status functions."""

    def _make_sync(self):
        from sync import SyncService
        sync = SyncService.__new__(SyncService)
        sync.api_url = "http://test.example.com"
        sync.api_key = "test-key"
        sync.connection_timeout = 10
        return sync

    def test_clear_station_scans_sends_correct_request(self):
        sync = self._make_sync()
        with patch("requests.delete") as mock_delete:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"ok": True, "deleted": 5}
            mock_delete.return_value = mock_response

            result = sync.clear_station_scans("Gate A")

            mock_delete.assert_called_once()
            call_args = mock_delete.call_args
            assert "clear-station" in call_args[0][0]
            assert call_args[1]["params"]["station"] == "Gate A"
            assert call_args[1]["headers"]["X-Confirm-Delete"] == "DELETE STATION SCANS"
            assert result["ok"] is True

    def test_send_heartbeat_sends_correct_payload(self):
        sync = self._make_sync()
        with patch("requests.post") as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_post.return_value = mock_response

            result = sync.send_heartbeat("Gate A", "2026-03-01T10:00:00Z", 42)

            mock_post.assert_called_once()
            call_args = mock_post.call_args
            assert "heartbeat" in call_args[0][0]
            body = call_args[1]["json"]
            assert body["station_name"] == "Gate A"
            assert body["last_clear_epoch"] == "2026-03-01T10:00:00Z"
            assert body["local_scan_count"] == 42
            assert result is True

    def test_get_station_status_returns_stations(self):
        sync = self._make_sync()
        with patch("requests.get") as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "stations": [
                    {"station_name": "Gate A", "status": "ready", "seconds_ago": 5},
                    {"station_name": "Gate B", "status": "pending", "seconds_ago": 30},
                ],
                "clear_epoch": "2026-03-01T10:00:00Z",
            }
            mock_get.return_value = mock_response

            result = sync.get_station_status()

            assert len(result["stations"]) == 2
            assert result["stations"][0]["status"] == "ready"

    def test_heartbeat_failure_returns_false(self):
        sync = self._make_sync()
        with patch("requests.post") as mock_post:
            mock_post.side_effect = Exception("network error")
            result = sync.send_heartbeat("Gate A", None, 0)
            assert result is False

    def test_clear_station_failure_returns_error(self):
        sync = self._make_sync()
        with patch("requests.delete") as mock_delete:
            mock_delete.side_effect = Exception("network error")
            result = sync.clear_station_scans("Gate A")
            assert result["ok"] is False

    def test_get_station_status_failure_returns_error(self):
        sync = self._make_sync()
        with patch("requests.get") as mock_get:
            mock_get.side_effect = Exception("network error")
            result = sync.get_station_status()
            assert "error" in result


if __name__ == "__main__":
    unittest.main()
