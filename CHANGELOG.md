# Changelog

All notable changes to TrackAttendance Frontend are documented in this file.

## v2.1.2 (2026-09-01)

### Fixed

- **Dashboard showed registered count as 0, logging a silent `ERROR`** ("SQLite objects created in a thread can only be used in that same thread") every time Dashboard was opened — a regression from v2.1.1's freeze fix, which wrapped the entire `DashboardService.get_dashboard_data()`/`export_to_excel()` call in `call_without_freezing_ui()`, moving their local SQLite reads onto a worker thread along with the network call. Fixed by injecting `run_network_call` into `DashboardService` so only the actual `requests.get()` calls run off-thread; SQLite reads stay on the calling thread. Found via the v2.1.1 live 2-laptop test.
- **A duplicate badge scan slipped through during live testing.** Root cause: `check_duplicate_cloud()`'s success path logged nothing (only errors), so the actual slow event left no trace. Live-measured the cloud endpoint: warm requests are 140–235ms, but a cold-path (cold TLS/cold Cloud Run instance) request took 2.44s — over the old `LIVE_SYNC_TIMEOUT_SECONDS` default of 2.0s. The client fails open on timeout (treats it as "not a duplicate"), matching the observed symptom exactly. Raised the default to 4.0s and added elapsed-time + outcome logging (client-side, and a matching connect/query timing split on the cloud API's `check-duplicate` endpoint) so future slowness is measurable instead of guessed at.

### Added

- **Dashboard shows the registered-employee count instantly on open**, with the cloud-sourced fields (scanned count, stations, BU breakdown) filling in asynchronously in the background exactly as before — no reason to make the user wait on a cloud round-trip just to see a number that's already in the local database.

### Docs

- Documented Live Sync (`LIVE_SYNC_*` env vars, the duplicate-check + immediate-upload flow, fail-open behavior) and cloud API rate limiting, which had no prior documentation despite existing since #54.

## v2.1.1 (2026-08-31)

### Fixed

- **App-wide freeze when opening Dashboard/Settings, worse (cross-station hangs) with Live Sync enabled.** Several `@pyqtSlot` methods (Dashboard data fetch/export, admin scan-count/clear-cloud/clear-station/station-status, dashboard-refresh get/set) and `AttendanceService.register_scan()`'s Live Sync cross-station duplicate check called `requests.*()` directly on the Qt main thread, blocking the entire event loop — including barcode-scanner keyboard input — for however long the network call took. Live Sync's check was the worst offender since it fires on every scan and every station hits the same shared backend, so backend slowness froze every station in lockstep. Added `qt_bridge.call_without_freezing_ui()`, which runs the call on a worker thread while pumping the calling thread's Qt event loop, preserving the existing synchronous return-value contract (e.g. block-mode duplicate rejection still gates before the scan is recorded) without freezing the UI. Falls back to a direct call when no `QApplication` exists, so no test behavior changes. New `tests/test_qt_bridge.py` proves the event loop stays pumped during the wait.

## v2.1.0 (2026-08-26)

### Added

- **Admin/settings panel keyboard support** (Enter, Escape, Tab, arrow keys). Enter confirms PIN/rename/delete-confirmation inputs. Escape steps back one level in nested admin views (settings → actions, confirm → actions) instead of always fully closing. Tab/Shift+Tab trap focus within the open admin view, wrapping at the first/last focusable element. Arrow Up/Down move focus the same as Tab, skipped on range sliders/`<select>` since those use the arrow keys natively for their own value. Fixed a regression where Tab on the plain scan screen blurred the barcode input with nothing catching the refocus. Focus indicator is a soft blurred glow instead of a hard outline.
- **Confetti burst on successful scans**, admin-toggleable (off by default via `config.CONFETTI_ENABLED`). Fires only on a genuinely new match (matched and not a duplicate) — the same condition the existing voice-greeting logic uses. Non-interactive canvas overlay, origin anchored to the barcode input's on-screen position, persisted across restarts.

This release also bundles everything from the 2026-08-24 entries below (sync coordinator bugfixes, search ranking, corrupt-roster crash fix). Tagged as `v2.1.0`.

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
