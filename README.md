# Track Attendance

## Project Overview

Track Attendance is a desktop companion for scanning QR or 1D barcodes, logging attendance instantly, and echoing results to a modern web UI hosted inside PyQt6. Operators get immediate feedback, supervisors get working exports, and the whole flow runs locally with no external services.

## Feature Highlights

- **Barcode-first workflow:** Accepts keyboard wedge scanners or manual entry and normalises every submission before it hits the database.
- **Instant feedback:** Live banner, dashboard counters, and recent-history list update with each scan so problems are spotted in seconds.
- **Auto-captured unknowns:** Mistyped or unrecognised IDs are stored with a “Not matched” flag for later reconciliation.
- **One-click exports:** XLSX reports land in `exports/` with columns for submitted value, match status, and station metadata.
- **Graceful shutdown:** Closing the window can trigger an export overlay, while stress tools can bypass the UI and export directly.

## Setup

1. **Clone the repository**
   ```bash
   git clone <repository_url>
   cd QR
   ```

2. **Create a virtual environment**
   ```bash
   python -m venv .venv
   ```

3. **Activate the environment**
   - Windows
     ```bash
     .venv\Scripts\activate
     ```
   - macOS/Linux
     ```bash
     source .venv/bin/activate
     ```

4. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```
   The PyQt6 + WebEngine stack is required; other libraries support reporting (openpyxl) and testing utilities.

5. **Prepare operational data**
   - Place the employee roster at `data/employee.xlsx` (columns: Legacy ID, Full Name, SL L1 Desc, Position Desc).
   - Move any existing `database.db` into `data/` or let the app bootstrap a fresh file on first run.
   - For packaged builds, keep the `data/` folder alongside `TrackAttendance.exe` so edits persist between runs.

## Running the App

```bash
python main.py
```

A placeholder “Awaiting first scan” row appears in the history list until the first badge is recorded.

## Building a Windows Executable

PyInstaller is already configured via `TrackAttendance.spec`. Run:

```bash
pyinstaller TrackAttendance.spec
```

The packaged app (with custom icon and bundled web assets) is produced in `dist/TrackAttendance/TrackAttendance.exe`. Distribute the entire folder so relative assets stay intact.

## Testing & Diagnostics

- `python tests\simulate_scans.py` — Exercises the web interface in an off-screen `QWebEngineView`. Expect `[ok]` log lines even when the PyQt bridge is unavailable.
- `python tests\stress_full_app.py` — Drives the full PyQt window using samples from `data/employee.xlsx` plus synthetic invalid barcodes. Key flags:
  - `--sample-size N` — how many employee IDs to draw from the workbook (default 50).
  - `--iterations N` / `--delay-ms N` — control run length and pacing.
  - `--no-specials` — skip synthetic invalid inputs (`999999`, `DROP TABLE;`, etc.).
  - `--windowed`, `--no-show-window`, `--disable-fade` — adjust presentation for CI or demos.

Example runs
```bash
# Fast, headless smoke test
python tests\stress_full_app.py --iterations 50 --delay-ms 0 --no-show-window --disable-fade

# Window visible with sampled employees only
python tests\stress_full_app.py --iterations 100 --sample-size 40 --no-specials --windowed --delay-ms 30

# Explicit barcode list (no sampling)
python tests\stress_full_app.py 101117 101118 101119 --iterations 30 --delay-ms 10
```

Exports from the stress harness are saved in `exports/` so results can be inspected after automated runs.

## Data Privacy

The repository intentionally ignores `data/database.db`, `data/employee.xlsx`, and generated exports. Keep those files local—they frequently contain sensitive roster information.
