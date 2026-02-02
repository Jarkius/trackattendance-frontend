# Test Coverage Issues - Quick Reference

Use this file to quickly create GitHub issues. Copy each section to create an issue.

---

## Issue 1: Sync Retry Logic Tests (P0)

**Title**: `[Testing] Add comprehensive tests for sync retry logic and error handling`

**Labels**: `testing`, `P0-critical`, `sync`

**Description**:
Add tests for `sync.py` retry logic (lines 233-350) covering all error types:
- HTTP 401/403 (no retry)
- HTTP 429/5xx (retry with backoff)
- Timeouts and connection errors
- Retry exhaustion handling

**Acceptance Criteria**:
- [ ] All error types have dedicated test cases
- [ ] Exponential backoff timing verified
- [ ] Scan status updates (synced/failed) verified
- [ ] Uses mocking (no network calls)

---

## Issue 2: AutoSyncManager Tests (P0)

**Title**: `[Testing] Add unit tests for AutoSyncManager background sync logic`

**Labels**: `testing`, `P0-critical`, `sync`

**Description**:
Add tests for `AutoSyncManager` class in `main.py` (lines 117-300):
- Idle detection logic
- Network checking before sync
- Lock mechanism preventing concurrent syncs
- Timer start/stop

**Acceptance Criteria**:
- [ ] Idle detection scenarios tested
- [ ] Sync trigger conditions tested
- [ ] Concurrency/locking tested
- [ ] No PyQt6 GUI required

---

## Issue 3: Duplicate Badge Detection Tests (P0)

**Title**: `[Testing] Add tests for duplicate badge detection in all modes`

**Labels**: `testing`, `P0-critical`, `database`

**Description**:
Add tests for `check_if_duplicate_badge()` and all three modes:
- `block` mode: Scan rejected
- `warn` mode: Scan recorded with warning
- `silent` mode: Scan recorded, logged only

**Acceptance Criteria**:
- [ ] All three modes tested
- [ ] Time window boundary conditions tested
- [ ] Database state verified
- [ ] Configuration override tested

---

## Issue 4: Excel Export Tests (P0)

**Title**: `[Testing] Add tests for Excel export functionality`

**Labels**: `testing`, `P0-critical`, `ui`

**Description**:
Add tests for `attendance.py:export_scans()` (lines 317-373):
- Thai character handling
- Special characters in data
- Error handling (disk full, permissions)
- Large dataset handling

**Acceptance Criteria**:
- [ ] Generated files validated with openpyxl
- [ ] Thai/special characters render correctly
- [ ] Error conditions handled gracefully
- [ ] 10k+ rows completes successfully

---

## Issue 5: Authentication Error Handling Tests (P1)

**Title**: `[Testing] Add tests for API authentication error handling`

**Labels**: `testing`, `P1-high`, `sync`

**Description**:
Test `test_authentication()` method and auth failure handling in sync:
- Invalid API key (401)
- Forbidden (403)
- Missing API key

**Acceptance Criteria**:
- [ ] Clear error messages for each failure type
- [ ] No retry on permanent auth failures
- [ ] Tests use mocked responses

---

## Issue 6: Roster File Validation Tests (P1)

**Title**: `[Testing] Add tests for employee roster file validation`

**Labels**: `testing`, `P1-high`, `database`

**Description**:
Test `attendance.py:validate_roster_headers()` (lines 50-88):
- Missing columns
- Wrong file format
- Corrupt files
- Empty files

**Acceptance Criteria**:
- [ ] All validation scenarios tested
- [ ] User-friendly error messages
- [ ] Tests use fixture files

---

## Issue 7: Station Name Configuration Tests (P1)

**Title**: `[Testing] Add tests for station name validation and configuration`

**Labels**: `testing`, `P1-high`, `config`

**Description**:
Test station name validation:
- 50 character limit
- Allowed characters (alphanumeric, space, dash, underscore)
- Persistence to database

**Acceptance Criteria**:
- [ ] Length limits enforced
- [ ] Invalid characters rejected
- [ ] Database persistence verified

---

## Issue 8: Database Error Path Tests (P1)

**Title**: `[Testing] Add tests for database error handling paths`

**Labels**: `testing`, `P1-high`, `database`

**Description**:
Test untested database methods:
- `mark_scans_as_failed()`
- `clear_all_scans()`
- `get_scans_by_bu()`
- `count_unmatched_scanned_badges()`
- Error handling paths

**Acceptance Criteria**:
- [ ] All listed methods have basic coverage
- [ ] Error conditions return appropriate responses
- [ ] Database state verified

---

## Issue 9: Configuration Validation Tests (P2)

**Title**: `[Testing] Add tests for configuration loading and validation`

**Labels**: `testing`, `P2-medium`, `config`

**Description**:
Test `config.py` parsing helpers:
- `_safe_int()` and `_safe_float()` edge cases
- Invalid/missing env vars
- Min/max clamping

---

## Issue 10: Logging and Secret Redaction Tests (P2)

**Title**: `[Testing] Add tests for logging setup and secret redaction`

**Labels**: `testing`, `P2-medium`, `config`

**Description**:
Test `SecretRedactingFormatter`:
- API keys redacted
- Bearer tokens redacted
- Normal messages unchanged

---

## Issue 11: Dashboard Integration Tests (P2)

**Title**: `[Testing] Add tests for dashboard API integration`

**Labels**: `testing`, `P2-medium`, `ui`

**Description**:
Test `DashboardService`:
- `get_dashboard_data()` response parsing
- `export_to_excel()` file generation
- Error handling

---

## Issue 12: UI Bridge Timeout Tests (P2)

**Title**: `[Testing] Add tests for JavaScript bridge timeout fallback`

**Labels**: `testing`, `P2-medium`, `ui`

**Description**:
Test JS-Python bridge timeout handling:
- Timeout triggers fallback
- Recovery after timeout
- Method not found handling

---

## Issue 13: End-to-End Integration Tests (P3)

**Title**: `[Testing] Create end-to-end integration test suite`

**Labels**: `testing`, `P3-low`

**Description**:
Full lifecycle tests:
- Startup to shutdown flow
- Offline to online recovery
- Multi-station scenarios

---

## Issue 14: Performance and Stress Tests (P3)

**Title**: `[Testing] Add performance benchmarks and stress tests`

**Labels**: `testing`, `P3-low`

**Description**:
Performance testing:
- 10k+ scans database operations
- Memory leak detection
- Large export performance

---

## Issue 15: Property-Based Tests (P3)

**Title**: `[Testing] Implement property-based testing for data validation`

**Labels**: `testing`, `P3-low`

**Description**:
Use hypothesis library for:
- Badge ID roundtrip
- Timestamp integrity
- Sync idempotency keys

---

## Issue 16: API Contract Tests (P3)

**Title**: `[Testing] Add API contract validation tests`

**Labels**: `testing`, `P3-low`

**Description**:
Validate API contracts:
- Request format matches spec
- Response schema validation
- Version compatibility
