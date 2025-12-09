# Track Attendance

Production-ready desktop application for scanning QR/1D barcodes, matching them against a roster, logging to SQLite, exporting to XLSX, and syncing to a cloud API. Built with Python and a PyQt6-hosted web UI for a kiosk-style experience.

## Project Overview
- 🚀 **Production-ready**: Offline-first desktop shell, packaged for Windows 10/11 via PyInstaller.
- ✅ **Cloud Sync Enabled**: Optional sync to a Google Cloud Run API; runs fully offline if no network is available.
- 🔒 **Privacy-first**: Only badge/timestamp/station are synced; employee names stay local.
- 🖥️ **Kiosk UX**: Frameless PyQt window hosting a modern web UI with live feedback, counters, and recent history.

## System Requirements
- Windows 10/11 (packaged build target).
- Python 3.11+ recommended (PyQt6 + WebEngine required).
- Keyboard-emulating barcode scanner (manual typing + Enter works for testing).

## Feature Highlights
- 🔍 Barcode-first workflow; normalizes input before writing to the database.
- 📊 Instant feedback banner, dashboard counters, and recent-history list.
- 🎨 Compact UI with optimized spacing; sync controls inline with stats.
- 🔄 Manual sync button (spinning icon during sync) and idle-triggered auto-sync.
- 🔍 Unknowns captured as “Not matched” for later reconciliation.
- 📈 One-click exports plus automatic export on shutdown (after a sync attempt).
- 🌐 Offline-first assets; runs without network access.
- 🛡 Graceful error handling and fallback UI if web assets fail to load.

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
   - Set `CLOUD_API_URL`, `CLOUD_API_KEY`, `CLOUD_SYNC_BATCH_SIZE` in `config.py`.
   - Tune auto-sync via `AUTO_SYNC_*` settings, or set `AUTO_SYNC_ENABLED = False` to disable.
   - Keep real API keys out of commits.

## Running the App
```bash
python main.py
```
- Prompts for a station name on first launch (saved in SQLite).
- Opens frameless and fullscreen by default (`config.SHOW_FULL_SCREEN` / `config.ENABLE_FADE_ANIMATION`).
- Shows “Awaiting first scan” until the first badge is recorded.

## Cloud Synchronization
- **Manual sync**: Dashboard sync button tests connectivity then pushes pending scans; status text shows success/error.
- **Auto-Sync (v1.2.0)**:
  - Idle detection: triggers only after `AUTO_SYNC_IDLE_SECONDS` with no scans.
  - Connectivity check: hits API root before syncing.
  - Timing: checks every `AUTO_SYNC_CHECK_INTERVAL_SECONDS`.
  - Conditions: idle, pending scans ≥ `AUTO_SYNC_MIN_PENDING_SCANS`, no active sync.
  - Messages: start/success/fail messages auto-clear after `AUTO_SYNC_MESSAGE_DURATION_MS`.
- **Sync-all option**: `sync_pending_scans(sync_all=True, max_batches=n)` flushes all pending scans in batches (opt-in; default is one batch) for admin or stress-test scenarios.
- **Shutdown flow**: On close, attempts a sync for pending scans (skips if offline or errors), then exports; UI overlay shows sync/export status.
- **Batching**: `sync_pending_scans` uploads batches and marks records `synced`/`failed` in SQLite with stats.

### Cloud API Configuration (config.py)
```python
CLOUD_API_URL = "https://trackattendance-api-969370105809.asia-southeast1.run.app"
CLOUD_API_KEY = "your-api-key-here"
CLOUD_SYNC_BATCH_SIZE = 100
```

### Auto-Sync Configuration
```python
AUTO_SYNC_ENABLED = True
AUTO_SYNC_IDLE_SECONDS = 30
AUTO_SYNC_CHECK_INTERVAL_SECONDS = 60
AUTO_SYNC_MIN_PENDING_SCANS = 1
AUTO_SYNC_SHOW_START_MESSAGE = True
AUTO_SYNC_SHOW_COMPLETE_MESSAGE = True
AUTO_SYNC_MESSAGE_DURATION_MS = 3000
AUTO_SYNC_CONNECTION_TIMEOUT = 5
```

