# Repository Guidelines

## Project Overview

TrackAttendance Frontend — offline-first desktop kiosk app for badge/QR attendance scanning with cloud sync.

**Stack**: Python 3.11+, PyQt6 + QWebEngineView, SQLite, Materialize CSS
**Target**: Windows desktop (.exe via PyInstaller)

## Project Structure

```
main.py              PyQt6 window, QWebEngineView, AutoSyncManager
attendance.py        Roster import (Excel), scan recording, duplicate detection, export
database.py          SQLite schema, queries, sync_status tracking
sync.py              Batch upload to cloud API, idempotency (SHA256), retry
dashboard.py         Statistics aggregation
config.py            All configuration with .env override
audio.py             Voice playback on successful scans (QMediaPlayer)
logging_config.py    Logging setup

web/                 Embedded kiosk UI (HTML/CSS/JS, Materialize, Inter font)
scripts/             Utility scripts (migration, debug, reset failed scans)
tests/               Test and simulation scripts (stress test, sync tests)
docs/                Technical docs (API, Architecture, Sync, PRD)
data/                Runtime data — database.db, employee.xlsx (gitignored)
exports/             Generated Excel reports (gitignored)
assets/              Icons, voice MP3s, PyInstaller resources
```

## Build, Test, and Development Commands

- `python -m venv .venv` — create virtual environment
- `.venv\Scripts\activate` — activate on Windows (`source .venv/bin/activate` on macOS/Linux)
- `pip install -r requirements.txt` — install dependencies
- `python main.py` — launch the kiosk app
- `pyinstaller TrackAttendance.spec` — build Windows .exe
- `python tests/stress_full_app.py --iterations 100 --delay-ms 30` — end-to-end stress test
- `python tests/test_production_sync.py` — test cloud sync
- `python scripts/reset_failed_scans.py` — reset failed scans to pending

## Coding Style

- **Python**: PEP 8, 4-space indent, snake_case functions, PascalCase classes
- **JavaScript**: camelCase identifiers matching HTML element IDs in `web/script.js`
- **CSS**: kebab-case class names, scoped by component in `web/css/`
- Docstrings on public functions exposed via QWebChannel

## Key Patterns

- **Offline-first**: All scans save to SQLite first. Sync is background/optional.
- **Config loading**: `.env` next to exe (frozen) → `.env` in script dir (dev) → system env vars
- **Sync states**: Each scan has `sync_status`: `pending` → `synced` or `failed`
- **Auto-sync**: Triggers when idle (no scans for N seconds) + pending scans + API reachable
- **Shutdown**: Test connectivity → sync all pending → export to Excel → close
- **Python-JS bridge**: QWebChannel exposes Python methods to `web/script.js`

## Commit & PR Guidelines

- Short imperative commit summaries (e.g., `feat: add voice playback on scan`)
- Reference GitHub issue IDs where applicable
- PRs should explain the change, outline validation steps
- Note any config/env changes explicitly

## Security & Configuration

- All secrets loaded from `.env` via `config.py` — never hardcode API keys
- `data/` contents are sensitive — never commit databases, rosters, or exports
- Required env vars: `CLOUD_API_URL`, `CLOUD_API_KEY`
- See `.env.example` for all available settings
