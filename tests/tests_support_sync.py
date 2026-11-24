"""Small shared builders for sync tests (network-only paths, no SQLite)."""

from unittest.mock import Mock

from database import ScanRecord
from sync import SyncService


def make_scan(scan_id, badge_id=None):
    return ScanRecord(
        id=scan_id, badge_id=badge_id or f"B{scan_id}",
        scanned_at="2026-11-24T10:00:00Z", station_name="TestStation",
        employee_full_name=None, legacy_id=None, sl_l1_desc=None,
        position_desc=None, email=None, scan_source="badge",
        sync_status="pending", synced_at=None, sync_error=None,
    )


class _NoDb:
    def __getattr__(self, name):
        raise AssertionError(f"network-only path touched db.{name}")


def service_without_db():
    return SyncService(db=_NoDb(), api_url="http://test.example.com", api_key="k")


def mock_response(status, json_data=None):
    r = Mock()
    r.status_code = status
    r.text = ""
    r.encoding = "utf-8"
    r.elapsed.total_seconds.return_value = 0.01
    r.json.return_value = json_data if json_data is not None else {}
    return r
