# Staff Attendance

## Project Overview

This application is designed to facilitate efficient staff attendance tracking using QR code scanning. It provides a user-friendly interface for scanning badges, displaying real-time feedback, and maintaining a historical log of scans. The application also features a dashboard to summarize attendance data.

## Features

*   **QR Code Scanning:** Quickly scan staff badges to record attendance.
*   **Real-time Feedback:** Instant visual feedback on successful scans or errors.
*   **Attendance Dashboard:** Displays key metrics such as total employees and scanned count.
*   **Scan History:** A chronological list of recent attendance records.
*   **Modern UI/UX:** Clean and intuitive interface built with Materialize CSS and custom styling.
*   **Exports Directory:** Barcode history exports are written to `exports/` with filenames like `Checkins_Station1_20250922_171536.xlsx`, matching the employee workbook column order, auto-sized for readability, and now include `Submitted Value` and `Matched` columns so manual entries remain traceable.

## Setup Instructions

To set up and run this project, follow these steps:

1.  **Clone the repository:**
    ```bash
    git clone <repository_url>
    cd QR
    ```

2.  **Create a Python Virtual Environment (recommended):**
    ```bash
    python -m venv .venv
    ```

3.  **Activate the Virtual Environment:**
    *   **Windows:**
        ```bash
        .venv\Scripts\activate
        ```
    *   **macOS/Linux:**
        ```bash
        source .venv/bin/activate
        ```

4.  **Install Dependencies:**
    ```bash
    pip install PyQt6 PyQt6-WebEngine
    ```
    *(Note: Other dependencies like `bottle`, `eel`, etc., might be present in the environment but `PyQt6` and `PyQt6-WebEngine` are crucial for the application's core functionality.)*

5.  **Prepare the data directory:**
    - Place your employee roster at `data/employee.xlsx`.
    - If you have an existing `database.db`, move it to `data/database.db` (the app will create one if missing).

## How to Run

After setting up the environment and installing dependencies, you can run the application:

```bash
python main.py
```

## UI/UX Notes

## Testing & Diagnostics

- `python tests\simulate_scans.py` spins up an off-screen `QWebEngineView` and submits a small set of barcodes against `web/index.html` to confirm the front-end wiring still works without the PyQt bridge. Expect the console message `Qt WebChannel transport not available; desktop integration disabled.` and `[ok]` log lines such as `feedback='Desktop bridge unavailable' total_scanned=0`; this means the DOM handlers ran successfully even though counters stay at zero.
- `python tests\stress_full_app.py` drives the full PyQt window using employee barcodes sampled from `data/employee.xlsx` plus optional synthetic edge cases. Useful flags:
  - `--sample-size N` limits how many employees are sampled (defaults to 50).
  - `--no-specials` skips the synthetic invalid barcodes.
  - `--iterations N` and `--delay-ms N` control run length and pacing.
  - `--windowed`, `--no-show-window`, and `--disable-fade` tweak window presentation.
  - Provide explicit barcodes as positional arguments to bypass sampling entirely.

Example runs:
```bash
# Fast, headless smoke test
python tests\stress_full_app.py --iterations 50 --delay-ms 0 --no-show-window --disable-fade

# Window visible with sampled employees only
python tests\stress_full_app.py --iterations 100 --sample-size 40 --no-specials --windowed --delay-ms 30

# Explicit barcode list (no sampling)
python tests\stress_full_app.py 101117 101118 101119 --iterations 30 --delay-ms 10
```

These utilities are optional; they do not change application behaviour when you launch the app with `python main.py`.
