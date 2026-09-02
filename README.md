# Track Attendance

A desktop kiosk application for tracking employee attendance using barcode/QR code scanners and manual employee lookup.

## 📋 What It Does

**Track Attendance** turns any PC with a barcode scanner into a check-in station:

1. **Employee scans their badge** → App reads the barcode
2. **Forgot badge?** → Type name or email to look up and record manually
3. **Instant feedback** → Shows employee name and confirms the scan
4. **Data saved locally** → All scans stored in SQLite database
5. **Auto-sync to cloud** → Uploads to central server when online
6. **Export to Excel** → One-click report generation

| Benefit | Description |
|---------|-------------|
| **Works offline** | Scans save locally and sync later |
| **Multi-station** | Multiple kiosks sync to one dashboard |
| **Privacy-first** | Employee names stay local; only badge IDs sync to cloud |
| **Zero training** | Plug in scanner, run app, start scanning |

## ✨ Features

- Barcode-first workflow with instant visual feedback (name, "THANK YOU" banner)
- **Employee lookup** — forgot-badge users type name or email to find their record and check in manually
- **Voice toggle** — mute/unmute scan confirmation audio from the header bar without restarting
- Voice confirmation on successful scans (ElevenLabs MP3s)
- Duplicate badge detection — configurable: `warn`, `block`, or `silent` (see [docs/SYNC.md](docs/SYNC.md))
- Dashboard with business unit breakdown and unmatched badge tracking
- Auto-sync to cloud when idle; manual sync button available
- One-click Excel export with unified columns (Scan Value, Legacy ID, Full Name, Email, Business Unit, Position, Station, Scanned At, Matched, Scan Source)
- Fully offline — runs without network; syncs when connection returns
- **Admin control center** (PIN-protected) — sectioned panel with Status, Data Management, and Settings; runtime-tunable sliders for duplicate detection (toggle + alert duration), voice, camera (confirm frames, strictness, reset to defaults), and connection check
- Welcome animation and configurable party/event background
- **Email field support** — optional `Email` column in roster xlsx (stays local, never synced)
- **Scan source tracking** — distinguishes badge scans, name lookups, and manual entries (`badge` / `lookup` / `manual`)
- **Business unit sync to cloud** — BU names synced for the mobile dashboard (organisational labels, not PII)
- **Public mobile attendance dashboard** — real-time with light/dark theme (follows device, toggle available); view live attendance from any device
- **Roster summary sync** — hash-based deduplication prevents redundant uploads
- **Station heartbeat & status** — stations report health via heartbeat; mobile dashboard shows online/offline status per station
- **Clear This Station / Clear All** — separate admin actions; Clear All resets all stations + roster via `clear_epoch` coordination
- **Voice file override** — drop custom MP3s in `voices/` next to exe to replace bundled voices without recompiling
- **CI/CD pipeline** — automated `pytest` runs on every push and PR (338 tests)
- **Camera proximity greeting** — YuNet DNN face detection with upper body Haar cascade fallback; detects approaching people even when face isn't visible (turned away, too tall/short); ElevenLabs voice greetings; presence-aware state machine with voice overlap prevention (disabled by default)
- **Debug panel** — live Python log streaming overlay in the kiosk UI with click-to-copy, Copy All, color-coded log levels, and 500ms polling; toggled from admin panel
- **Admin debug controls** — runtime log level (ERROR/WARN/INFO/DEBUG), console output toggle, debug panel toggle; all settings persist across restarts
- **Focus lock release** — when debug panel is active, focus lock disengages to allow free clicking, text selection, and clipboard copy

## 💻 Requirements

- Windows 10/11 or macOS (packaged build target; both supported)
- Python 3.11+ (PyQt6 + WebEngine)
- Keyboard-emulating barcode scanner (manual typing + Enter works for testing)
- **Camera plugin (optional)**: USB/built-in webcam, `opencv-python` (YuNet DNN model bundled)

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
├── voices/                # (Optional) Custom MP3s override bundled voices
├── greetings/             # (Optional) Custom greeting MP3s override bundled greetings
└── exports/               # Excel reports saved here
```

> **Note**: The app looks for `.env` next to the exe first (user-editable), then falls back to the bundled `.env` inside the exe.

## 🧪 Testing

```bash
# Full unit test suite (338 tests)
python -m pytest tests/ -v

# Stress test (end-to-end with UI)
python tests/stress_full_app.py --iterations 100 --delay-ms 30

# Sync tests
python tests/test_production_sync.py
python tests/test_batch_sync.py
python tests/test_connection_scenarios.py

# Camera proximity detector (unit tests, no hardware needed)
python tests/test_proximity_detector.py

# Multi-station cloud dashboard verification
python tests/simulate_multi_station.py

