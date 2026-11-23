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
  - `main.py`: removed the duplicate `enumerate_cameras`; the probe (`_probe_cameras`) runs via `call_without_freezing_ui`. The three backup exports (admin clear x2, remote clear) pass `run_blocking=call_without_freezing_ui`. New `pause_with_event_loop()` replaces the three GUI-thread `time.sleep(0.5)` calls in shutdown. New `sync_pending_until_deadline()` is the shutdown batch loop, bounded by `config.SHUTDOWN_SYNC_DEADLINE_SECONDS`.
  - `attendance.py`: `export_scans(run_blocking=None)` reads SQLite on the caller thread and hands only the workbook build/save (`_write_export_workbook`, no DB access) to `run_blocking`.
  - `database.py`: `get_sync_statistics` is now a `GROUP BY sync_status` plus `MAX(synced_at)`; added `idx_scans_synced_at`.
  - `config.py`: `SHUTDOWN_SYNC_DEADLINE_SECONDS` (default 30, bounds 1-600).
  - Tests: `tests/test_gui_thread_hygiene.py` (new), `tests/test_config.py`.
- Verification results:
  - Ticket verification set plus test_config: 74 passed, 1 skipped.
  - Local CI (`ci.sh`): 476 passed, 1 skipped; standalone Windows-only tests ran.
  - `get_sync_statistics` on 50,000 rows (30 calls, median): 7.46 ms before, 1.60 ms after.
- Known limitations:
  - The deadline is checked between batches, so one in-flight batch can overrun it by its network timeout.
  - The shutdown export and the close-path export still run on the GUI thread (out of scope).
  - The QTimer-heartbeat responsiveness check with 5,000 scans was not run (needs a live QApplication harness). The off-thread routing is covered by unit tests only.
  - `pause_with_event_loop` is not exercised under a live Qt loop in tests (no app under pytest; it falls back to `time.sleep`).
