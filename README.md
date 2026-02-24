# Track Attendance

A desktop kiosk application for tracking employee attendance using barcode/QR code scanners.

## 📋 What It Does

**Track Attendance** turns any Windows PC with a barcode scanner into a check-in station:

1. **Employee scans their badge** → App reads the barcode
2. **Instant feedback** → Shows employee name and confirms the scan
3. **Data saved locally** → All scans stored in SQLite database
4. **Auto-sync to cloud** → Uploads to central server when online
5. **Export to Excel** → One-click report generation

| Benefit | Description |
|---------|-------------|
| **Works offline** | Scans save locally and sync later |
| **Multi-station** | Multiple kiosks sync to one dashboard |
| **Privacy-first** | Employee names stay local; only badge IDs sync to cloud |
| **Zero training** | Plug in scanner, run app, start scanning |

## ✨ Features

- Barcode-first workflow with instant visual feedback (name, "THANK YOU" banner)
- Voice confirmation on successful scans (ElevenLabs MP3s)
- Duplicate badge detection — configurable: `warn`, `block`, or `silent` (see [docs/SYNC.md](docs/SYNC.md))
- Dashboard with business unit breakdown and unmatched badge tracking
- Auto-sync to cloud when idle; manual sync button available
- One-click Excel export; automatic export on shutdown
- Fully offline — runs without network; syncs when connection returns
- Admin panel (PIN-protected) to clear cloud + local database before events
- Welcome animation and configurable party/event background
- **[Experimental]** Camera proximity greeting — detects approaching people and plays a bilingual welcome audio (disabled by default)

## 💻 Requirements

- Windows 10/11 (packaged build target)
- Python 3.11+ (PyQt6 + WebEngine)
- Keyboard-emulating barcode scanner (manual typing + Enter works for testing)
- **Camera plugin (optional)**: USB/built-in webcam, `opencv-python`, `mediapipe`, `edge-tts`

## 🚀 Setup

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows PowerShell/cmd
source .venv/bin/activate       # macOS/Linux

# Option A: uv (fast)
uv pip install -r requirements.txt

# Option B: pip (standard)
pip install -r requirements.txt
```

Place employee roster at `data/employee.xlsx` with columns: `Legacy ID`, `Full Name`, `SL L1 Desc`, `Position Desc`.

Create `.env` file (see `.env.example`):
```ini
CLOUD_API_KEY=your-api-key-here
# Optional
CLOUD_API_URL=https://your-api-endpoint
SHOW_FULL_SCREEN=True
SHOW_PARTY_BACKGROUND=False
```

## ▶️ Running

```bash
python main.py
```

- Prompts for station name on first launch
- Opens frameless fullscreen by default
- Press `Escape` to close (syncs pending scans, exports to Excel, then exits)

## 📦 Building

```bash
# Production build (spec file)
pyinstaller --noconfirm TrackAttendance.spec

# Quick dev build
pyinstaller --noconfirm --onedir --name "TrackAttendance" --icon "assets/greendot.ico" --add-data ".env;." --add-data "web;web" --hidden-import "certifi" main.py
```

### 🚢 Deployment

1. Copy `dist/TrackAttendance/TrackAttendance.exe` to target machine
2. Create `data/` folder, place `employee.xlsx` inside
3. Create `.env` next to exe with your API key
4. Ensure Windows Firewall allows the application
5. Run the application

**Folder structure on target machine**:
```
TrackAttendance/
├── TrackAttendance.exe    # Main application
├── .env                   # Your configuration (create this)
├── data/
│   ├── employee.xlsx      # Employee roster (required)
│   └── database.db        # Created automatically on first run
└── exports/               # Excel reports saved here
```

> **Note**: The app looks for `.env` next to the exe first (user-editable), then falls back to the bundled `.env` inside the exe.

## 🧪 Testing

```bash
# Stress test (end-to-end with UI)
python tests/stress_full_app.py --iterations 100 --delay-ms 30

# Sync tests
python tests/test_production_sync.py
python tests/test_batch_sync.py
python tests/test_connection_scenarios.py

