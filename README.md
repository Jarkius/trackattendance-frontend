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
- Opens frameless and fullscreen by default (controlled by `config.SHOW_FULL_SCREEN = True` and `config.ENABLE_FADE_ANIMATION = True`).
- Shows "Awaiting first scan" until the first badge is recorded.
- Press `Escape` to close the application; at shutdown, syncs pending scans (if online) then exports all records to XLSX.

## Cloud Synchronization

### Sync Mechanism Overview
The sync system is **offline-first** by design. All scans are recorded locally to SQLite with a `sync_status` field. Synchronization happens in three phases:

1. **Status Tracking**: Each scan record has a `sync_status`:
   - `pending` — Not yet uploaded to cloud
   - `synced` — Successfully uploaded (with idempotency key to prevent duplicates)
   - `failed` — Upload attempt failed (network error, API rejection, etc.)

2. **Batch Processing**: Syncs happen in configurable batches (default 100 scans per batch):
   - Each batch is uploaded atomically; if any record fails, the entire batch is marked `failed`
   - Batches are processed sequentially; no batches run in parallel
   - Each batch generates a unique idempotency key to ensure cloud API doesn't process duplicates

3. **Sync Flow**:
   ```
   Query pending scans → Check connectivity → Upload batch → Mark as synced/failed → Repeat until done
   ```

