# Changelog

All notable changes to TrackAttendance Frontend are documented in this file.

## 2026-08-24

### Fixed

- **Shutdown-sync race with the coordinator barrier.** `_handle_close_event`'s direct `sync_service.sync_pending_scans(sync_all=True)` call was the one remaining SQLite mutation outside the coordinator's snapshot/network-only/apply pattern from the #65–#69 fixes. Wrapped in the same pause/reset/resume barrier sequence used at the other three barrier sites.
- **Search ranking tiers 3/4 had the same insertion-order starvation bug as tier 1.** The "contains anywhere" tier now ranks by match position; the "all words present, any order" tier now ranks by word adjacency. Confirmed against reconstructed starvation scenarios.
- **Corrupt roster file could crash the app at startup.** A malformed `employee.xlsx` with `ROSTER_STRICT_VALIDATION=False` or `ROSTER_VALIDATION_ENABLED=False` fell through to an unguarded `load_workbook()` call and crashed instead of degrading gracefully via the existing `_roster_error` path.

### Chore

- Documented the `.venv` interpreter requirement for PyQt6-dependent commands in `CLAUDE.md`.
- Bumped `actions/checkout`/`actions/setup-python` past the deprecated Node.js 20 runtime in CI.
- **Untracked `logs/trackattendance.log` and stray screenshots from git.** These had been committed since before `.gitignore`'s `logs/*.log` rule existed, so the rule never took effect retroactively — the log file contained real scan data (badge IDs, station names, timestamps) going back to Dec 2025. Removed from tracking going forward (`git rm --cached`); files remain on disk. Note: this does not remove the data from past commits' history — a separate history-rewrite would be needed for that, and hasn't been done.

## 2026-08-21

### Fixed

- **Sync coordinator bugfixes (issues #65–#69)**, building on the `BackgroundSyncCoordinator` introduced in `77a41a3`:
  - **#65 — stranded lock/flag after a barrier.** A `pause_barrier()` call (admin cloud/station data clear, or remote-clear detection) that fired while an auto-sync or manual `sync_now()` job was already dequeued/in-flight would permanently strand `AutoSyncManager.is_syncing`/`_sync_lock` or `Api._manual_sync_in_progress`, since the job's own completion callback gets silently dropped by the coordinator's generation check and never runs to clear them. Added `AutoSyncManager.reset_after_barrier()` and `Api._reset_manual_sync_state()`, wired into all three barrier call sites (`admin_clear_cloud_data`, `admin_clear_station_data`, `_handle_clear_epoch_and_heartbeat_slot`).
  - **#66 — cross-thread SQLite access on first Live Sync call.** `SyncService.sync_single_scan()` called `_generate_idempotency_key()`, which lazily resolves and caches the station name via `self.db.get_station_name()` — a SQLite read from the coordinator's worker thread. Changed the signature to `sync_single_scan(scan, station_name)`; the caller (`AttendanceService.register_scan()`) now resolves `station_name` on the main thread before the worker-thread lambda closure captures it.
  - **#67 — DB-apply failures not counted against auto-sync cooldown.** A `mark_scans_as_synced`/`mark_scans_as_failed` exception during `_on_auto_sync_result()`'s DB-apply step was silently absorbed and the batch treated as a network success for cooldown-counter purposes. Added `db_apply_failed` tracking, OR'd into the failure decision.
  - **#68 — network-only batch sync returning `ok: True` on failure.** Four failure branches in `sync_scan_batch_network_only()` (401 unauthorized, non-retryable 4xx, `RequestException`, retries-exhausted) returned `"ok": True` despite the batch having failed. Corrected to `False` (or `last_error is None` for the retries-exhausted fallback).
  - **#69 — unrecognized sync-outcome stage silently treated as success.** Both `_on_auto_sync_result()` and `_on_manual_sync_result()` had no `else`/`elif` branch for an unexpected `stage` value, letting it fall through into the batch-handling path with an empty `batch_result` and register as a false success. Added explicit `stage != "batch"` guards that treat any unrecognized stage as a hard failure.
  - Verified end-to-end against a real `BackgroundSyncCoordinator` (not the `SynchronousCoordinator` test fake) via new `tests/test_barrier_reset_integration.py`, plus manual live-app monitoring (multiple manual/auto sync cycles, clean shutdown, no stranded state).

- **Employee search (`AttendanceService.search_employee()`) not prioritizing name-prefix matches.** A short query like `"c"` or `"j"` could have its top-10 results filled entirely by employees whose name merely *contained* the letter somewhere (e.g. "Marcus"), starving out employees whose name actually *started with* it (e.g. "Carlos"). Split the old single substring-match tier into three ranked tiers: first-name-prefix match → other-word-prefix match (surname, etc.) → plain substring-anywhere match. Confirmed against the live 443-employee roster (`"j"` now surfaces "Jihun Jung" before "Parichart Jiravachara").

- **Employee lookup overlay (`web/script.js`) UI issues:**
  - Results list didn't reset scroll position between searches — a second search reopened the overlay still scrolled from wherever the previous search left it. Now resets `lookupResults.scrollTop = 0` on every `showLookupOverlay()` call.
  - No keyboard navigation within the results list. Added Up/Down arrow-key handling that moves a highlighted/focused state between result rows (wraps at the ends, auto-scrolls into view); Enter already worked via native `<button>` focus behavior once focus tracking was added.
  - `Escape` closed the entire app window while the lookup overlay was open, since the global Escape handler didn't know about it. Now closes just the lookup overlay first, matching the existing admin/dashboard overlay behavior.

### Tests

- Updated: `tests/test_sync_network_only_batch.py`, `tests/test_live_sync.py`, `tests/test_live_sync_coordinator_enqueue.py`, `tests/test_sync_coordinator.py`, `tests/test_auto_sync_coordinator_integration.py`, `tests/test_sync_now_async.py`.
- Added: `tests/test_barrier_reset_integration.py`, `tests/test_search_employee_prefix_priority.py`.
- Full suite (447+ tests, PyQt6-required files run under the Python 3.12 interpreter at `C:\Users\jsanitareephon\AppData\Local\Programs\Python\Python312\python.exe`, or the project's own `.venv`) passes with 0 failures.