# Utilities
python scripts/reset_failed_scans.py        # Reset failed scans to pending
python scripts/debug_sync_performance.py     # Profile sync bottlenecks
python scripts/create_test_scan.py           # Insert test scan record
```

## 🗂️ Project Structure

```
main.py              PyQt6 window, QWebEngineView, AutoSyncManager
attendance.py        Roster import, scan recording, duplicate detection, export
database.py          SQLite schema, queries, sync_status tracking
sync.py              Cloud sync client (batch upload, idempotency, retry)
config.py            All configuration with .env override
web/                 Embedded kiosk UI (HTML/CSS/JS)
plugins/camera/      Proximity detection plugin (opt-in, disabled by default)
scripts/             Utility scripts (migration, debug, reset)
tests/               Test and simulation scripts
docs/                Technical documentation
ψ/                   Oracle memory (retrospectives, learnings)
```

## 📖 Documentation

- [Architecture](docs/ARCHITECTURE.md) — Component design, data flow, error handling
- [Cloud API](docs/API.md) — Endpoint specs, auth, request/response formats
- [Sync & Duplicate Detection](docs/SYNC.md) — Offline sync, auto-sync, batch processing, duplicate modes
- [Product Requirements](docs/PRD.md) — Feature requirements
- [Feature: Indicator Redesign](docs/FEATURE_INDICATOR_REDESIGN.md) — Connection indicator design
- [Claude Code Action](docs/CLAUDE_CODE_ACTION.md) — AI-powered code assistance setup

## 📝 Version History

- **v1.5.0** — Camera proximity greeting plugin (experimental, opt-in), bilingual audio greetings, voice volume control
- **v1.4.0** — Welcome animation, party background, duplicate silent fix
- **v1.3.0** — Dashboard BU breakdown, duplicate badge detection
- **v1.2.0** — Auto-sync with idle detection
- **v1.1.0** — Sync status UI redesign
- **v1.0.0** — Initial production cloud sync

## ⚙️ Configuration Reference

All settings are in `config.py` with `.env` override. Key settings:

| Variable | Default | Description |
|----------|---------|-------------|
| `CLOUD_API_URL` | Cloud Run URL | API endpoint for sync |
| `CLOUD_API_KEY` | *(required)* | Bearer token for API auth |
| `CLOUD_SYNC_BATCH_SIZE` | 100 | Scans per sync batch |
| `AUTO_SYNC_IDLE_SECONDS` | 30 | Idle time before auto-sync triggers |
| `DUPLICATE_BADGE_ACTION` | `warn` | `warn` / `block` / `silent` |
| `SHOW_FULL_SCREEN` | `True` | Fullscreen kiosk mode |
| `SHOW_PARTY_BACKGROUND` | `True` | Festive background image |
| `VOICE_ENABLED` | `True` | Voice confirmation on scan |
| `VOICE_VOLUME` | `1.0` | Playback volume (`0.0`–`1.0`) |
| `ADMIN_PIN` | *(empty)* | 4-6 digit PIN to enable admin panel (leave empty to disable) |
| `ENABLE_CAMERA_DETECTION` | `False` | Enable camera proximity greeting plugin |
| `CAMERA_DEVICE_ID` | `0` | Camera index (`0` = default webcam) |
| `CAMERA_GREETING_COOLDOWN_SECONDS` | `10` | Seconds between proximity greetings |
| `CAMERA_SCAN_BUSY_SECONDS` | `30` | Seconds to suppress greetings after a badge scan |

See `.env.example` for the full list.

## 🔧 Troubleshooting

**"Cannot connect to API" after building exe**: SSL certificates not bundled. Ensure `--hidden-import "certifi"` is in your build command. The app auto-sets `SSL_CERT_FILE` for frozen builds.

**Connection indicator shows red**: Check that `.env` exists next to the exe and `CLOUD_API_KEY` is set. Test with `python tests/test_connection_scenarios.py`.

**Badge not matching despite being in Excel**: Stale database. Delete `data/database.db` and restart — the app reimports `employee.xlsx` on startup with hash-based change detection.

**Scans stuck as "failed"**: Run `python scripts/reset_failed_scans.py` to reset them back to `pending` for retry.

**Camera greeting fires too often in queues**: Greetings are automatically suppressed while badge scans are happening (controlled by `CAMERA_SCAN_BUSY_SECONDS`, default 30s). The greeting only plays when the kiosk has been idle — no scans for 30 seconds and the scan "thank you" voice has finished. Increase `CAMERA_SCAN_BUSY_SECONDS` for busier events, or disable with `ENABLE_CAMERA_DETECTION=False`.

## 🔒 Data Privacy

Employee names and rosters stay local. Never commit `data/`, `exports/`, or `.env` files.
