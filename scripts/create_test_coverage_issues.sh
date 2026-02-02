#!/bin/bash
# Script to create GitHub issues for test coverage improvements
# Usage: ./scripts/create_test_coverage_issues.sh
# Requires: gh CLI authenticated

set -e

REPO="Jarkius/trackattendance-frontend"

echo "Creating labels..."
gh label create testing --color 7057ff --description "Test-related issues" --repo "$REPO" 2>/dev/null || echo "Label 'testing' already exists"
gh label create P0-critical --color b60205 --description "Critical priority" --repo "$REPO" 2>/dev/null || echo "Label 'P0-critical' already exists"
gh label create P1-high --color d93f0b --description "High priority" --repo "$REPO" 2>/dev/null || echo "Label 'P1-high' already exists"
gh label create P2-medium --color fbca04 --description "Medium priority" --repo "$REPO" 2>/dev/null || echo "Label 'P2-medium' already exists"
gh label create P3-low --color 0e8a16 --description "Low priority" --repo "$REPO" 2>/dev/null || echo "Label 'P3-low' already exists"
gh label create sync --color 1d76db --description "Sync functionality" --repo "$REPO" 2>/dev/null || echo "Label 'sync' already exists"
gh label create database --color 5319e7 --description "Database layer" --repo "$REPO" 2>/dev/null || echo "Label 'database' already exists"
gh label create ui --color c5def5 --description "User interface" --repo "$REPO" 2>/dev/null || echo "Label 'ui' already exists"
gh label create config --color f9d0c4 --description "Configuration" --repo "$REPO" 2>/dev/null || echo "Label 'config' already exists"

echo ""
echo "Creating P0 (Critical) issues..."

# Issue 1
gh issue create --repo "$REPO" \
  --title "[Testing] Add comprehensive tests for sync retry logic and error handling" \
  --label "testing,P0-critical,sync" \
  --body "$(cat <<'EOF'
## Summary

The sync retry logic in `sync.py` (lines 233-350) handles all network error scenarios but has zero test coverage. This is critical because network failures could cause data loss if the retry logic fails silently.

## Scope

Create `tests/test_sync_retry.py` with tests for:

### Error Type Tests
- [ ] HTTP 401 Unauthorized - should NOT retry, mark permanent failure
- [ ] HTTP 403 Forbidden - should NOT retry, mark permanent failure
- [ ] HTTP 400 Bad Request - should NOT retry
- [ ] HTTP 429 Rate Limited - SHOULD retry with backoff
- [ ] HTTP 500 Server Error - SHOULD retry with backoff
- [ ] HTTP 502/503/504 - SHOULD retry with backoff
- [ ] Connection timeout - SHOULD retry with backoff
- [ ] Connection refused - SHOULD retry with backoff

### Retry Behavior Tests
- [ ] Verify exponential backoff timing (1s, 2s, 4s, 8s)
- [ ] Verify max retries respected (default: 3)
- [ ] Verify retry exhaustion marks scans as failed
- [ ] Verify successful retry after transient failure

### Edge Cases
- [ ] Partial batch failure (some scans succeed, others fail)
- [ ] Malformed JSON response from API
- [ ] Empty response body

## Acceptance Criteria

- [ ] All error types listed above have dedicated test cases
- [ ] Tests use mocking (no actual network calls)
- [ ] Tests verify correct scan status updates (synced/failed)
- [ ] All tests pass in CI

## References

- `sync.py:233-350` - `_sync_one_batch()` implementation
- `sync.py:29-33` - `_is_retryable_error()` helper
EOF
)"

# Issue 2
gh issue create --repo "$REPO" \
  --title "[Testing] Add unit tests for AutoSyncManager background sync logic" \
  --label "testing,P0-critical,sync" \
  --body "$(cat <<'EOF'
## Summary

The `AutoSyncManager` class in `main.py` (lines 117-300+) controls background synchronization but has zero test coverage. This is critical because silent failures in auto-sync could cause data to never reach the cloud.

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

## Acceptance Criteria

- [ ] All scenarios listed above have test coverage
- [ ] Tests don't require PyQt6 GUI (mock Qt components)
- [ ] Tests complete in < 30 seconds total
- [ ] All tests pass in CI

## References

- `main.py:117-300` - `AutoSyncManager` class
EOF
)"