# Utilities
python tests/reset_failed_scans.py           # Reset failed scans to pending
python tests/debug_sync_performance.py       # Profile sync bottlenecks
python tests/create_test_scan.py             # Insert test scan record
```

## 🗂️ Project Structure

```
main.py              PyQt6 window, QWebEngineView, AutoSyncManager
attendance.py        Roster import, scan recording, duplicate detection, export
database.py          SQLite schema, queries, sync_status tracking
sync.py              Cloud sync client (batch upload, idempotency, retry, Live Sync)
dashboard.py         Local dashboard with Excel export, BU breakdown
config.py            All configuration with .env override
qt_bridge.py         Runs blocking calls off the Qt main thread without freezing the UI
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
- [Mobile Dashboard Plan](docs/MOBILE_DASHBOARD_PLAN.md) — Public real-time attendance dashboard design
- [Product Requirements](docs/PRD.md) — Feature requirements
- [Feature: Indicator Redesign](docs/FEATURE_INDICATOR_REDESIGN.md) — Connection indicator design
- [Claude Code Action](docs/CLAUDE_CODE_ACTION.md) — AI-powered code assistance setup
- [Configuration Reference](docs/CONFIGURATION.md) — All settings with defaults and descriptions
- [Commercialization Plan](docs/COMMERCIALIZE.md) — Licensing, pricing, Stripe integration, go-to-market strategy

## 📝 Version History

