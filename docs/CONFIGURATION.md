# Configuration Reference

All settings are managed through environment variables, loaded from a `.env` file or system environment. See `.env.example` for a quick-start template.

**Loading priority**: `.env` next to executable (frozen builds) > `.env` in script directory (dev) > system environment variables.

## Cloud API (Required)

| Variable | Default | Description |
|----------|---------|-------------|
| `CLOUD_API_URL` | Cloud Run endpoint | API endpoint for sync |
| `CLOUD_API_KEY` | *(required)* | Bearer token for API auth. App exits on startup if missing. |
| `CLOUD_SYNC_BATCH_SIZE` | `100` | Scans per sync batch (1-1000) |

## Connection Health Check

| Variable | Default | Description |
|----------|---------|-------------|
| `CONNECTION_CHECK_INTERVAL_SECONDS` | `10` | Polling interval for connection status (seconds). Set to 0 to disable. |
| `CONNECTION_CHECK_TIMEOUT_SECONDS` | `1.5` | Timeout for health check requests (0.5-30) |
| `CONNECTION_CHECK_INITIAL_DELAY_SECONDS` | `15` | Delay before first check on startup |

## Auto-Sync

| Variable | Default | Description |
|----------|---------|-------------|
| `AUTO_SYNC_ENABLED` | `True` | Enable automatic background sync |
| `AUTO_SYNC_IDLE_SECONDS` | `30` | Seconds of inactivity before auto-sync triggers (5-3600) |
| `AUTO_SYNC_CHECK_INTERVAL_SECONDS` | `60` | How often to check if sync should run (10-3600) |
| `AUTO_SYNC_MIN_PENDING_SCANS` | `1` | Minimum pending scans to trigger sync (1-10000) |
| `AUTO_SYNC_SHOW_START_MESSAGE` | `True` | Show UI message when sync starts |
| `AUTO_SYNC_SHOW_COMPLETE_MESSAGE` | `True` | Show UI message when sync completes |
| `AUTO_SYNC_MESSAGE_DURATION_MS` | `3000` | Duration of sync status messages (0-30000 ms) |
| `AUTO_SYNC_CONNECTION_TIMEOUT` | `5` | Network timeout for connectivity checks (1-30 seconds) |

## Sync Resilience

| Variable | Default | Description |
|----------|---------|-------------|
| `SYNC_RETRY_ENABLED` | `True` | Retry failed syncs with exponential backoff |
| `SYNC_RETRY_MAX_ATTEMPTS` | `3` | Max retry attempts per batch (1-10) |
| `SYNC_RETRY_BACKOFF_SECONDS` | `5` | Initial backoff delay, doubles each attempt (1-60) |
| `AUTO_SYNC_MAX_CONSECUTIVE_FAILURES` | `5` | Failures before cooldown kicks in (1-100) |
| `AUTO_SYNC_FAILURE_COOLDOWN_SECONDS` | `300` | Cooldown period after consecutive failures (30-3600) |

## Roster Validation

| Variable | Default | Description |
|----------|---------|-------------|
| `ROSTER_VALIDATION_ENABLED` | `True` | Validate employee.xlsx on import |
| `ROSTER_STRICT_VALIDATION` | `True` | Skip import if required columns missing |

Required Excel columns: `Legacy ID`, `Full Name`, `SL L1 Desc`, `Position Desc`.

## Duplicate Badge Detection

| Variable | Default | Description |
|----------|---------|-------------|
| `DUPLICATE_BADGE_DETECTION_ENABLED` | `True` | Enable duplicate scan detection |
| `DUPLICATE_BADGE_TIME_WINDOW_SECONDS` | `60` | Time window to consider scans as duplicates (1-3600) |
| `DUPLICATE_BADGE_ACTION` | `warn` | `warn` (yellow alert, scan accepted), `block` (red alert, scan rejected), `silent` (no alert, scan accepted) |
| `DUPLICATE_BADGE_ALERT_DURATION_MS` | `3000` | Alert auto-dismiss duration (500-30000 ms) |
| `SCAN_FEEDBACK_DURATION_MS` | `2000` | "THANK YOU" display duration after scan (500-30000 ms) |

## UI

| Variable | Default | Description |
|----------|---------|-------------|
| `SHOW_FULL_SCREEN` | `True` | Launch in fullscreen kiosk mode |
| `ENABLE_FADE_ANIMATION` | `True` | Enable fade-in animation on startup |
| `SHOW_PARTY_BACKGROUND` | `True` | Show festive/event background image |
| `AUTO_EXPORT_ON_SHUTDOWN` | `True` | Auto-export scans to Excel on app close |

## Voice

| Variable | Default | Description |
|----------|---------|-------------|
| `VOICE_ENABLED` | `True` | Play voice confirmation on successful scan |
| `VOICE_VOLUME` | `1.0` | Playback volume (0.0-1.0) |

## Admin

| Variable | Default | Description |
|----------|---------|-------------|
| `ADMIN_PIN` | *(empty)* | 4-6 digit PIN to enable admin panel. Leave empty to disable. |

Admin panel is accessible from the dashboard header (gear icon). Features: view cloud scan count, clear cloud + local database (resets station name, auto-closes app).

## Logging

| Variable | Default | Description |
|----------|---------|-------------|
| `LOGGING_ENABLED` | `True` | Enable file logging |
| `LOGGING_FILE` | `logs/trackattendance.log` | Log file path |
| `LOGGING_LEVEL` | `INFO` | Log level: DEBUG, INFO, WARNING, ERROR, CRITICAL |
| `LOGGING_CONSOLE` | `True` | Also log to console/stdout |
| `LOG_SECRETS` | `False` | Log sensitive data (never enable in production) |

## Application Paths

These are directory/file names relative to the application root. Actual paths are computed at runtime based on execution mode (dev vs frozen).

| Constant | Value | Description |
|----------|-------|-------------|
| `DATA_DIRECTORY_NAME` | `data` | Database and roster directory |
| `EXPORT_DIRECTORY_NAME` | `exports` | Excel export output directory |
| `LOGS_DIRECTORY_NAME` | `logs` | Log file directory |
| `DATABASE_FILENAME` | `database.db` | SQLite database file |
| `EMPLOYEE_WORKBOOK_FILENAME` | `employee.xlsx` | Employee roster file |
