# 10: GUI-thread blocking hygiene (#111)

## Objective
The GUI thread does no camera probing, Excel writing or sleeping, and shutdown finishes within a bounded total time.

## Dependencies
- none. It touches `main.py` shutdown and admin-clear code near the barrier logic, so land it after 01.

## Scope
- Relevant modules/files:
  - `main.py`: `enumerate_cameras` :1140/:1217, admin clear :1363/:1455, remote clear :2291, shutdown :2780-2990
  - `database.py`: `get_sync_statistics` :551
  - `config.py`: a new `SHUTDOWN_SYNC_DEADLINE_SECONDS`
- Expected behavior:
  - Delete the duplicate `enumerate_cameras` and run the probe via `call_without_freezing_ui`.
  - Run the backup export the same way, without reordering barrier → export → clear.
  - Replace the shutdown `time.sleep` calls with `QTimer`-driven steps, or an event-loop pump that lets the overlay repaint.
  - The shutdown sync loop stops at the deadline. Remaining scans stay pending and are included in the export.
  - Serve `get_sync_statistics` from cached counters, or add an index on `sync_status`.

## Acceptance Criteria
- [ ] Only one `enumerate_cameras` definition remains.
- [ ] Given 5,000 local scans, then admin clear keeps the UI responsive during the backup export (measured with a QTimer heartbeat in a disposable harness).
- [ ] Given an unreachable API and 1,000 pending scans, then shutdown completes within the deadline plus the export time.
- [ ] Before/after timings of `get_sync_statistics` with 50,000 rows are recorded in the PR.
- [ ] The barrier/clear-ordering tests still pass.

## Contracts and Constraints
- Preserve the PR #64 barrier semantics. SQLite stays on the main thread. The new config flag follows `config.py` conventions (default: 30 s).

## Verification
```bash
python -m pytest tests/test_admin_clear_barrier_ordering.py tests/test_barrier_reset_integration.py tests/test_performance.py tests/test_slice_a_perf.py -v
```

## Completion Report
- Changed files:
- Verification results:
- Known limitations:
