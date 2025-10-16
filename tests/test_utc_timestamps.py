"""Test UTC timestamp generation for cloud sync compatibility."""

from datetime import datetime, timezone
from pathlib import Path
import sys
import tempfile

# Ensure UTF-8 encoding for console output
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from database import DatabaseManager, EmployeeRecord, ISO_TIMESTAMP_FORMAT


def test_timestamp_format():
    """Verify timestamps are in UTC format with Z suffix"""
    print("Testing UTC Timestamp Format\n")
    print(f"ISO_TIMESTAMP_FORMAT: {ISO_TIMESTAMP_FORMAT}")

    # Generate a timestamp
    timestamp = datetime.now(timezone.utc).strftime(ISO_TIMESTAMP_FORMAT)
    print(f"Generated timestamp: {timestamp}")

    # Verify format
    assert timestamp.endswith('Z'), "Timestamp must end with 'Z' for UTC"
    assert 'T' in timestamp, "Timestamp must have 'T' separator"
    assert len(timestamp) == 20, f"Timestamp should be 20 chars, got {len(timestamp)}"

    # Verify it can be parsed back
    try:
        parsed = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        print(f"✓ Parsed back successfully: {parsed}")
    except ValueError as e:
        raise AssertionError(f"Failed to parse timestamp: {e}")

    print("✓ Timestamp format is correct!\n")


def test_database_scan_storage():
    """Test that database stores scans with UTC timestamps"""
    print("Testing Database Scan Storage\n")

    # Create temporary database
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        db = DatabaseManager(db_path)

        # Create test employee
        employee = EmployeeRecord(
            legacy_id="TEST001",
            full_name="Test User",
            sl_l1_desc="Test Dept",
            position_desc="Tester"
        )
        db.bulk_insert_employees([employee])

        # Record a scan (no timestamp provided - should auto-generate)
        db.record_scan(
            badge_id="TEST001",
            station_name="Test Station",
            employee=employee
        )

        # Fetch and verify
        scans = db.fetch_all_scans()
        assert len(scans) == 1, f"Expected 1 scan, got {len(scans)}"

        scan = scans[0]
        print(f"Stored timestamp: {scan.scanned_at}")

        # Verify format
        assert scan.scanned_at.endswith('Z'), f"Stored timestamp must end with 'Z', got: {scan.scanned_at}"
        assert 'T' in scan.scanned_at, "Stored timestamp must have 'T' separator"

        print(f"✓ Badge ID: {scan.badge_id}")
        print(f"✓ Station: {scan.station_name}")
        print(f"✓ Timestamp: {scan.scanned_at}")
        print(f"✓ Format: Correct UTC with Z suffix!\n")

        db.close()


def test_cloud_api_compatibility():
    """Test that our timestamps are compatible with cloud API format"""
    print("Testing Cloud API Compatibility\n")

    timestamp = datetime.now(timezone.utc).strftime(ISO_TIMESTAMP_FORMAT)
    print(f"Local format: {timestamp}")

    # Cloud API expects ISO8601 with timezone
    # Our format: 2025-10-15T12:30:45Z
    # Should be directly compatible!

    # Verify it matches ISO8601 date-time format
    try:
        # This is what the cloud API will do
        dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        print(f"✓ Cloud can parse: {dt}")
        print(f"✓ Timezone aware: {dt.tzinfo is not None}")
        print("✓ Compatible with cloud API!\n")
    except Exception as e:
        raise AssertionError(f"Cloud API would reject this format: {e}")


if __name__ == "__main__":
    print("="* 60)
    print("UTC Timestamp Tests for Cloud Sync")
    print("=" * 60 + "\n")

    try:
        test_timestamp_format()
        test_database_scan_storage()
        test_cloud_api_compatibility()

        print("=" * 60)
        print("✅ All tests passed!")
        print("=" * 60)
    except AssertionError as e:
        print("=" * 60)
        print(f"❌ Test failed: {e}")
        print("=" * 60)
        sys.exit(1)
