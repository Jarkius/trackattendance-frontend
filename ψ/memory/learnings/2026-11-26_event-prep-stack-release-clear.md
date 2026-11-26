---
pattern: Before a release, reproduce CI locally, never move the checkout under a running dev app, and test anything that deletes cloud data only with fakes or one deliberate rehearsal
date: 2026-11-26
source: session: Jarkius/trackattendance-frontend, PRs #121-#124, releases v2.2.0 / v2.2.1 (event prep for 27 Nov, 10 stations)
concepts: [release, ci, stacked-prs, multi-station-clear, sync, hold-screen, deployment, windows]
---

## 1. Stacked PRs hide CI failures

`test.yml` only runs on PRs into `main`. #122 and #123 were stacked on #121, so they never
ran tests, and #121 itself had been red for a day: four new test modules imported PyQt6,
which CI does not install (`requirements-test.txt`), so collection stopped and **no** test ran.

- Rule: every test module that needs Qt starts with `pytest.importorskip("PyQt6")` (the
  older Qt tests already did).
- Reproduce CI before merging: a throwaway venv with only `requirements-test.txt`, then the
  CI command from `.claude/rules/project-verification.md`. It showed the exact 4 errors.

## 2. Never switch branches under a running dev app

The user ran the app from the working tree. Checking out #121's branch for a review fix
removed `plugins/camera/person_detector.py` from disk; clicking People then logged
`cannot import name 'person_detector'` and fell back to Faces. It looked like a product bug.

- Review or fix older branches in a `git worktree`, not by moving the main checkout.
- When the user reports an error mid-session, first check whether the session changed the
  files the running app loads.

## 3. Multi-station clear: one choke point, and the station's own epoch

Clear ALL bumps a cloud `clear_epoch`; stations compare it with their own at each health
check. A station offline during the clear re-uploaded its pre-clear scans on reconnect:
the auto-sync job's `test_connection()` saw the new epoch but uploaded anyway.

- Fix in one place: every upload path (auto, manual, live, shutdown) goes through
  `SyncService.sync_scan_batch_network_only`; it holds the batch while
  `remote_clear_pending()` (station epoch != cloud epoch). Mirror the station epoch into
  `SyncService.local_clear_epoch` wherever it is written, including the initiating station
  (else the guard holds its own new scans until the next health check).
- Pausing sync for a clear needs `try/finally` resume, or one exception stops sync forever.
- Clear ALL hits the live cloud API the stations use. Prove it with fakes
  (`tests/test_clear_rearm.py`) and a fake QWebChannel bridge for the page; run the real
  thing once, deliberately, in the rehearsal.

## 4. "Clear" means "back to event-ready"

The event workflow is: rehearse on all stations, clear, hold screen back up with scans
blocked, Esc per station at opening. Re-arming from `.env` (snapshotted in
`Api._config_defaults` before saved settings load) beats a new remote-command API the day
before an event: it reuses the tested clear channel and needs no cloud change.

## 5. Windows tooling traps

- Grep/ripgrep skips gitignored files: search `logs\trackattendance.log` with
  `Select-String`, not Grep, or "no matches" is a lie.
- `tests/test_encoding_thai.py` and `tests/test_utc_timestamps.py` replace `sys.stdout` on
  Windows, which kills a full pytest run (`I/O operation on closed file`); exclude them
  locally (CI on Linux is fine). `test_native_video.py` can crash a full Windows run but
  passes alone. `test_barrier_reset_integration` is timing-flaky (fails ~1 in 5 on main).
- `build.bat` rebuilds `dist\TrackAttendance` from scratch: anything put there by hand
  (event `.env`, `data\employee.xlsx`) is gone after a rebuild. Keep the event `.env` and
  roster somewhere durable and copy them in after each build.
- `deploy.bat` (robocopy without /PURGE) never deletes on the target: remove retired media
  from `C:\TrackAttendance\media` by hand, or it stays as a fallback.
- In PowerShell, `git rev-parse X^{tree}` gets mangled; use `git diff --quiet A B`.
