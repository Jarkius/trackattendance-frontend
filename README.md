﻿# Track Attendance

<!-- Add a screenshot of the application UI here -->
<!-- ![Track Attendance UI](path/to/screenshot.png) -->

## Project Overview

🚀 **Production-Ready** Track Attendance is a standalone desktop application for scanning QR or 1D barcodes, logging attendance instantly, and displaying results on a modern, real-time dashboard. Built with Python and a PyQt6-hosted web UI, it provides a seamless "kiosk-style" experience for operators.

✅ **Cloud Sync Enabled**: The system now supports both offline-first operation and seamless cloud synchronization to a production Google Cloud Run API.

The system maintains data privacy while offering enterprise-grade cloud backup and multi-device synchronization capabilities.

## System Requirements

- **Operating System:** Primarily designed and packaged for **Windows 10/11**.
- **Python:** Python 3.8+
- **Hardware:** A keyboard-emulating barcode scanner (QR or 1D) is recommended for the intended workflow.

## Feature Highlights

- **🔍 Barcode-first workflow:** Accepts keyboard wedge scanners or manual entry and normalises every submission before it hits the database.
- **📊 Instant feedback:** Live banner, dashboard counters, and recent-history list update with each scan so problems are spotted in seconds.
- **🎨 Modern UI Design:** Compact, intuitive interface with optimized spacing for maximum scan history visibility.
- **🔄 Intuitive Sync Button:** Universal sync icon (🔄) with bright blue (#00A3E0) color and spinning animation during sync operations.
- **📊 Compact Dashboard:** Integrated sync status with inline statistics display in dashboard section.
- **🔍 Auto-captured unknowns:** Mistyped or unrecognised IDs are stored with a "Not matched" flag for later reconciliation.
- **📈 One-click & Auto Exports:** Manually export the attendance log to an XLSX file at any time. The application also performs a final export automatically on shutdown.
- **🔄 Cloud Synchronization:** ✅ **PRODUCTION READY** - Seamlessly sync attendance data to production cloud API with manual sync controls.
- **📊 Real-time Sync Statistics:** Dashboard shows pending/synced/failed scan counts with 20px spacing for optimal readability.
- **🔒 Privacy-Preserving:** Only scan data (badge ID, timestamp, location) is synced to cloud; employee names remain local.
- **⚡ Batch Processing:** Efficiently sync multiple records in batches with idempotency protection.
- **🛡️ Error Recovery:** Handles network failures gracefully with retry mechanisms and error logging.
- **🔧 Graceful shutdown:** Closing the window can trigger an export overlay, while stress tools can bypass the UI and export directly.
- **🌐 Offline First:** All assets and logic are bundled. The application runs entirely offline without network access required.
- **📱 Responsive Design:** Optimized layout across different screen sizes with adaptive spacing and controls.

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
     source .venv/bin/activate  # For development; packaging is Windows-focused
     ```

4. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```
   The PyQt6 + WebEngine stack is required; other libraries support reporting (openpyxl) and testing utilities.

5. **Prepare operational data**
   - Place the employee roster at `data/employee.xlsx` (columns: Legacy ID, Full Name, SL L1 Desc, Position Desc).
   - Place any existing `database.db` into `data/` or let the app bootstrap a fresh file on first run.
   - For packaged builds, keep the `data/` folder alongside `TrackAttendance.exe` so edits persist between runs.

## Running the App

```bash
python main.py
```

A placeholder "Awaiting first scan" row appears in the history list until the first badge is recorded.

## 🌐 Cloud Synchronization

### Production Cloud API Status
- **✅ Live URL**: https://trackattendance-api-969370105809.asia-southeast1.run.app
- **🗄️ Database**: Neon PostgreSQL (production)
- **📊 Synced Records**: 120+ scans successfully synced
- **🔄 Sync Status**: Fully operational and tested across multiple networks
- **⚡ Performance**: Optimized sync with ~1-2 second response times

### Cloud Sync Features
- **🎯 Intuitive Sync Button**: Circular sync icon (🔄) with bright blue (#00A3E0) color for instant recognition
- **⚙️ Visual Feedback**: Button spins during sync operation showing real-time progress
- **📊 Compact Layout**: Sync button positioned inline with statistics for better UX
- **📈 Real-time Status**: Dashboard shows pending/synced/failed scan counts with optimized 20px spacing
- **⚡ Batch Processing**: Efficiently uploads multiple records in batches
- **🔒 Privacy Preserved**: Only badge data synced; employee names stay local
- **🛡️ Error Handling**: Network failures handled gracefully with retry logic
- **🔄 Idempotency**: Duplicate scans automatically detected and prevented

### Cloud Sync Testing
The repository includes comprehensive test scripts for cloud sync functionality:

```bash
# Create test scan data
python create_test_scan.py

# Test full production sync
python test_production_sync.py

# Debug sync process
python test_sync_debug.py

# Test batch sync processing
python test_batch_sync.py

# Test network connection scenarios
python test_connection_scenarios.py

# Analyze sync performance
python debug_sync_performance.py
```

### Sync Workflow
1. **Local Storage**: Scans are stored immediately in local SQLite database
2. **Pending Status**: New scans marked as "pending" for cloud sync
3. **Manual Sync**: User clicks "Sync Now" to upload to cloud API
4. **Batch Upload**: Multiple pending scans uploaded in efficient batches
5. **Status Update**: Local records updated to "synced" or "failed" status
6. **Privacy Maintained**: Only scan data (badge, time, location) sent to cloud

## 🎨 UI/UX Design (v1.1.0)

### Dashboard Redesign
The application features a modern, space-optimized dashboard design focused on maximizing scan history visibility while maintaining clean aesthetics.

#### Sync Status Integration
- **Compact Layout**: Sync controls integrated directly into dashboard section
- **Inline Statistics**: Pending/Synced/Failed counts displayed horizontally with 20px spacing
- **Smart Button Placement**: 30px circular sync button positioned inline with statistics
- **Visual Hierarchy**: Clear separation between sections with optimized padding

#### Sync Button Design
- **Icon**: Universal sync symbol (🔄 circular arrows) for instant recognition
- **Color**: Bright blue (#00A3E0) for excellent visibility and modern appearance
- **Size**: 30px circular button - compact yet easily clickable
- **Animation**: Smooth spinning animation during sync operations
- **States**:
  - Normal: Bright blue (#00A3E0)
  - Hover: Darker blue (#0082B3) with lift effect
  - Syncing: Spinning animation with visual feedback
  - Disabled: Grey with no-drop cursor

#### Space Optimization
The UI has been meticulously optimized to maximize scan history visibility:

- **Dashboard Title**: Reduced padding (15px → 8px) and margin (20px → 12px)
- **Sync Section**: Optimized spacing with minimal waste (~23px saved)
- **Export Button**: Compact height with 8px padding and 0.9rem font
- **Sidebar Padding**: Reduced to 10px (top/bottom) for maximum content space
- **History Section**: Minimal 3px margin-top for tight visual connection
- **Result**: 70-80px additional vertical space = **3-5 more scan entries visible!**

#### Visual Design Principles
- ✅ **Clarity**: Clean, uncluttered interface with clear visual hierarchy
- ✅ **Efficiency**: Maximum information density without feeling cramped
- ✅ **Feedback**: Immediate visual feedback for all user actions
- ✅ **Recognition**: Universal icons and familiar interaction patterns
- ✅ **Responsiveness**: Adaptive layout for different screen sizes

#### Color Palette
- **Primary Green**: #86bc25 (Deloitte brand, export button)
- **Sync Blue**: #00A3E0 (bright, intuitive for cloud sync)
- **Text Dark**: #333333 (high contrast for readability)
- **Text Medium**: #8c8c8c (secondary information)
- **Border**: #e5e5e5 (subtle separation)
- **Background**: #ffffff (clean, professional)

#### Typography & Spacing
- **Card Titles**: 1.25rem, 700 weight, 8px padding-bottom
- **Sync Stats**: 0.75rem labels, 0.9rem values, 20px gaps
- **Export Button**: 0.9rem, uppercase, 0.5px letter-spacing
- **Scan History**: 0.8rem items with 6px vertical padding

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

## 📋 Version History

### v1.1.0 - Sync Status UI Redesign (Latest)
**Release Date**: 2025-11-10

Major UI improvements focused on sync status interface redesign with space optimization.

**New Features:**
- 🔄 Universal sync icon (circular arrows) replacing cloud_upload
- 💙 Bright blue color (#00A3E0) for better visibility
- ⚡ Spinning animation during sync operations
- 📊 Compact dashboard layout with inline sync statistics
- 📏 Optimized spacing throughout interface
- 📈 3-5 more scan entries visible without scrolling

**Technical Changes:**
- 11 commits in PR #3
- 3 files modified (HTML, CSS, JavaScript)
- ~70-80px vertical space optimization
- Improved responsive design

**Files Modified:**
- `web/index.html` - Restructured sync status layout
- `web/css/style.css` - Comprehensive CSS updates
- `web/script.js` - Enhanced sync button behavior

See [Release v1.1.0](../../releases/tag/v1.1.0) for full details.

### v1.0.0 - Production Cloud Sync
**Initial Release**

- ✅ Production-ready cloud synchronization
- ✅ Google Cloud Run API integration
- ✅ Neon PostgreSQL database
- ✅ 120+ scans successfully tested
- ✅ Privacy-preserving sync (badge data only)
- ✅ Offline-first architecture
- ✅ Batch processing with idempotency
- ✅ Comprehensive test suite

## Data Privacy

The repository intentionally ignores `data/database.db`, `data/employee.xlsx`, and generated exports. Keep those files local—they frequently contain sensitive roster information.
