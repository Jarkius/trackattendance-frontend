# Track Attendance

PyQt6 desktop shell that hosts a local web UI for scanning badge barcodes, matching them against an Excel roster, writing scans to SQLite, exporting to XLSX, and optionally syncing to a cloud API.

## Features
- Keyboard-wedge scanners or manual entry with live feedback and recent-history list.
- Employee matching from `data/employee.xlsx`; unmatched scans are stored with a "not matched" flag for follow-up.
- Local persistence in `data/database.db` with per-station tagging; prompts for a station name on first launch.
- Manual exports to `exports/` plus automatic export (and optional sync) during shutdown.
- Cloud sync via `sync.py` with manual "Sync Now" and idle-triggered auto-sync controlled by `config.py`.
- Offline-first UI assets in `web/`; scanning and exporting work without network access.

## System Requirements
- Windows 10/11 target environment (PyInstaller bundle is Windows-focused).
- Python 3.11+ recommended with PyQt6 and PyQt6-WebEngine.
- Keyboard-emulating barcode scanner for best results (typing + Enter also works).

## Setup
1. Clone the repository and enter the folder.
2. Create/activate a virtual environment:
   ```bash
   python -m venv .venv
   .venv\Scripts\activate  # PowerShell/cmd
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Provide operational data:
   - Place the employee roster at `data/employee.xlsx` with columns `Legacy ID`, `Full Name`, `SL L1 Desc`, `Position Desc`.
   - On first run, a sample `data/exampleof_employee.xlsx` is created if the roster is missing; update it and save as `employee.xlsx`.
   - `data/database.db` is created automatically.
5. Configure sync (optional):
   - Update `config.py` with your `CLOUD_API_URL`, `CLOUD_API_KEY`, and batch size.
   - Tune auto-sync knobs (`AUTO_SYNC_*`) or set `AUTO_SYNC_ENABLED = False` to disable background sync.
   - Keep real API keys out of commits.

## Run the App
```bash
python main.py
```
- The app prompts for a station name on first launch; the value is saved in the database.
- The window opens frameless and fullscreen by default. Edit `config.SHOW_FULL_SCREEN`/`config.ENABLE_FADE_ANIMATION` if you need different behavior.
- Scan a badge (or type and press Enter). The dashboard counters and history update immediately.

## Cloud Sync
- `sync.py` uploads pending scans in batches to the configured API and marks records as `synced`/`failed` in SQLite.
- Manual sync: the "Sync" button in the dashboard tests connectivity, then calls `sync_now` to push pending scans. Status text shows successes or errors.
- Auto-sync: `AutoSyncManager` runs every `AUTO_SYNC_CHECK_INTERVAL_SECONDS`, checks idle time (`AUTO_SYNC_IDLE_SECONDS`), pending count (`AUTO_SYNC_MIN_PENDING_SCANS`), and connectivity before calling `sync_pending_scans`. Status messages clear after `AUTO_SYNC_MESSAGE_DURATION_MS`.
- Shutdown flow: closing the window triggers a sync attempt for pending scans before exporting so cloud state and local exports stay aligned.

## Data & Exports
- Runtime data lives in `data/` (SQLite database, employee workbook). These files are intentionally ignored by git.
- Exports are written to `exports/Checkins_<station>_<timestamp>.xlsx` with submitted value, match flag, roster columns, station, and timestamp.
- Manual exports are available from the UI; a final export runs automatically during shutdown even if sync fails.

## Testing & Utilities
- `tests/stress_full_app.py` drives the PyQt window end-to-end; example:
  ```bash
  python tests/stress_full_app.py --iterations 50 --no-show-window --disable-fade
  ```
- Stress test flags:
  - `--iterations N` (default 200): number of scans to submit.
  - `--sample-size N` (default 50): employee barcodes to sample from `employee.xlsx`.
  - `--delay-ms N` (default 75): delay between scans.
  - `--no-specials`: exclude synthetic invalid barcodes.
  - `--no-show-window`: hide the window (headless).
  - `--windowed`: show the window but not fullscreen.
  - `--disable-fade`: skip the fade animation.
  - `--verbose`: log every scan instead of periodic checkpoints.
- Stress test examples:
  ```bash
  # Fast, headless smoke test
  python tests/stress_full_app.py --iterations 50 --delay-ms 0 --no-show-window --disable-fade

  # Windowed with sampled employees only
  python tests/stress_full_app.py --iterations 100 --sample-size 40 --no-specials --windowed --delay-ms 30

  # Explicit barcode list
  python tests/stress_full_app.py 101117 101118 101119 --iterations 30 --delay-ms 10
  ```
- `tests/simulate_scans.py` loads `web/index.html` and submits a list of barcodes without the desktop shell.
- Sync diagnostics: `test_production_sync.py`, `test_batch_sync.py`, `test_connection_scenarios.py`, `debug_sync_performance.py`, `reset_failed_scans.py`, `migrate_sync_schema.py`, and `create_test_scan.py` help validate API connectivity and database state. They expect a configured API and a local database.
- Timestamp formatting checks: `tests/test_utc_timestamps.py` asserts stored timestamps use the UTC `Z` suffix.

## Packaging
```bash
pyinstaller TrackAttendance.spec
```
- The packaged app lands in `dist/TrackAttendance/`. Keep `data/` alongside the executable so scans and exports persist between runs.

## Repository Layout
- `main.py`: PyQt6 entry point, window lifecycle, shutdown export/sync, auto-sync manager.
- `attendance.py` / `database.py`: employee import, scan recording, SQLite access, and XLSX export.
- `sync.py`: cloud sync client.
- `config.py`: API endpoint/key, auto-sync cadence, and UI flags.
- `web/`: HTML/CSS/JS for the embedded UI (Materialize, Inter, Material Icons).
- `data/`, `exports/`: runtime storage (not version controlled; keep a `.gitkeep` only).
- `tests/`: simulation and diagnostics scripts.
- `assets/` and `TrackAttendance.spec`: packaging assets and PyInstaller configuration.
- `Backup/`: archived experiments (not loaded at runtime).

## Troubleshooting
- If the UI fails to load, a fallback HTML page appears; verify `web/` exists next to `main.py` or inside the PyInstaller bundle.
- If employee data is missing, the app creates `data/exampleof_employee.xlsx` and flags unmatched scans; replace it with a real `employee.xlsx`.
- Ensure Qt WebEngine is installed (from `requirements.txt`) when running tests that spin up a `QWebEngineView`.