- **v2.1.6** — Fixed "Save Current Settings to .env" wiping all comments and dropping unlisted settings from a hand-tuned `.env`; now edits values in place instead of regenerating the whole file from a template
- **v2.1.5** — Fixed a race where clearing station/cloud data could be resurrected by an in-flight auto-sync upload landing after the delete; the sync coordinator barrier is now raised before the cloud delete call, not after
- **v2.1.4** — Added "Save Current Settings to .env" button in Admin Panel → Settings, writing this station's live settings (env + SQLite overrides) back to `.env` so a tuned station's config can be copied to other stations instead of re-entering values by hand; backs up any existing `.env` first, excludes `CLOUD_API_KEY` by design
- **v2.1.3** — Skipped the Live Sync cloud duplicate-check for unmatched manual name entries (was delaying "not matched" responses for no reason), fixed Dashboard export's "Not Yet Scanned" sheet incorrectly listing employees who had already scanned (badge_id vs legacy_id mismatch), fixed the last remaining main-thread-blocking network call during app shutdown
- **v2.1.2** — Fixed Dashboard showing registered count as 0 (a v2.1.1 regression — cross-thread SQLite crash), raised Live Sync's duplicate-check timeout from 2.0s to 4.0s after live testing showed a cold-path request exceed it (client fails open on timeout, letting a duplicate through), added timing/outcome logging to the duplicate check on both client and cloud API, Dashboard now shows the registered count instantly on open with cloud-sourced fields filling in asynchronously
- **v2.1.1** — Fixed app-wide freeze when opening Dashboard/Settings, and worse cross-station hangs with Live Sync enabled — several admin/dashboard calls and Live Sync's cross-station duplicate check were blocking the Qt main thread on network I/O; now run off-thread via `qt_bridge.call_without_freezing_ui()` without changing existing blocking semantics
- **v2.1.0** — Sync coordinator bugfixes (#65-#69: stranded barrier locks, cross-thread SQLite access, network-only batch `ok` field corrections, unrecognized-stage fallthrough), shutdown-sync now routed through the coordinator barrier, employee search ranking fixed (prefix/substring/word-match tiers no longer starved by cache iteration order), corrupt roster file degrades gracefully instead of crashing at startup, admin/settings panel keyboard navigation (Enter to confirm, Escape to step back a level, Tab/Shift+Tab focus trap, arrow-key navigation), confetti burst on successful scans (admin-toggleable, off by default)
- **v2.0.0** — Admin debug controls (log level, console output, debug panel toggles), live Python log streaming overlay with click-to-copy and color-coded levels, focus lock release when debug panel active, clipboard fallback for QWebEngineView `file://` context, commercialization plan
- **v1.9.0** — YuNet DNN face detection with upper body Haar cascade fallback (4-layer detection chain: YuNet → upper body → Haar face → motion), ElevenLabs voice greetings, voice overlap race condition fix, admin controls for confirm frames/strictness/duplicate detection toggle/alert duration with reset-to-defaults, camera icon repositioned below title bar, Excel export timezone conversion (UTC → local), PostgreSQL composite indexes and connection pool scaling (50 connections), BU aggregation query optimized with CTE, 338 tests
- **v1.8.0** — Admin control center redesign (sectioned panel with runtime settings sliders), voice file override (`voices/` next to exe), duplicate detection by `legacy_id`, detailed duplicate roster report, configurable Haar cascade sensitivity, scan source tracking refined (`badge`/`lookup`/`manual`), dashboard refresh interval setting, station heartbeat & live status, clear this station / clear all with `clear_epoch` coordination, slider UI (green/grey fill bar), settings persistence across restarts, 307 tests
- **v1.7.0** — Voice toggle (mute/unmute from header), employee email/name lookup for forgot-badge users, scan source tracking (`badge` / `manual_lookup`), unified export columns, `scan_source` column in cloud DB, requirements.txt cleanup (268 tests)
- **v1.6.0** — Email field, BU sync to cloud, public mobile dashboard, roster summary sync, CI/CD test pipeline, stress test with local vs cloud dashboard verification
- **v1.5.1** — Animated camera icon: dot turns amber on detection, reverts to green when person leaves, with pulse animation on state transitions
- **v1.5.0** — Camera proximity greeting plugin (experimental, opt-in), bilingual audio greetings, presence-aware state machine with hysteresis, VoicePlayer.is_playing(), 13 unit tests, voice volume control
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
| `LIVE_SYNC_ENABLED` | `False` | Real-time cross-station duplicate check + immediate upload per scan — see [SYNC.md](docs/SYNC.md#live-sync-real-time-cross-station-duplicate-check). Adds 2 API calls per scan; counts against the cloud API's per-IP rate limit — raise `RATE_LIMIT_MAX` on the cloud API before a high-traffic multi-station event |
| `LIVE_SYNC_TIMEOUT_SECONDS` | `4.0` | Timeout for the Live Sync duplicate-check call (`0.5`–`10.0`) |
| `LIVE_SYNC_DUP_WINDOW_MINUTES` | `5` | How far back to check for a cross-station duplicate (`1`–`1440`) |
| `DUPLICATE_BADGE_ACTION` | `warn` | `warn` / `block` / `silent` |
| `SHOW_FULL_SCREEN` | `True` | Fullscreen kiosk mode |
| `SHOW_PARTY_BACKGROUND` | `True` | Festive background image |
| `VOICE_ENABLED` | `True` | Voice confirmation on scan |
| `VOICE_VOLUME` | `1.0` | Playback volume (`0.0`–`1.0`) |
| `ADMIN_PIN` | *(empty)* | 4-6 digit PIN to enable admin panel (leave empty to disable) |
| `DEBUG` | `False` | Enable debug mode (disables focus lock) |
| `ENABLE_CAMERA_DETECTION` | `False` | Enable camera proximity greeting plugin |
| `CAMERA_DEVICE_ID` | `0` | Camera index (`0` = default webcam) |
| `CAMERA_SHOW_OVERLAY` | `True` | Show floating camera preview (set `False` for production) |
| `CAMERA_GREETING_COOLDOWN_SECONDS` | `60` | Minimum seconds between greetings — prevents re-greeting a standing person when detection flickers |
| `CAMERA_SCAN_BUSY_SECONDS` | `30` | Seconds to suppress greetings after a badge scan |
| `CAMERA_MIN_SIZE_PCT` | `0.20` | Minimum detection size as fraction of frame width — filters out distant people |
| `CAMERA_ABSENCE_THRESHOLD_SECONDS` | `5` | Seconds with no person before kiosk resets to "empty" (ready to greet next person) |
| `CAMERA_CONFIRM_FRAMES` | `3` | Consecutive detected frames required before greeting (prevents false positives) |
| `CAMERA_HAAR_MIN_NEIGHBORS` | `5` | Haar cascade strictness — higher = fewer false positives but may miss detections |
| `SCAN_FEEDBACK_DURATION_MS` | `5000` | Duration to show employee name after scan |
| `DUPLICATE_BADGE_ALERT_DURATION_MS` | `3000` | Duplicate alert display duration |

See `.env.example` for the full list.

## 🔧 Troubleshooting

**"Cannot connect to API" after building exe**: SSL certificates not bundled. Ensure `--hidden-import "certifi"` is in your build command. The app auto-sets `SSL_CERT_FILE` for frozen builds.

**Connection indicator shows red**: Check that `.env` exists next to the exe and `CLOUD_API_KEY` is set. Test with `python tests/test_connection_scenarios.py`.

**Badge not matching despite being in Excel**: Stale database. Delete `data/database.db` and restart — the app reimports `employee.xlsx` on startup with hash-based change detection.

**Scans stuck as "failed"**: Run `python scripts/reset_failed_scans.py` to reset them back to `pending` for retry.

**Camera greeting fires too often**: The detector uses presence-aware state tracking with hysteresis — it requires `CAMERA_CONFIRM_FRAMES` (default 3) consecutive detected frames before greeting, preventing false positives from shadows or flickers. It only greets once when someone arrives at an empty kiosk, then stays quiet while they remain. The person must leave (no face/body for `CAMERA_ABSENCE_THRESHOLD_SECONDS`, default 3s) before the next person gets greeted. Even after leaving, if the same person returns within `CAMERA_GREETING_COOLDOWN_SECONDS` (default 10s) the greeting is suppressed. Additionally, greetings are suppressed during active scanning (`CAMERA_SCAN_BUSY_SECONDS`, default 30s) and never overlap with the scan "thank you" voice. For busy events, increase `CAMERA_SCAN_BUSY_SECONDS` or disable with `ENABLE_CAMERA_DETECTION=False`.

## 🔒 Data Privacy

Employee names and rosters stay local. Never commit `data/`, `exports/`, or `.env` files.

- **Employee names, email, position** — stored in the local database only; never synced to the cloud
- **Business unit names** — synced to cloud for the mobile dashboard; these are organisational labels, not personally identifiable information
- **Cloud receives only**: badge ID, station name, scan timestamp, business unit label, scan source