### Manual Sync
- User clicks the sync button on the dashboard
- App tests connectivity to the cloud API (5-second timeout by default)
- If online: uploads one batch of pending scans (default 100), updates UI counters, shows success/error message
- If offline: shows error message; scans remain `pending` in the database
- Sync button shows a spinning blue icon (#00A3E0) while syncing; message auto-clears after `AUTO_SYNC_MESSAGE_DURATION_MS`

### Auto-Sync Mechanism (v1.2.0+)
Automatically syncs pending scans when certain conditions are met:

**Trigger Conditions**:
- Application is idle (no scans for ≥ `AUTO_SYNC_IDLE_SECONDS`, default 30s)
- At least `AUTO_SYNC_MIN_PENDING_SCANS` scans pending (default 1)
- No sync operation is already in progress
- Auto-sync is enabled (`AUTO_SYNC_ENABLED = True`)

**Idle Detection**:
- Timer starts after each scan is recorded
- Resets every time a new scan arrives
- After idle threshold is reached, checks every `AUTO_SYNC_CHECK_INTERVAL_SECONDS` (default 60s)
- Does not interrupt active scanning; waits for the idle period

**Execution**:
- Tests connectivity to cloud API
- If online: uploads one batch (100 scans by default)
- If offline: silent fail; retries on next idle period
- Shows brief success/fail message on UI (auto-clears after `AUTO_SYNC_MESSAGE_DURATION_MS`)

### Idle Time Configuration
```python
AUTO_SYNC_IDLE_SECONDS = 30              # Time with no scans before sync trigger
AUTO_SYNC_CHECK_INTERVAL_SECONDS = 60    # How often to check idle condition
AUTO_SYNC_MIN_PENDING_SCANS = 1          # Minimum pending to trigger sync
AUTO_SYNC_CONNECTION_TIMEOUT = 5         # Seconds to wait for connectivity check
```

**Example Timeline**:
```
10:00:00 — Scan recorded; timer starts
10:00:30 — 30 seconds elapsed with no scans; idle condition met
10:00:35 — Check interval fires; tests API connectivity
10:00:40 — If online, uploads batch and clears pending counter
10:01:00 — Check interval fires again if pending still exist
```

### Offline/No Internet Scenarios

**Scenario 1: Start Offline**
- App starts without network access
- Scans are recorded to SQLite normally
- Auto-sync checks fail silently (no error shown unless `VERBOSE` mode)
- Manual sync button shows "Connection failed" message if user presses sync
- All scans remain `pending` in database
- App continues to function fully offline

**Scenario 2: Go Offline Mid-Session**
- App loses network connection after recording scans
- Active sync operation (if running) fails; scans stay `pending`
- Next auto-sync check detects no connectivity; waits for connection
- When connection returns, next idle period triggers sync automatically
- User does not need to restart or manually retry

**Scenario 3: Intermittent Connection**
- Connectivity checks use timeout of `AUTO_SYNC_CONNECTION_TIMEOUT` (5s default)
- If API responds slowly but eventually succeeds, sync completes normally
- If check times out, sync is skipped; no corrupted partial batches
- Idempotency keys ensure duplicate protection if API receives batch twice

**Scenario 4: Sync Failure (API Error)**
- If API rejects a batch (HTTP 5xx, validation error, etc.), batch is marked `failed`
- Failed scans do not retry automatically; manual sync or admin tools can reprocess
- See `tests/reset_failed_scans.py` to reset failed scans back to `pending`

### Sync Status Information

**Dashboard Display**:
- **Pending Counter**: Shows number of scans not yet synced (green badge if auto-sync enabled)
- **Synced Counter**: Total successfully uploaded scans
- **Failed Counter**: Scans that failed to upload (shown in red if any exist)
- **Sync Icon**: Blue spinning icon during active sync; still when idle
- **Status Message**: "Syncing...", "Sync failed", "Sync complete" (auto-clears)

**Database View**:
```bash
# Check sync statistics (see `attendance.py`)
db = Database()
stats = db.get_sync_statistics()
# Returns: { "pending": 42, "synced": 1058, "failed": 3 }
```

**Logs**:
- `sync.py` logs all upload attempts with batch sizes, success/failure counts, and API responses
- Enable `--verbose` flag in stress test to see detailed sync logs

### Sync-All Option
For admin or stress-test scenarios, sync all pending scans in multiple batches:

```python
# Sync one batch only (default)
result = sync_service.sync_pending_scans()
# Returns: { "synced": 100, "failed": 0, "pending": 45 }

# Sync all pending scans until none remain
result = sync_service.sync_pending_scans(sync_all=True, max_batches=50)
# Returns: { "synced": 145, "failed": 0, "pending": 0, "batches": 2 }

# Sync all with no batch limit (use with caution)
result = sync_service.sync_pending_scans(sync_all=True)
```

### Shutdown Flow
When the application closes:

1. **Sync Phase** (if any pending scans):
   - Tests API connectivity
   - If online: uploads all pending batches (respects `CLOUD_SYNC_BATCH_SIZE`)
   - Shows overlay: "Syncing X pending scan(s)..."
   - If offline or sync fails: shows warning; continues to export

2. **Export Phase**:
   - Exports all records (including newly synced ones) to XLSX
   - Shows overlay: "Exporting data..."
   - File saved to `exports/Checkins_<station>_<timestamp>.xlsx`

3. **Close Phase**:
   - Shows final status ("Ready to close")
   - Closes window after brief delay (1.5s default)

**Note**: Shutdown sync uploads all batches (not just one) to ensure data is not lost on close.

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
- `tests/stress_full_app.py` drives the PyQt window end-to-end with optional cloud sync.
  - Flags: `--iterations`, `--sample-size`, `--delay-ms`, `--no-specials`, `--no-show-window`, `--fullscreen`, `--disable-fade`, `--verbose`.
  - Default behavior: shows the UI window maximized (not fullscreen); use `--no-show-window` for headless or `--fullscreen` to force full screen mode.
  - Sync behavior: tests cloud connectivity before syncing; if online, uploads all pending scans (sync_all mode); if offline, skips sync and proceeds to export. After successful sync, holds the window open for 10 seconds so you can view final counters.
  - Examples:
    ```bash
    # Fast, headless smoke test (no window, no sync UI)
    python tests/stress_full_app.py --iterations 50 --delay-ms 0 --no-show-window --disable-fade

    # Maximized window with sampled employees only
    python tests/stress_full_app.py --iterations 100 --sample-size 40 --no-specials --delay-ms 30

    # Explicit barcode list with fullscreen
    python tests/stress_full_app.py 101117 101118 101119 --iterations 30 --delay-ms 10 --fullscreen
    ```
- `tests/simulate_scans.py`: submits barcodes to `web/index.html` without the desktop shell.
- Sync diagnostics: `test_production_sync.py`, `test_batch_sync.py`, `test_connection_scenarios.py`, `debug_sync_performance.py`, `reset_failed_scans.py`, `migrate_sync_schema.py`, `create_test_scan.py`.
- Timestamp check: `tests/test_utc_timestamps.py` verifies UTC `Z` suffix format.

## Development Workflow

### Common Development Tasks

**Check sync statistics in database**:
```python
from attendance import Database
db = Database('data/database.db')
stats = db.get_sync_statistics()
print(f"Pending: {stats['pending']}, Synced: {stats['synced']}, Failed: {stats['failed']}")
```

**Reset failed scans back to pending**:
```bash
python tests/reset_failed_scans.py
```

**Test cloud connectivity without syncing**:
```bash
python tests/test_connection_scenarios.py
```

**Run full stress test with sync verification**:
```bash
# 2000 iterations with cloud sync after completion
python tests/stress_full_app.py --iterations 2000 --delay-ms 100 --sample-size 50
```

**Check database schema**:
```bash
sqlite3 data/database.db ".schema"
```

### Environment Variables

Optional: Create `.env` file to override config defaults:
```bash
CLOUD_API_URL=<your-api-url>
CLOUD_API_KEY=<your-api-key>
CLOUD_SYNC_BATCH_SIZE=100
AUTO_SYNC_ENABLED=True
SHOW_FULL_SCREEN=False
```

## Packaging

```bash
pyinstaller TrackAttendance.spec
```
- Output: `dist/TrackAttendance/TrackAttendance.exe`; keep `data/` alongside the executable so scans/exports persist.
- Before packaging, update version numbers in `TrackAttendance.spec` and commit changes.

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
- **Current (Dec 2025)** — Shutdown sync before export (Issue #8), sync-all option for cloud uploads (`sync_pending_scans(sync_all=True)`), and stress harness improvements (connection test before sync, maximized window by default, 10s post-sync hold to view results). **Known Issue**: UI pending counter may not update to 0 before window closes in stress test (Issue #11, under investigation).
- **v1.2.0** — Auto-Sync Intelligence: idle detection, connectivity check, inline status updates, configurable via `config.py`.
- **v1.1.0** — Sync status UI redesign: compact layout, spinning sync icon, space optimization.
- **v1.0.0** — Initial production cloud sync: batch uploads, idempotency, offline-first.

## Known Issues & Troubleshooting

### Issue #11: Pending Counter May Not Update to 0 in Stress Test
**Symptom**: After syncing in the stress test, the UI shows an outdated pending counter (e.g., "3 pending") even though the database shows `Pending: 0` and the sync was successful.

**Root Cause**: Multiple async layers in JavaScript callback execution (`runJavaScript()` → `updateSyncStatus()` → bridge callback) can complete after the window closes.

**Workaround**: Check the console output; the test prints final sync statistics including database state. The database state is the source of truth.

**Status**: Under investigation; proposed solutions include direct DOM manipulation instead of async callbacks (see GitHub Issue #11).

**Affected**: `tests/stress_full_app.py` only; production app works correctly.

### Sync Failures with No Error Message
**Symptom**: Manual sync button shows no message (silent failure).

**Possible Causes**:
1. Network unreachable (no connectivity to cloud API)
2. API key invalid or expired
3. API endpoint misconfigured in `config.py`

**Debug Steps**:
1. Verify network connectivity: `ping api-endpoint-domain`
2. Check `config.py` for correct `CLOUD_API_URL` and `CLOUD_API_KEY`
3. Run `tests/test_connection_scenarios.py` to test connectivity
4. Enable verbose logging: `python main.py` with `--verbose` flag if available

### Offline Mode Appears to Break Auto-Sync
**Symptom**: Auto-sync stops working after going offline; doesn't resume when connection returns.

**Expected Behavior**: This is correct. Auto-sync silently fails when offline and will retry on the next idle check. No action needed; scans remain `pending` and will sync automatically when connection returns.

## Data Privacy
- Do not commit `data/database.db`, `data/employee.xlsx`, or generated exports. Keep sensitive rosters local.