# Issue 3
gh issue create --repo "$REPO" \
  --title "[Testing] Add tests for duplicate badge detection in all modes" \
  --label "testing,P0-critical,database" \
  --body "$(cat <<'EOF'
## Summary

The duplicate badge detection feature has zero test coverage despite being user-facing functionality with three distinct modes.

## Scope

Create `tests/test_duplicate_detection.py` with tests for:

### Database Layer Tests (`check_if_duplicate_badge`)
- [ ] Returns True when same badge scanned within time window
- [ ] Returns False when same badge scanned outside time window
- [ ] Returns False for different badge IDs
- [ ] Time window boundary test (exactly at window edge)

### Block Mode Tests
- [ ] Duplicate scan is rejected (not recorded)
- [ ] Response includes `duplicate: true, action: "blocked"`
- [ ] Original scan preserved in database

### Warn Mode Tests
- [ ] Duplicate scan IS recorded (not blocked)
- [ ] Response includes `duplicate: true, action: "warned"`
- [ ] Both scans exist in database

### Silent Mode Tests
- [ ] Duplicate scan IS recorded
- [ ] Response includes `duplicate: true, action: "silent"`
- [ ] Log message indicates duplicate detected

### Configuration Tests
- [ ] `DUPLICATE_BADGE_DETECTION_ENABLED=false` disables all detection
- [ ] Custom time window respected

## Acceptance Criteria

- [ ] All three modes (block/warn/silent) have dedicated test suites
- [ ] Time window boundary conditions tested
- [ ] Database state verified after each operation
- [ ] All tests pass in CI

## References

- `database.py:check_if_duplicate_badge()` - Detection logic
- `attendance.py:277-296` - Response handling
- `config.py` - `DUPLICATE_BADGE_*` configuration
EOF
)"

# Issue 4
gh issue create --repo "$REPO" \
  --title "[Testing] Add tests for Excel export functionality" \
  --label "testing,P0-critical,ui" \
  --body "$(cat <<'EOF'
## Summary

The Excel export functionality (`attendance.py:export_scans()`, lines 317-373) generates user-facing reports but has no test coverage.

## Scope

Create `tests/test_excel_export.py` with tests for:

### Basic Export Tests
- [ ] Export creates valid .xlsx file
- [ ] File contains correct headers
- [ ] Scan data matches database content

### Data Handling Tests
- [ ] Thai employee names render correctly
- [ ] Mixed Thai/English content works
- [ ] Special characters in badge IDs handled
- [ ] Empty employee name (unmatched badge) handled

### Edge Cases
- [ ] Export with zero scans creates empty report
- [ ] Export with 10,000+ scans completes successfully

### Error Handling Tests
- [ ] Permission denied on export directory
- [ ] Export directory doesn't exist (should create)

## Acceptance Criteria

- [ ] All data types (Thai, special chars) tested
- [ ] Error conditions handled gracefully
- [ ] Generated files validated with openpyxl
- [ ] Tests use temporary directories
- [ ] All tests pass in CI

## References

- `attendance.py:317-373` - `export_scans()` implementation
EOF
)"

echo ""
echo "Creating P1 (High) issues..."

# Issue 5
gh issue create --repo "$REPO" \
  --title "[Testing] Add tests for API authentication error handling" \
  --label "testing,P1-high,sync" \
  --body "$(cat <<'EOF'
## Summary

The `test_authentication()` method exists in `sync.py` but is never called in tests. Authentication failures (401, 403) need proper handling.

## Scope

- [ ] Valid API key returns success
- [ ] Invalid API key returns 401 with clear message
- [ ] Missing API key header returns 401
- [ ] 401 during sync marks batch as permanent failure (no retry)
- [ ] 403 during sync marks batch as permanent failure (no retry)
- [ ] Empty `CLOUD_API_KEY` detected at startup

## Acceptance Criteria

- [ ] All authentication scenarios tested
- [ ] Clear error messages for each failure type
- [ ] No retry on permanent auth failures
- [ ] Tests use mocked responses

## References

- `sync.py:96-132` - `test_authentication()` method
- `sync.py:271-281` - 401 handling in `_sync_one_batch()`
EOF
)"

# Issue 6
gh issue create --repo "$REPO" \
  --title "[Testing] Add tests for employee roster file validation" \
  --label "testing,P1-high,database" \
  --body "$(cat <<'EOF'