## UI/UX Notes
- Sync status inline with stats; 30px circular sync icon (bright blue #00A3E0) with spin animation while syncing.
- Color use: Blue (#00A3E0) for manual sync, Green (#86bc25) for auto-sync success, Red for errors.
- Optimized spacing yields 3–5 more visible history rows; responsive layout for different screen sizes.

## Data & Exports
- Runtime data in `data/` (SQLite DB, employee workbook); ignored by git.
- Exports: `exports/Checkins_<station>_<timestamp>.xlsx` with submitted value, match flag, roster columns, station, timestamp.
- Automatic export on shutdown (after optional sync attempt); manual export from UI any time.

## Testing & Utilities
- `tests/stress_full_app.py` drives the PyQt window end-to-end.
  - Flags: `--iterations`, `--sample-size`, `--delay-ms`, `--no-specials`, `--no-show-window`, `--windowed`, `--disable-fade`, `--verbose`.
  - Default behavior: shows the full UI in fullscreen when run with no flags; use `--no-show-window` (headless) or `--windowed` (non-fullscreen) to change it.
  - Examples:
    ```bash
    # Fast, headless smoke test
    python tests/stress_full_app.py --iterations 50 --delay-ms 0 --no-show-window --disable-fade

    # Windowed with sampled employees only
    python tests/stress_full_app.py --iterations 100 --sample-size 40 --no-specials --windowed --delay-ms 30

    # Explicit barcode list
    python tests/stress_full_app.py 101117 101118 101119 --iterations 30 --delay-ms 10
    ```
  - Behavior: checks cloud connectivity before bulk sync; if offline, skips sync and proceeds to export. After syncing, holds the window open for 3 seconds so you can view counters.
- `tests/simulate_scans.py`: submits barcodes to `web/index.html` without the desktop shell.
- Sync diagnostics: `test_production_sync.py`, `test_batch_sync.py`, `test_connection_scenarios.py`, `debug_sync_performance.py`, `reset_failed_scans.py`, `migrate_sync_schema.py`, `create_test_scan.py`.
- Timestamp check: `tests/test_utc_timestamps.py` verifies UTC `Z` suffix format.

## Packaging
```bash
pyinstaller TrackAttendance.spec
```
- Output: `dist/TrackAttendance/TrackAttendance.exe`; keep `data/` alongside the executable so scans/exports persist.

## Repository Layout
- `main.py` — PyQt6 entry, window lifecycle, shutdown sync/export, AutoSyncManager wiring.
- `attendance.py` / `database.py` — roster import, scan recording, SQLite access, XLSX export.
- `sync.py` — cloud sync client (batch upload, idempotency key generation).
- `config.py` — API endpoint/key, auto-sync cadence, UI flags.
- `web/` — HTML/CSS/JS for the embedded UI (Materialize, Inter, Material Icons).
- `tests/` — simulation, stress, and diagnostics scripts.
- `assets/` + `TrackAttendance.spec` — packaging assets and PyInstaller config.
- `data/`, `exports/` — runtime storage (ignored by git); `Backup/` — archived experiments.

## Version History (high level)
- **Current (Dec 2025)** — Shutdown sync before export (Issue #8), sync-all option for cloud uploads (`sync_pending_scans(sync_all=True)`), and stress harness improvements (connection test before sync, 3s post-sync hold to view results).
- **v1.2.0** — Auto-Sync Intelligence: idle detection, connectivity check, inline status updates, configurable via `config.py`.
- **v1.1.0** — Sync status UI redesign: compact layout, spinning sync icon, space optimization.
- **v1.0.0** — Initial production cloud sync: batch uploads, idempotency, offline-first.

## Data Privacy
- Do not commit `data/database.db`, `data/employee.xlsx`, or generated exports. Keep sensitive rosters local.
