# Handoff: Career Level + Lucky Draw / Unique Scans export (2026-11-23)

Repo: `C:\Workspace\Projects\trackattendance-latest` (the correct, current repo; `..\trackattendance-frontend` is an older checkout of the same GitHub remote — don't edit it).
Nothing is committed. See `git diff` for the code; this doc only records what the diff doesn't.

## Decisions (LOCKED, from the user)
- New roster column `Career Level` (numeric 0–9 in `data/employee.xlsx`). Optional column, stored as a normalised string.
- **Lucky Draw** sheet: one row per rostered attendee (first scan overall), **no Email**, excludes Career Level **9 (Partner)** and **0 (Intern)**.
- **Unique Scans (Per Day)** sheet: one row per employee per calendar day, first scan of that day. Raw duplicates stay in "All Scans".
- Only the **Dashboard report** (`dashboard.py` `export_to_excel`, built from cloud scans across all stations) is changed. Local `Checkins_*.xlsx` export (`attendance.py` `export_scans`) deliberately untouched.
- No "By Career Level" breakdown.
- Old "Deduplicated Attendance" sheet **removed** (name unclear). Consequence: the cross-station-duplicate flag no longer exists anywhere; offered a "Stations Scanned" column on Unique Scans (Per Day) — user hasn't answered.

## Done
- `database.py`: `career_level` on `EmployeeRecord`, `employees` table (ALTER migration), insert/load.
- `attendance.py`: roster reads Career Level; `_normalize_career_level`; `ROSTER_IMPORT_VERSION = "2"` stored in `roster_meta.import_version` so an unchanged roster file is re-imported once after upgrade (found by testing: without it existing DBs kept blank Career Level).
- `dashboard.py`: Career Level column in All Scans / Not Yet Scanned; new sheets above via `_write_simple_sheet`; `LUCKY_DRAW_EXCLUDED_LEVELS`.
- `tests/test_dashboard.py`: new test for career level/per-day/lucky draw; removed cross-station test; unmatched-scan test retargeted.
- `docs/API.md`, `docs/SYNC.md` references updated (`CHANGELOG.md`/`README.md` history left as-is).

## Verified
- `pytest tests/test_dashboard.py tests/test_roster_bootstrap_corrupt_file.py tests/test_bu_export.py tests/test_excel_export.py tests/test_search_employee_prefix_priority.py` — pass.
- Test export from a copy of the real scanned DB (59 scans, station TEST, 58 unique employees): Unique per day 58, Lucky Draw 47 (58 − 5 level 9 − 6 level 0). Output: `exports/_test_export_career_level.xlsx` (gitignored; a copy also sits in `..\trackattendance-frontend\exports`, safe to delete).

## Not done / open
- Full `pytest tests` run errors in pytest output capture (unrelated to the change); only the files above were run. Typecheck/lint not run.
- Cloud API was mocked in the test export; real multi-station / multi-day output unverified.
- No commit. Not rebuilt/installed (`build.bat` installs to `C:\TrackAttendance`).
- Not ported to the saas fork (`bash scripts/sync-to-saas.sh`) — only if the user wants.
- Docs: consider adding Career Level / new sheets to `CHANGELOG.md`/`README.md` and a roster-column note in `docs/`.
- Caveat to remember: Monitoring Mode (Admin → Cloud Sync, `config.CLOUD_READ_ONLY`) blocks all uploads; stations with it on won't appear in the cloud-built Dashboard report.

## Suggested skills
- `code-review` (or `system-review`) on the diff before committing.
- `pyinstaller-windows-deployment` if rebuilding/installing the exe.
- `oracle-skills:rrr` for the session retrospective after commit.