## Summary

The roster validation logic in `attendance.py:validate_roster_headers()` handles various file format issues but has no test coverage.

## Scope

### Valid File Tests
- [ ] Correct headers accepted
- [ ] Extra columns ignored
- [ ] Column order doesn't matter

### Missing Column Tests
- [ ] Missing "Badge ID" column - clear error
- [ ] Missing "Name" column - clear error
- [ ] All columns missing - appropriate error

### File Format Tests
- [ ] .xlsx file works
- [ ] Empty file - clear error
- [ ] File with only headers (no data) - warning or success

### Error Handling Tests
- [ ] File not found - clear error
- [ ] Permission denied - clear error
- [ ] Corrupt Excel file - clear error

## Acceptance Criteria

- [ ] All validation scenarios tested
- [ ] Error messages are user-friendly
- [ ] Tests use fixture files
- [ ] All tests pass in CI

## References

- `attendance.py:50-88` - `validate_roster_headers()` implementation
EOF
)"

# Issue 7
gh issue create --repo "$REPO" \
  --title "[Testing] Add tests for station name validation and configuration" \
  --label "testing,P1-high,config" \
  --body "$(cat <<'EOF'
## Summary

Station name validation (50 char limit, regex pattern) in `attendance.py:ensure_station_configured()` is not tested.

## Scope

