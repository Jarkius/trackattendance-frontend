# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

TrackAttendance Frontend — offline-first desktop kiosk app for badge/QR attendance scanning with cloud sync.

**Stack**: Python 3.11+, PyQt6 + QWebEngineView, SQLite, Materialize CSS
**Target**: Windows desktop (.exe via PyInstaller)
**Repo**: `Jarkius/trackattendance-frontend`

## Commands

```bash
# Setup
python -m venv .venv
source .venv/bin/activate          # .venv\Scripts\activate on Windows
pip install -r requirements.txt

# Run
python main.py

# Build Windows .exe
pyinstaller TrackAttendance.spec

# Tests (standalone scripts, no test framework)
python tests/stress_full_app.py --iterations 100 --delay-ms 30
python tests/test_production_sync.py
python tests/test_batch_sync.py
python tests/test_connection_scenarios.py
python tests/test_sync_debug.py
python tests/simulate_scans.py

# Utility scripts
python scripts/reset_failed_scans.py
python scripts/migrate_sync_schema.py
python scripts/debug_sync_performance.py
python scripts/check_timestamp_format.py
python scripts/create_test_scan.py
```

## Architecture

```
main.py              PyQt6 window, QWebEngineView, AutoSyncManager
attendance.py        Roster import (Excel), scan recording, duplicate detection, export
database.py          SQLite schema, queries, sync_status tracking
sync.py              Batch upload to cloud API, idempotency (SHA256), retry
dashboard.py         Statistics aggregation
config.py            All configuration with .env override
logging_config.py    Logging setup

web/
├── index.html       Single-page kiosk UI
├── script.js        Frontend logic (barcode input, overlays, dashboard counters)
├── css/style.css    Custom styling
└── materialize/     CSS framework
```

**Data flow**: Badge scanned (keyboard emulation) → JS listener → QWebChannel → Python → SQLite (pending) → batch sync → cloud API → PostgreSQL

**Offline-first**: All scans save locally first. Sync happens in background when idle. No data lost if offline.

**Privacy**: Employee names stay in local SQLite only. Only badge IDs sync to cloud.

## Key Patterns

**Sync states**: Each scan has `sync_status`: `pending` → `synced` or `failed`

**Auto-sync**: Triggers when idle (no scans for N seconds) + pending scans exist + API reachable

**Shutdown sequence**: Test connectivity → sync all pending → export to Excel → close

**Duplicate detection**: Configurable via `.env` — `warn` (yellow overlay), `block` (red, rejected), `silent` (log only)

**Python ↔ JS bridge**: QWebChannel exposes Python methods to `web/script.js`

**Config loading priority**: `.env` next to executable (frozen) → `.env` in script dir (dev) → system env vars

## Env Variables

Required: `CLOUD_API_URL`, `CLOUD_API_KEY`

Optional (with defaults in `config.py`): `AUTO_SYNC_IDLE_SECONDS`, `AUTO_SYNC_CHECK_INTERVAL_SECONDS`, `CLOUD_SYNC_BATCH_SIZE`, `DUPLICATE_BADGE_DETECTION_ENABLED`, `DUPLICATE_BADGE_TIME_WINDOW_SECONDS`, `DUPLICATE_BADGE_ACTION`, `SHOW_FULL_SCREEN`, `ENABLE_FADE_ANIMATION`, `SHOW_PARTY_BACKGROUND`, `LOG_LEVEL`

## Style

- PEP 8: 4-space indent, snake_case functions, PascalCase classes
- JS: camelCase identifiers matching HTML element IDs
- CSS: kebab-case class names, scoped by component in `web/css/`
- Docstrings on public functions exposed via QWebChannel

## Data Directories (gitignored)

- `data/` — `database.db`, `employee.xlsx` (sensitive, never commit)
- `exports/` — generated Excel reports
- `logs/` — application logs
- `.venv/` — virtual environment

## Cloud API

Syncs to `trackattendance-api` (separate repo: `Jarkius/trackattendance-api`)

- `POST /v1/scans/batch` — batch upload with Bearer auth and idempotency keys
- `GET /v1/dashboard/stats` — aggregated statistics
- `GET /v1/dashboard/export` — paginated scan export

## Lessons Learned

- Break complex work into 1-hour phases; minimum viable first, then expand
- Parallel agents speed up analysis of different system aspects
- Phase markers ("Phase 1:", "Phase 2:") in issues help track incremental progress
- Time zone: GMT+7 (Bangkok)
