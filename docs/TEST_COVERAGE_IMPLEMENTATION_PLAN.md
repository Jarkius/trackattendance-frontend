# Test Coverage Implementation Plan

This document contains detailed GitHub issues for improving test coverage in the TrackAttendance Frontend codebase.

**Generated**: 2026-02-02
**Analysis Session**: [claude/analyze-test-coverage-ROZjv](https://claude.ai/code/session_018RqH4i5cABz8s3guubM1iy)

---

## Overview

| Priority | Count | Description |
|----------|-------|-------------|
| P0 - Critical | 4 | Would break production if untested code fails |
| P1 - High | 4 | Important functionality gaps |
| P2 - Medium | 4 | Quality improvements |
| P3 - Long-term | 4 | Future enhancements |

**Total Issues**: 16

---

## Labels to Create

Before creating issues, ensure these labels exist:

| Label | Color | Description |
|-------|-------|-------------|
| `testing` | `#7057ff` | Test-related issues |
| `P0-critical` | `#b60205` | Critical priority |
| `P1-high` | `#d93f0b` | High priority |
| `P2-medium` | `#fbca04` | Medium priority |
| `P3-low` | `#0e8a16` | Low priority |
| `sync` | `#1d76db` | Sync functionality |
| `database` | `#5319e7` | Database layer |
| `ui` | `#c5def5` | User interface |
| `config` | `#f9d0c4` | Configuration |

---

## P0 - Critical Priority Issues

### Issue #1: Add Sync Retry Logic Tests

**Title**: `[Testing] Add comprehensive tests for sync retry logic and error handling`

**Labels**: `testing`, `P0-critical`, `sync`

**Body**:
```markdown
## Summary

The sync retry logic in `sync.py` (lines 233-350) handles all network error scenarios but has zero test coverage. This is critical because network failures could cause data loss if the retry logic fails silently.

## Current State

- `_sync_one_batch()` implements exponential backoff retry
- Handles: HTTP 401, 4xx, 5xx, 429, timeouts, connection errors
- No tests exist for any error path

## Scope

Create `tests/test_sync_retry.py` with tests for:

### Error Type Tests
- [ ] HTTP 401 Unauthorized - should NOT retry, mark permanent failure
- [ ] HTTP 403 Forbidden - should NOT retry, mark permanent failure
- [ ] HTTP 400 Bad Request - should NOT retry
- [ ] HTTP 404 Not Found - should NOT retry
- [ ] HTTP 429 Rate Limited - SHOULD retry with backoff
- [ ] HTTP 500 Server Error - SHOULD retry with backoff
- [ ] HTTP 502/503/504 - SHOULD retry with backoff
- [ ] Connection timeout - SHOULD retry with backoff
- [ ] Connection refused - SHOULD retry with backoff
- [ ] DNS resolution failure - SHOULD retry with backoff

### Retry Behavior Tests
- [ ] Verify exponential backoff timing (1s, 2s, 4s, 8s)
- [ ] Verify max retries respected (default: 3)
- [ ] Verify retry exhaustion marks scans as failed
- [ ] Verify successful retry after transient failure

### Edge Cases
- [ ] Partial batch failure (some scans succeed, others fail)
- [ ] Malformed JSON response from API
- [ ] Empty response body
- [ ] Response timeout mid-transfer

## Technical Approach

Use `unittest.mock` to mock `requests.post()` responses:

```python
from unittest.mock import patch, Mock
import pytest
from sync import SyncService

@patch('sync.requests.post')
def test_http_500_triggers_retry(mock_post):
    # First call fails, second succeeds
    mock_post.side_effect = [
        Mock(status_code=500, text="Internal Server Error"),
        Mock(status_code=200, json=lambda: {"synced_count": 5})
    ]

    service = SyncService(db, api_url, api_key)
    result = service.sync_pending_scans()

    assert mock_post.call_count == 2
    assert result["synced"] == 5
```

## Files to Create/Modify

- [ ] Create `tests/test_sync_retry.py`
- [ ] May need to refactor `sync.py` to make retry logic more testable

## Acceptance Criteria

- [ ] All error types listed above have dedicated test cases
- [ ] Tests use mocking (no actual network calls)
- [ ] Tests verify correct scan status updates (synced/failed)
- [ ] Tests verify backoff timing within tolerance
- [ ] All tests pass in CI

## References

- `sync.py:233-350` - `_sync_one_batch()` implementation
- `sync.py:29-33` - `_is_retryable_error()` helper
```

---

### Issue #2: Add AutoSyncManager Tests

**Title**: `[Testing] Add unit tests for AutoSyncManager background sync logic`

**Labels**: `testing`, `P0-critical`, `sync`

**Body**:
```markdown
## Summary

The `AutoSyncManager` class in `main.py` (lines 117-300+) controls background synchronization but has zero test coverage. This is critical because silent failures in auto-sync could cause data to never reach the cloud.

## Current State

- `AutoSyncManager` handles: idle detection, network checking, sync locking, UI status updates
- Used in production for all background sync operations
- No tests exist

## Scope

Create `tests/test_auto_sync_manager.py` with tests for:

### Core Logic Tests
- [ ] `is_idle()` returns True when no scans for N seconds
- [ ] `is_idle()` returns False immediately after scan
- [ ] `on_scan()` updates last scan timestamp correctly
- [ ] `check_internet_connection()` returns True when API reachable
- [ ] `check_internet_connection()` returns False when API unreachable

### Sync Trigger Tests
- [ ] `check_and_sync()` triggers sync when: idle + pending scans + API reachable
- [ ] `check_and_sync()` skips sync when: not idle
- [ ] `check_and_sync()` skips sync when: no pending scans
- [ ] `check_and_sync()` skips sync when: API unreachable
- [ ] `check_and_sync()` skips sync when: sync already in progress (lock held)

### Concurrency Tests
- [ ] Lock prevents concurrent sync operations
- [ ] Scan during sync resets idle timer
- [ ] Multiple rapid `check_and_sync()` calls don't cause race

### Timer Tests
- [ ] Timer starts correctly with `start()`
- [ ] Timer stops correctly with `stop()`
- [ ] Timer interval matches config

## Technical Approach

Extract testable logic from AutoSyncManager or use dependency injection:

```python
from unittest.mock import Mock, patch
import time

def test_idle_detection_after_scan():
    manager = AutoSyncManager(
        attendance_service=Mock(),
        sync_service=Mock(),
        idle_seconds=5
    )

    manager.on_scan()
    assert manager.is_idle() == False

    time.sleep(6)
    assert manager.is_idle() == True

@patch.object(SyncService, 'test_connection')
def test_sync_skipped_when_offline(mock_conn):
    mock_conn.return_value = (False, "Connection refused")
    manager = AutoSyncManager(...)

    result = manager.check_and_sync()

    assert result["skipped"] == True
    assert "offline" in result["reason"]
```

## Files to Create/Modify

- [ ] Create `tests/test_auto_sync_manager.py`
- [ ] May need to extract `AutoSyncManager` to separate file for testability
- [ ] May need to add dependency injection for `SyncService`

## Acceptance Criteria

- [ ] All scenarios listed above have test coverage
- [ ] Tests don't require PyQt6 GUI (mock Qt components)
- [ ] Tests complete in < 30 seconds total
- [ ] Concurrency tests use threading to simulate real conditions
- [ ] All tests pass in CI

## References

- `main.py:117-300` - `AutoSyncManager` class
- `main.py:144` - `start()` method
- `main.py:189` - `check_and_sync()` method
```

---

### Issue #3: Add Duplicate Badge Detection Tests

**Title**: `[Testing] Add tests for duplicate badge detection in all modes`

**Labels**: `testing`, `P0-critical`, `database`

**Body**:
```markdown
## Summary

The duplicate badge detection feature (`check_if_duplicate_badge()` in `database.py` and handling in `attendance.py`) has zero test coverage despite being user-facing functionality with three distinct modes.

## Current State

- Three modes: `block`, `warn`, `silent`
- Configurable time window (default: 60 seconds)
- Detection logic in `database.py:check_if_duplicate_badge()`
- Response handling in `attendance.py:register_scan()` (lines 277-296)
- No tests exist

## Scope

Create `tests/test_duplicate_detection.py` with tests for:

### Database Layer Tests (`check_if_duplicate_badge`)
- [ ] Returns True when same badge scanned within time window
- [ ] Returns False when same badge scanned outside time window
- [ ] Returns False for different badge IDs
- [ ] Handles different stations correctly (same badge, different station)
- [ ] Time window boundary test (exactly at window edge)
- [ ] Empty database returns False

### Block Mode Tests
- [ ] Duplicate scan is rejected (not recorded)
- [ ] Response includes `duplicate: true, action: "blocked"`
- [ ] Original scan preserved in database
- [ ] UI receives red error feedback

### Warn Mode Tests
- [ ] Duplicate scan IS recorded (not blocked)
- [ ] Response includes `duplicate: true, action: "warned"`
- [ ] UI receives yellow warning feedback
- [ ] Both scans exist in database

### Silent Mode Tests
- [ ] Duplicate scan IS recorded
- [ ] Response includes `duplicate: true, action: "silent"`
- [ ] UI receives normal success feedback
- [ ] Log message indicates duplicate detected

### Configuration Tests
- [ ] `DUPLICATE_BADGE_DETECTION_ENABLED=false` disables all detection
- [ ] Custom time window respected (e.g., 30 seconds, 120 seconds)
- [ ] Invalid action falls back to default

## Test Data

```python
TEST_CASES = [
    # (badge_id, first_scan_time, second_scan_time, time_window, expected_duplicate)
    ("ABC123", "2025-01-01T10:00:00Z", "2025-01-01T10:00:30Z", 60, True),   # Within window
    ("ABC123", "2025-01-01T10:00:00Z", "2025-01-01T10:01:30Z", 60, False),  # Outside window
    ("ABC123", "2025-01-01T10:00:00Z", "2025-01-01T10:01:00Z", 60, True),   # Boundary
    ("ABC123", "2025-01-01T10:00:00Z", "2025-01-01T10:01:01Z", 60, False),  # Just outside
]
```

## Files to Create/Modify

- [ ] Create `tests/test_duplicate_detection.py`
- [ ] Verify `database.py:check_if_duplicate_badge()` implementation

## Acceptance Criteria

- [ ] All three modes (block/warn/silent) have dedicated test suites
- [ ] Time window boundary conditions tested
- [ ] Database state verified after each operation
- [ ] Response format validated
- [ ] Configuration override tests pass
- [ ] All tests pass in CI

## References

- `database.py:check_if_duplicate_badge()` - Detection logic
- `attendance.py:277-296` - Response handling
- `config.py` - `DUPLICATE_BADGE_*` configuration
```

---

### Issue #4: Add Excel Export Tests

**Title**: `[Testing] Add tests for Excel export functionality`

**Labels**: `testing`, `P0-critical`, `ui`

**Body**:
```markdown
## Summary

The Excel export functionality (`attendance.py:export_scans()`, lines 317-373) generates user-facing reports but has no test coverage. Export failures could cause data loss or corrupted files.

## Current State

- Exports scan data to Excel with formatting
- Handles Thai characters and special formatting
- Creates timestamped files in `exports/` directory
- No tests exist

## Scope

Create `tests/test_excel_export.py` with tests for:

### Basic Export Tests
- [ ] Export creates valid .xlsx file
- [ ] File contains correct headers
- [ ] Scan data matches database content
- [ ] Timestamp in filename is correct format

### Data Handling Tests
- [ ] Thai employee names render correctly
- [ ] Mixed Thai/English content works
- [ ] Special characters in badge IDs handled
- [ ] Very long employee names truncated appropriately
- [ ] Empty employee name (unmatched badge) handled
- [ ] NULL values don't cause errors

### Edge Cases
- [ ] Export with zero scans creates empty report (or appropriate message)
- [ ] Export with 10,000+ scans completes successfully
- [ ] Export with duplicate badge IDs shows all entries
- [ ] Date range spanning midnight works correctly

### Error Handling Tests
- [ ] Permission denied on export directory
- [ ] Disk full during write
- [ ] Export directory doesn't exist (should create)
- [ ] File already exists with same name
- [ ] Corrupted database scan record

### Format Validation
- [ ] Column widths are reasonable
- [ ] Date/time formatting is consistent
- [ ] Headers are bold/styled (if applicable)
- [ ] File can be opened by Excel/LibreOffice

## Technical Approach

```python
import openpyxl
from pathlib import Path
import tempfile

def test_export_with_thai_names(tmp_path):
    # Setup database with Thai employee
    db = DatabaseManager(tmp_path / "test.db")
    db.bulk_insert_employees([
        {"badge_id": "TH001", "name": "สมชาย ใจดี", "bu": "IT"}
    ])
    db.record_scan("TH001", "Station-A", "สมชาย ใจดี")

    service = AttendanceService(db_path, roster_path, tmp_path)
    export_path = service.export_scans()

    # Verify Excel content
    wb = openpyxl.load_workbook(export_path)
    ws = wb.active
    assert ws['C2'].value == "สมชาย ใจดี"  # Name column
```

## Files to Create/Modify

- [ ] Create `tests/test_excel_export.py`
- [ ] May need test fixtures for sample employee data

## Acceptance Criteria

- [ ] All data types (Thai, special chars, long strings) tested
- [ ] Error conditions handled gracefully
- [ ] Generated files validated with openpyxl
- [ ] Tests use temporary directories (cleanup after)
- [ ] Large dataset test completes in < 30 seconds
- [ ] All tests pass in CI

## References

- `attendance.py:317-373` - `export_scans()` implementation
- `test_encoding_thai.py` - Reference for Thai character handling
```

---

## P1 - High Priority Issues

### Issue #5: Add Authentication Error Handling Tests

**Title**: `[Testing] Add tests for API authentication error handling`

**Labels**: `testing`, `P1-high`, `sync`

**Body**:
```markdown
## Summary

The `test_authentication()` method exists in `sync.py` (lines 96-132) but is never called in tests. Authentication failures (401, 403) need proper handling to alert users of configuration issues.

## Current State

- `test_authentication()` method exists but untested
- 401/403 responses in `_sync_one_batch()` not tested
- Invalid API key scenarios not covered

## Scope

Create tests in `tests/test_sync_auth.py`:

### Authentication Method Tests
- [ ] Valid API key returns success
- [ ] Invalid API key returns 401 with clear message
- [ ] Expired API key handled (if applicable)
- [ ] Missing API key header returns 401
- [ ] Malformed API key format handled

### Sync Authentication Failure Tests
- [ ] 401 during sync marks batch as permanent failure (no retry)
- [ ] 403 during sync marks batch as permanent failure (no retry)
- [ ] Auth failure message propagated to UI

### Configuration Tests
- [ ] Empty `CLOUD_API_KEY` detected at startup
- [ ] Whitespace-only API key rejected

## Acceptance Criteria

- [ ] All authentication scenarios tested
- [ ] Clear error messages for each failure type
- [ ] No retry on permanent auth failures
- [ ] Tests use mocked responses

## References

- `sync.py:96-132` - `test_authentication()` method
- `sync.py:271-281` - 401 handling in `_sync_one_batch()`
```

---

### Issue #6: Add Roster File Validation Tests

**Title**: `[Testing] Add tests for employee roster file validation`

**Labels**: `testing`, `P1-high`, `database`

**Body**:
```markdown
## Summary

The roster validation logic in `attendance.py:validate_roster_headers()` (lines 50-88) handles various file format issues but has no test coverage.

## Current State

- Validates Excel headers for required columns
- Handles missing files, corrupt files, wrong format
- No tests exist

## Scope

Create `tests/test_roster_validation.py`:

### Valid File Tests
- [ ] Correct headers accepted
- [ ] Extra columns ignored
- [ ] Column order doesn't matter

### Missing Column Tests
- [ ] Missing "Badge ID" column - clear error
- [ ] Missing "Name" column - clear error
- [ ] Missing "BU" column - clear error (or handled gracefully)
- [ ] All columns missing - appropriate error

### File Format Tests
- [ ] .xlsx file works
- [ ] .xls file works (or clear error if unsupported)
- [ ] .csv file - clear error
- [ ] Empty file - clear error
- [ ] File with only headers (no data) - warning or success

### Error Handling Tests
- [ ] File not found - clear error
- [ ] Permission denied - clear error
- [ ] Corrupt Excel file - clear error
- [ ] Binary file (not Excel) - clear error

## Acceptance Criteria

- [ ] All validation scenarios tested
- [ ] Error messages are user-friendly
- [ ] Tests use fixture files or generated test data
- [ ] All tests pass in CI

## References

- `attendance.py:50-88` - `validate_roster_headers()` implementation
```

---

### Issue #7: Add Station Name Configuration Tests

**Title**: `[Testing] Add tests for station name validation and configuration`

**Labels**: `testing`, `P1-high`, `config`

**Body**:
```markdown
## Summary

Station name validation (50 char limit, regex pattern) in `attendance.py:ensure_station_configured()` (lines 202-235) is not tested.

## Scope

Create tests in `tests/test_station_config.py`:

### Validation Tests
- [ ] Valid station name accepted (alphanumeric, spaces, dash, underscore)
- [ ] 50 character name accepted (boundary)
- [ ] 51+ character name rejected
- [ ] Special characters rejected: `!@#$%^&*()`
- [ ] Empty string rejected
- [ ] Whitespace-only rejected
- [ ] Thai characters - verify behavior (accept or reject?)

### Persistence Tests
- [ ] Station name saved to database
- [ ] Station name loaded on restart
- [ ] Station name change updates database

## Acceptance Criteria

- [ ] Regex pattern validated against spec
- [ ] Length limits enforced
- [ ] Clear error messages for invalid names
- [ ] Database persistence verified

## References

- `attendance.py:202-235` - `ensure_station_configured()` implementation
- `database.py:set_station_name()` - Persistence
```

---

### Issue #8: Add Database Error Path Tests

**Title**: `[Testing] Add tests for database error handling paths`

**Labels**: `testing`, `P1-high`, `database`

**Body**:
```markdown
## Summary

Several database methods have no test coverage, including error handling paths.

## Scope

Create `tests/test_database_errors.py`:

### Untested Methods
- [ ] `mark_scans_as_failed(scan_ids, error_msg)` - verify scans marked correctly
- [ ] `clear_all_scans()` - verify all scans deleted
- [ ] `get_scans_by_bu()` - verify grouping logic
- [ ] `count_unmatched_scanned_badges()` - verify count accuracy
- [ ] `get_roster_hash()` / `set_roster_hash()` - verify persistence

### Error Handling Tests
- [ ] `mark_scans_as_synced()` with invalid scan IDs
- [ ] `record_scan()` with database locked
- [ ] Operations on closed database connection
- [ ] Concurrent schema creation

## Acceptance Criteria

- [ ] All listed methods have basic coverage
- [ ] Error conditions return appropriate responses
- [ ] Database state verified after each operation

## References

- `database.py` - All methods listed above
```

---

## P2 - Medium Priority Issues

### Issue #9: Add Configuration Validation Tests

**Title**: `[Testing] Add tests for configuration loading and validation`

**Labels**: `testing`, `P2-medium`, `config`

**Body**:
```markdown
## Summary

Configuration parsing in `config.py` uses `_safe_int()` and `_safe_float()` helpers but edge cases are untested.

## Scope

Create `tests/test_config.py`:

### Safe Parsing Tests
- [ ] Valid integer string parsed correctly
- [ ] Valid float string parsed correctly
- [ ] Non-numeric string returns default
- [ ] Empty string returns default
- [ ] Value below min returns min
- [ ] Value above max returns max
- [ ] Negative values handled

### Environment Variable Tests
- [ ] `.env` file loaded correctly
- [ ] System env vars override `.env`
- [ ] Missing required vars (`CLOUD_API_URL`, `CLOUD_API_KEY`) - behavior documented
- [ ] Boolean parsing (`true`, `false`, `1`, `0`)

## Acceptance Criteria

- [ ] All edge cases for `_safe_int()` and `_safe_float()` covered
- [ ] Configuration priority documented and tested
- [ ] Invalid values don't crash application

## References

- `config.py` - All configuration logic
```

---

### Issue #10: Add Logging and Secret Redaction Tests

**Title**: `[Testing] Add tests for logging setup and secret redaction`

**Labels**: `testing`, `P2-medium`, `config`

**Body**:
```markdown
## Summary

The `SecretRedactingFormatter` in `logging_config.py` redacts sensitive information from logs but patterns are not validated.

## Scope

Create `tests/test_logging.py`:

### Secret Redaction Tests
- [ ] API keys redacted from log messages
- [ ] Bearer tokens redacted
- [ ] Database connection strings redacted (if applicable)
- [ ] Partial matches don't over-redact
- [ ] Normal messages pass through unchanged

### Setup Tests
- [ ] Log directory created if missing
- [ ] Invalid log level falls back to INFO
- [ ] File rotation works (if configured)

## Acceptance Criteria

- [ ] All sensitive patterns in codebase identified and tested
- [ ] Redaction doesn't break log readability
- [ ] Setup errors handled gracefully

## References

- `logging_config.py` - `SecretRedactingFormatter` class
```

---

### Issue #11: Add Dashboard Integration Tests

**Title**: `[Testing] Add tests for dashboard API integration`

**Labels**: `testing`, `P2-medium`, `ui`

**Body**:
```markdown
## Summary

The `DashboardService` class in `dashboard.py` handles API integration for statistics and export but has no test coverage.

## Scope

Create `tests/test_dashboard.py`:

### API Integration Tests
- [ ] `get_dashboard_data()` parses valid response
- [ ] `get_dashboard_data()` handles API error
- [ ] `get_dashboard_data()` handles malformed JSON
- [ ] `export_to_excel()` creates valid file

### Response Validation Tests
- [ ] Required fields present in response
- [ ] Numeric fields are actually numbers
- [ ] Date fields parse correctly

## Acceptance Criteria

- [ ] API responses mocked for testing
- [ ] Error handling verified
- [ ] Export file validated

## References

- `dashboard.py` - `DashboardService` class
```

---

### Issue #12: Add UI Bridge Timeout Tests

**Title**: `[Testing] Add tests for JavaScript bridge timeout fallback`

**Labels**: `testing`, `P2-medium`, `ui`

**Body**:
```markdown
## Summary

The JS-Python bridge has timeout handling but the fallback mechanism isn't fully tested.

## Scope

Extend `tests/test_validation_ui.py`:

### Timeout Tests
- [ ] Bridge call timeout triggers fallback
- [ ] Fallback displays appropriate UI message
- [ ] Recovery after timeout works

### Bridge Failure Tests
- [ ] Partial bridge initialization handled
- [ ] Method not found handled gracefully
- [ ] Exception in Python method handled

## Acceptance Criteria

- [ ] Timeout scenarios tested with controlled delays
- [ ] User sees appropriate feedback on failures

## References

- `test_validation_ui.py` - Existing UI tests
- `web/script.js` - Bridge usage
```

---

## P3 - Long-term Issues

### Issue #13: Add End-to-End Integration Tests

**Title**: `[Testing] Create end-to-end integration test suite`

**Labels**: `testing`, `P3-low`

**Body**:
```markdown
## Summary

Create comprehensive end-to-end tests covering the full application lifecycle.

## Scope

Create `tests/test_e2e_integration.py`:

### Lifecycle Tests
- [ ] Startup → load roster → scan → export → sync → shutdown
- [ ] First-time setup flow (no existing data)
- [ ] Upgrade flow (existing data from previous version)

### Scenario Tests
- [ ] Offline → back online → sync backlog
- [ ] Multi-station with dashboard aggregation
- [ ] Concurrent scanning and auto-sync

## Acceptance Criteria

- [ ] Tests run against real (test) API
- [ ] Data cleanup between tests
- [ ] Tests complete in < 5 minutes

## References

- All application modules
```

---

### Issue #14: Add Performance and Stress Tests

**Title**: `[Testing] Add performance benchmarks and stress tests`

**Labels**: `testing`, `P3-low`

**Body**:
```markdown
## Summary

Add performance tests to ensure the application handles production-scale data.

## Scope

Create `tests/test_performance.py`:

### Scale Tests
- [ ] 10,000 scans in database - operations remain fast
- [ ] 1,000 employees - roster load time acceptable
- [ ] 100 rapid scans - no dropped events
- [ ] Large Excel export (10k rows) - completes in reasonable time

### Memory Tests
- [ ] No memory leak over 1000 scan cycles
- [ ] Database connection pooling effective

## Acceptance Criteria

- [ ] Baseline metrics established
- [ ] Tests fail if performance degrades significantly
- [ ] Memory profiling included

## References

- `tests/stress_full_app.py` - Existing stress test
```

---

### Issue #15: Add Property-Based Tests

**Title**: `[Testing] Implement property-based testing for data validation`

**Labels**: `testing`, `P3-low`

**Body**:
```markdown
## Summary

Use property-based testing (hypothesis) to discover edge cases in data handling.

## Scope

Create `tests/test_properties.py`:

### Data Format Properties
- [ ] Any valid badge ID is stored and retrieved unchanged
- [ ] Timestamps always round-trip correctly
- [ ] Employee names survive encoding/decoding
- [ ] Sync idempotency keys are always unique for unique scans

### Invariants
- [ ] Scan count never decreases (without explicit delete)
- [ ] Pending + synced + failed = total
- [ ] Employee lookup is O(1)

## Technical Approach

```python
from hypothesis import given, strategies as st

@given(badge_id=st.text(min_size=1, max_size=50))
def test_badge_id_roundtrip(badge_id):
    db.record_scan(badge_id, "Station", None)
    scans = db.fetch_all_scans()
    assert scans[-1]['badge_id'] == badge_id
```

## Acceptance Criteria

- [ ] hypothesis library added to requirements
- [ ] Key data paths covered
- [ ] Found edge cases documented

## References

- https://hypothesis.readthedocs.io/
```

---

### Issue #16: Add API Contract Tests

**Title**: `[Testing] Add API contract validation tests`

**Labels**: `testing`, `P3-low`, `sync`

**Body**:
```markdown
## Summary

Validate that sync API requests and responses match expected contracts.

## Scope

Create `tests/test_api_contract.py`:

### Request Validation
- [ ] Batch sync request format matches API spec
- [ ] Idempotency key format correct
- [ ] Authentication header format correct
- [ ] Content-Type header set

### Response Validation
- [ ] Success response has required fields
- [ ] Error response has error message
- [ ] Pagination fields present (if applicable)

### Compatibility Tests
- [ ] API version negotiation (if applicable)
- [ ] Deprecated field handling

## Acceptance Criteria

- [ ] Contract tests against mock API
- [ ] Can optionally run against staging API
- [ ] Schema validation using jsonschema or similar

## References

- `docs/API.md` - API documentation
- `sync.py` - Request/response handling
```

---

## Implementation Order

### Sprint 1 (P0 - Critical)
1. Issue #1: Sync Retry Logic Tests
2. Issue #2: AutoSyncManager Tests
3. Issue #3: Duplicate Badge Detection Tests
4. Issue #4: Excel Export Tests

### Sprint 2 (P1 - High)
5. Issue #5: Authentication Error Handling Tests
6. Issue #6: Roster File Validation Tests
7. Issue #7: Station Name Configuration Tests
8. Issue #8: Database Error Path Tests

### Sprint 3 (P2 - Medium)
9. Issue #9: Configuration Validation Tests
10. Issue #10: Logging and Secret Redaction Tests
11. Issue #11: Dashboard Integration Tests
12. Issue #12: UI Bridge Timeout Tests

### Sprint 4 (P3 - Long-term)
13. Issue #13: End-to-End Integration Tests
14. Issue #14: Performance and Stress Tests
15. Issue #15: Property-Based Tests
16. Issue #16: API Contract Tests

---

## Quick Reference: Create Issues via GitHub CLI

If `gh` CLI is available, use these commands:

```bash
# Create labels first
gh label create testing --color 7057ff --description "Test-related issues"
gh label create P0-critical --color b60205 --description "Critical priority"
gh label create P1-high --color d93f0b --description "High priority"
gh label create P2-medium --color fbca04 --description "Medium priority"
gh label create P3-low --color 0e8a16 --description "Low priority"
gh label create sync --color 1d76db --description "Sync functionality"
gh label create database --color 5319e7 --description "Database layer"
gh label create ui --color c5def5 --description "User interface"
gh label create config --color f9d0c4 --description "Configuration"

# Create issues (example for Issue #1)
gh issue create \
  --title "[Testing] Add comprehensive tests for sync retry logic and error handling" \
  --label "testing,P0-critical,sync" \
  --body-file issue_1_body.md
```

---

## Metrics

After implementation, measure:

- **Line coverage**: Target 80%+
- **Branch coverage**: Target 70%+
- **Critical path coverage**: Target 100%
- **Test execution time**: Target < 2 minutes for full suite

---

*Document generated by Claude Code analysis session*