### Validation Tests
- [ ] Valid station name accepted (alphanumeric, spaces, dash, underscore)
- [ ] 50 character name accepted (boundary)
- [ ] 51+ character name rejected
- [ ] Special characters rejected: \`!@#$%^&*()\`
- [ ] Empty string rejected
- [ ] Whitespace-only rejected

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
EOF
)"

# Issue 8
gh issue create --repo "$REPO" \
  --title "[Testing] Add tests for database error handling paths" \
  --label "testing,P1-high,database" \
  --body "$(cat <<'EOF'
## Summary

Several database methods have no test coverage, including error handling paths.

## Scope

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

## Acceptance Criteria

- [ ] All listed methods have basic coverage
- [ ] Error conditions return appropriate responses
- [ ] Database state verified after each operation

## References

- `database.py` - All methods listed above
EOF
)"

echo ""
echo "Creating P2 (Medium) issues..."

# Issue 9
gh issue create --repo "$REPO" \
  --title "[Testing] Add tests for configuration loading and validation" \
  --label "testing,P2-medium,config" \
  --body "$(cat <<'EOF'
## Summary

Configuration parsing in `config.py` uses `_safe_int()` and `_safe_float()` helpers but edge cases are untested.

## Scope

### Safe Parsing Tests
- [ ] Valid integer string parsed correctly
- [ ] Valid float string parsed correctly
- [ ] Non-numeric string returns default
- [ ] Empty string returns default
- [ ] Value below min returns min
- [ ] Value above max returns max

### Environment Variable Tests
- [ ] `.env` file loaded correctly
- [ ] Boolean parsing (`true`, `false`, `1`, `0`)

## Acceptance Criteria

- [ ] All edge cases for `_safe_int()` and `_safe_float()` covered
- [ ] Invalid values don't crash application

## References

- `config.py` - All configuration logic
EOF
)"

# Issue 10
gh issue create --repo "$REPO" \
  --title "[Testing] Add tests for logging setup and secret redaction" \
  --label "testing,P2-medium,config" \
  --body "$(cat <<'EOF'
## Summary

The `SecretRedactingFormatter` in `logging_config.py` redacts sensitive information from logs but patterns are not validated.

## Scope

### Secret Redaction Tests
- [ ] API keys redacted from log messages
- [ ] Bearer tokens redacted
- [ ] Normal messages pass through unchanged

### Setup Tests
- [ ] Log directory created if missing
- [ ] Invalid log level falls back to INFO

## Acceptance Criteria

- [ ] All sensitive patterns identified and tested
- [ ] Redaction doesn't break log readability
- [ ] Setup errors handled gracefully

## References

- `logging_config.py` - `SecretRedactingFormatter` class
EOF
)"

# Issue 11
gh issue create --repo "$REPO" \
  --title "[Testing] Add tests for dashboard API integration" \
  --label "testing,P2-medium,ui" \
  --body "$(cat <<'EOF'
## Summary

The `DashboardService` class in `dashboard.py` handles API integration but has no test coverage.

## Scope

### API Integration Tests
- [ ] `get_dashboard_data()` parses valid response
- [ ] `get_dashboard_data()` handles API error
- [ ] `get_dashboard_data()` handles malformed JSON
- [ ] `export_to_excel()` creates valid file

### Response Validation Tests
- [ ] Required fields present in response
- [ ] Numeric fields are actually numbers

## Acceptance Criteria

- [ ] API responses mocked for testing
- [ ] Error handling verified
- [ ] Export file validated

## References

- `dashboard.py` - `DashboardService` class
EOF
)"

# Issue 12
gh issue create --repo "$REPO" \
  --title "[Testing] Add tests for JavaScript bridge timeout fallback" \
  --label "testing,P2-medium,ui" \
  --body "$(cat <<'EOF'
## Summary

The JS-Python bridge has timeout handling but the fallback mechanism isn't fully tested.

## Scope

### Timeout Tests
- [ ] Bridge call timeout triggers fallback
- [ ] Fallback displays appropriate UI message
- [ ] Recovery after timeout works

### Bridge Failure Tests
- [ ] Method not found handled gracefully
- [ ] Exception in Python method handled

## Acceptance Criteria

- [ ] Timeout scenarios tested with controlled delays
- [ ] User sees appropriate feedback on failures

## References

- `test_validation_ui.py` - Existing UI tests
- `web/script.js` - Bridge usage
EOF
)"

echo ""
echo "Creating P3 (Long-term) issues..."

# Issue 13
gh issue create --repo "$REPO" \
  --title "[Testing] Create end-to-end integration test suite" \
  --label "testing,P3-low" \
  --body "$(cat <<'EOF'
## Summary

Create comprehensive end-to-end tests covering the full application lifecycle.

## Scope

### Lifecycle Tests
- [ ] Startup -> load roster -> scan -> export -> sync -> shutdown
- [ ] First-time setup flow (no existing data)

### Scenario Tests
- [ ] Offline -> back online -> sync backlog
- [ ] Multi-station with dashboard aggregation
- [ ] Concurrent scanning and auto-sync

## Acceptance Criteria

- [ ] Tests run against real (test) API
- [ ] Data cleanup between tests
- [ ] Tests complete in < 5 minutes
EOF
)"

# Issue 14
gh issue create --repo "$REPO" \
  --title "[Testing] Add performance benchmarks and stress tests" \
  --label "testing,P3-low" \
  --body "$(cat <<'EOF'
## Summary

Add performance tests to ensure the application handles production-scale data.

## Scope

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

## References

- `tests/stress_full_app.py` - Existing stress test
EOF
)"

# Issue 15
gh issue create --repo "$REPO" \
  --title "[Testing] Implement property-based testing for data validation" \
  --label "testing,P3-low" \
  --body "$(cat <<'EOF'
## Summary

Use property-based testing (hypothesis) to discover edge cases in data handling.

## Scope

### Data Format Properties
- [ ] Any valid badge ID is stored and retrieved unchanged
- [ ] Timestamps always round-trip correctly
- [ ] Employee names survive encoding/decoding

### Invariants
- [ ] Scan count never decreases (without explicit delete)
- [ ] Pending + synced + failed = total

## Technical Approach

Add `hypothesis` to requirements and create property-based tests.

## Acceptance Criteria

- [ ] hypothesis library added to requirements
- [ ] Key data paths covered
- [ ] Found edge cases documented
EOF
)"

# Issue 16
gh issue create --repo "$REPO" \
  --title "[Testing] Add API contract validation tests" \
  --label "testing,P3-low" \
  --body "$(cat <<'EOF'
## Summary

Validate that sync API requests and responses match expected contracts.

## Scope

### Request Validation
- [ ] Batch sync request format matches API spec
- [ ] Idempotency key format correct
- [ ] Authentication header format correct

### Response Validation
- [ ] Success response has required fields
- [ ] Error response has error message

## Acceptance Criteria

- [ ] Contract tests against mock API
- [ ] Schema validation using jsonschema or similar

## References

- `docs/API.md` - API documentation
- `sync.py` - Request/response handling
EOF
)"

echo ""
echo "All 16 issues created successfully!"
echo ""
echo "View issues at: https://github.com/$REPO/issues"
