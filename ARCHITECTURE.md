# Architecture Document: Track Attendance

## 1. Overview

Track Attendance ships as a PyQt6 desktop shell that hosts a single-page web interface. Python owns process orchestration, scanners, persistence, and exporting, while the embedded web UI handles rendering and operator interactions.

## 2. Components

### 2.1 Desktop Shell (Python / PyQt6)
- **Entry point:** `main.py`
- **Responsibilities:**
  - Initialises `QApplication`, `QMainWindow`, and `QWebEngineView`.
  - Ensures operational data exists (`data/database.db`, station name prompt, employee bootstrap).
  - Registers the `Api` object on a `QWebChannel` so JavaScript can call back-end slots (`submit_scan`, `export_scans`, `get_initial_data`, `close_window`).
  - Applies window chrome (frameless, fade-in animation) and handles close events, including auto-export logic.

### 2.2 Web Interface (HTML/CSS/JavaScript)
- **Location:** `web/index.html`, `web/css/style.css`, `web/script.js`
- **Responsibilities:**
  - Renders counters, live feedback banner, recent scan history, export overlay, and placeholder states.
  - Queues channel calls until the bridge is ready and updates the DOM using the payloads returned from Python.
  - Provides accessibility cues (focus management, aria attributes) and keyboard affordances for scanners.

### 2.3 Data Layer
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
   - When the operator closes the window, the PyQt close handler can run an export and surface the result through the overlay.

## 4. Packaging & Runtime Assets

- **Icon & Spec:** `assets/track_attendance.ico`, `TrackAttendance.spec` configure PyInstaller builds.
- **Embedded assets:** `web/` and `assets/` are bundled so the executable can run without network access.
- **Operational data:** `data/` and `exports/` stay outside the bundle; they are created/ignored at runtime to protect sensitive information.

## 5. External Dependencies

- **PyQt6 / PyQt6-WebEngine:** windowing, web engine, and Qt channels.
- **openpyxl:** workbook import/export support.
- **Pillow:** utility helpers (icon generation, optional future imaging needs).
- **PyInstaller:** Windows packaging.

These dependencies are pinned in `requirements.txt` to keep builds reproducible.
