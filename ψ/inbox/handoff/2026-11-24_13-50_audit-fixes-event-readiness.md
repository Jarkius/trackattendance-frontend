# Handoff: audit fixes v2.1.11 and event readiness (2026-11-24)

Event: Friday 2026-11-28, about 1,900 attendees and 10 kiosks.
Merged: frontend PR #113 (v2.1.11, issues #101–#112 closed) and API PRs #28 and #29, both deployed. What changed is in `CHANGELOG.md` here and in the API repo. The API-side state and evidence are in `trackattendance-api/docs/handoffs/2026-11-24_event-readiness.md`.

## Watch out: uncommitted Career Level work on another machine
`ψ/inbox/handoff/2026-11-23_16-45_career-level-lucky-draw.md` describes uncommitted Career Level / Lucky Draw / Unique Scans work in `C:\Workspace\Projects\trackattendance-latest`. That folder is not on this machine, and none of that work is on `main`. v2.1.11 rewrote much of `dashboard.py`'s export (Summary buckets, Walk-ins sheet, `compute_bu_breakdown`, `classify_export_scan`, formula neutralising), so pulling `main` into that checkout **will conflict in `dashboard.py` and `tests/test_dashboard.py`**. Merge carefully. Keep `neutralize_formulas(wb)` before every save, and count by the normalised `legacy_id`.

## Decisions (LOCKED, from the user)
- Attendance buckets:
  - **registered attended** is the rate numerator;
  - **walk-ins** are manual, unmatched entries, synced to the cloud and counted separately;
  - **unknown badges** are counted separately and need review.
- Cross-station duplicate scans are allowed during the event and handled later in the report. **Do not enable `IMMEDIATE_SYNC_ENABLED`.**
- Cloud Run min instances is 1 for the event; lower it to 0 afterwards.

## Verified
- Local CI command: 522 passed, 1 skipped. GitHub CI `test` passed on PR #113.
- Live end-to-end test against prod (throwaway station, cleaned up) covered:
  - sync and idempotent resend;
  - bucket deltas (matched +2, walk-ins +2, unknown +1);
  - the kiosk dashboard reading cloud buckets;
  - the export, where `=E2E+1` stays text.
- Live load test: 8 stations at about 7× peak and a burst of 2,400 scans. All arrived, with no duplicates or errors.

## Not verified / open
- **Real-kiosk test with a physical scanner.** The scanner-input fixes were only checked with simulated keystrokes in an offscreen QWebEngine harness. Check these:
  - rapid scans during a duplicate alert;
  - a scan while the lookup box is open;
  - the new Walk-ins and Unknown badges figures.
- **Rebuild and install v2.1.11 on all 10 kiosks** (`build.bat`). Confirm the version in each window title.
- **Kiosk sync timing:** auto-sync only runs after `AUTO_SYNC_IDLE_SECONDS` (30) with no scans, so during a steady queue a busy kiosk may not upload until it quietens. No data is lost; the cloud dashboard lags. The user accepted this.
- **Do not rename stations mid-event:** `admin_rename_station` updates SQLite but not the cached names in `AttendanceService` and `SyncService`. This is pre-existing.
- **Clear the cloud scans** (66 at handoff) before doors open.
- **Startup roster dialogs are modal.** This is pre-existing; they only appear on real roster problems.
- **Not ported to the saas fork** (`bash scripts/sync-to-saas.sh`).
