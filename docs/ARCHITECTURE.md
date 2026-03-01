# Architecture Document: Track Attendance

## 1. Overview

Track Attendance ships as a PyQt6 desktop shell that hosts a single-page web interface. Python owns process orchestration, scanners, persistence, and exporting, while the embedded web UI handles rendering and operator interactions.

## 2. Components

### 2.1 Desktop Shell (Python / PyQt6)
- **Entry point:** `main.py`
- **Responsibilities:**
  - Initialises `QApplication`, `QMainWindow`, and `QWebEngineView`.
  - Ensures operational data exists (`data/database.db`, station name prompt, employee bootstrap).
  - Registers the `Api` object on a `QWebChannel` so JavaScript can call back-end slots (`submit_scan`, `export_scans`, `get_initial_data`, `close_window`, `finalize_export_close`).
  - Applies window chrome (frameless, fade-in animation) and handles close events, including auto-export logic.
  - Manages critical startup failures, such as prompting for a station name if unconfigured or displaying a fallback UI if web assets are missing.

### 2.2 Web Interface (HTML/CSS/JavaScript)
- **Location:** `web/index.html`, `web/css/style.css`, `web/script.js`
- **Responsibilities:**
  - Renders counters, live feedback banner, recent scan history, export overlay, and placeholder states.
  - Queues channel calls until the bridge is ready and updates the DOM using the payloads returned from Python.
  - Provides accessibility cues (focus management, aria attributes) and keyboard affordances for scanners.

### 2.3 Local Dashboard (`dashboard.py`)

- **Location:** `dashboard.py`
- **Responsibilities:**
  - Provides a local operator dashboard with Excel export capability.
  - Displays per-BU attendance breakdown so operators can monitor business unit coverage at a glance.
  - Reads an optional `email` column from the roster file; the value is cached at scan time and displayed locally.
  - The `email` field is **never included in sync payloads** — it stays local to the device at all times.

### 2.4 Data Layer
- **Location:** `attendance.py`, `database.py`, `data/`
- **Responsibilities:**
  - Manages SQLite persistence for stations, employees, and scan history (`DatabaseManager`).
  - Coordinates workbook imports, scan registration, and XLSX export formatting (`AttendanceService`).
  - Ensures unmatched scans are captured with flags for follow-up, and exposes aggregate counts.

## 3. Communication Flow

1. **Startup**
   - `main.py` builds the window, registers `Api`, loads `web/index.html`, and blocks until the page is ready.
   - JavaScript initialises, waits for the channel, requests initial payload (`api.get_initial_data()`), and renders the dashboard.

2. **Scanning**
   - A scanner sends keystrokes to the hidden input. JavaScript captures the Enter event and calls `api.submit_scan(badgeId)`.
   - Python sanitises the badge, looks up the employee, records the entry, and returns a dictionary with match flag, history, and updated totals.
   - JavaScript refreshes counters, recent history, and the live feedback banner. Unknown entries show `Not matched` but are still stored.

3. **Exporting**
   - From the UI, `export_scans` is invoked via the channel, prompting Python to gather all scans and write an XLSX file under `exports/`.
   - When the operator closes the window, the PyQt `closeEvent` handler runs an export and uses a dedicated JavaScript function (`window.__handleExportShutdown`) to display the result in the UI overlay before closing.

## 4. Mobile Dashboard Data Flow

The mobile dashboard is a single HTML file (`public/index.html`) served by `@fastify/static` from the cloud API. It requires no authentication and is rate-limited at 30 requests per minute.

```
Local kiosk (PyQt6)
  │
  ├─ Scan recorded → SQLite (local)
  │
  ├─ Auto/manual sync → POST /v1/scans/batch → Cloud PostgreSQL
  │
  └─ Health check (on first success) → POST /v1/roster/summary → Cloud PostgreSQL
                                         (hash-based dedup, BU counts only)

Cloud API (Cloud Run)
  │
  └─ GET /v1/dashboard/public/stats ← polled every 30s by mobile dashboard HTML
       (aggregates scan data + roster summary from PostgreSQL)

Mobile dashboard (public/index.html)
  - Attendance rate %
  - Scanned / total registered
  - Per-BU breakdown with registered counts
  - Per-station scan counts
  - No auth required
```

### Email Field

The roster spreadsheet supports an optional `email` column. When present:
- The value is read and cached in the local SQLite database at roster import time.
- It is surfaced in the local dashboard (`dashboard.py`) for operator reference.
- It is **never transmitted** to the cloud API in any sync payload (scan batches, roster summaries, or health checks).

### Roster Summary Sync Flow

```
main thread
  └─ Startup → reads SQLite employees table → builds in-memory BU cache
                (employee counts grouped by business_unit / sl_l1_desc)

health check thread (background)
  └─ First successful API ping
       └─ calls sync_roster_summary_from_data()
            ├─ reads BU cache from memory
            ├─ serialises payload + computes SHA256 hash
            ├─ compares with last accepted hash
            └─ if changed → POST /v1/roster/summary → cache new hash
```

## 5. Error Handling & Resilience

- **UI Load Failure:** If `web/index.html` cannot be loaded, the `QWebEngineView` will render a static `FALLBACK_ERROR_HTML` page to notify the user of the misconfiguration.
- **Missing Employee Roster:** On startup, if `data/employee.xlsx` is not found and the employee table is empty, the application presents a `QMessageBox` warning before proceeding. Scans will be recorded as "unmatched" in this state.
- **Export Failures:** Both manual and on-close export operations are wrapped in `try...except` blocks. If an error occurs, the `export-overlay` in the UI is invoked with a failure state, providing feedback to the user instead of crashing.

## 6. Packaging & Runtime Assets

- **Icon & Spec:** `assets/track_attendance.ico`, `TrackAttendance.spec` configure PyInstaller builds.
- **Embedded assets:** `web/` and `assets/` are bundled so the executable can run without network access.
- **Operational data:** `data/` and `exports/` stay outside the bundle; they are created/ignored at runtime to protect sensitive information.

## 7. External Dependencies
The web interface relies on locally-hosted, open-source assets for its presentation layer. This ensures the application can run fully offline without fetching resources from external CDNs.

- **Typography:** The primary font is Inter, served from `web/fonts/`. It is chosen for its high legibility on screens.
- **Icons:** UI icons are provided by the Material Icons set, served from `web/fonts/` and defined in `web/css/material-icons.css`. This provides a consistent and modern visual language for interactive elements.

## 8. Backend Dependencies

- **PyQt6 / PyQt6-WebEngine:** windowing, web engine, and Qt channels.
- **openpyxl:** workbook import/export support.
- **Pillow:** utility helpers (icon generation, optional future imaging needs). Note: Listed as a conceptual dependency for build tasks; not currently included in `requirements.txt`.
- **PyInstaller:** Windows packaging.

These dependencies are pinned in `requirements.txt` to keep builds reproducible.
