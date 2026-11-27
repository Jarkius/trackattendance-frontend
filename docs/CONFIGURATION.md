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
| `DUPLICATE_BADGE_TIME_WINDOW_SECONDS` | `60` | Time window to consider scans as duplicates (1-86400; the admin panel's "Always" preset uses 86400 = 24h) |
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

## Hold Screen & Idle Screensaver

Full-screen overlay showing a still key visual or a video loop. Two independent uses.

**Event content:** put the event's files in a `media\` folder next to `TrackAttendance.exe` (in development: next to `main.py`; `build.bat` ships a repo-root `media\`). Video: `.mp4` or `.webm` (it plays in Qt's own media player, which handles the usual H.264/AAC MP4). Image: `.jpg`, `.png` or `.webp`. Video and image are chosen separately; when several files of a kind are present, the one added most recently is used, and any file the kiosk cannot play is skipped for the next one. Without usable event files the neutral built-in defaults (`assets/media`) are shown. Admin → Settings shows which files are in use and why any were skipped, and greys out Video/Image when none is usable.

**Video that will not play:** Admin shows why it was skipped. As a fallback, `scripts\convert-to-webm.bat input.mp4` re-encodes it to WebM with ffmpeg (install it with `winget install Gyan.FFmpeg`).

**Pause between loops** (video on the idle screensaver and the hold screen): the video rests silently on its first frame for this many seconds between plays, so a looping video with sound is less tiring during an event. Admin slider, or `VIDEO_LOOP_PAUSE_SECONDS`.

All of these are also in the admin panel (Settings) and persist across restarts; a value saved from the admin panel or by pressing Esc overrides `.env`.

**Idle screensaver** (during the event): appears after the idle time, any input closes it, returns after the next idle period.

| Variable | Default | Description |
|----------|---------|-------------|
| `SCREENSAVER_ENABLED` | `False` | Turn the idle screensaver on |
| `SCREENSAVER_CONTENT` | `video` | `video` / `image` |
| `SCREENSAVER_IDLE_SECONDS` | `60` | Idle seconds before it appears (min `5`; admin slider 5-300) |
| `SCREENSAVER_MUTED` | `False` | Play the video silently. Also applies to the hold screen video (Admin: Video Sound) |
| `SCREENSAVER_CAMERA` | `wake` | Needs `ENABLE_CAMERA_DETECTION`. `off` = ignore the camera; `wake` = a person arriving closes it and it will not restart while someone is in front of the station; `sound` = the video keeps looping, sound fades in (about 2 s) when a person is seen and out after they leave. On the hold screen `sound` works the same, while `wake` and `off` do nothing (only Esc releases the hold) |

**Hold screen** (before check-in opens): shows at once and stays. `Esc` releases it for good (saved; no timeout resume, survives reboot until released). `Ctrl+Shift+H` or the admin toggle turns it back on.

**Rehearsal, then reset:** with `HOLD_ENABLED=True` in `.env`, any clear puts the hold screen back up with `.env`'s `HOLD_SCANS`, replacing an Esc release or scans setting changed during testing. Admin → Clear ALL stations on one station resets every online station within one health check (`CONNECTION_CHECK_INTERVAL_SECONDS`); those stations skip the "Data Cleared" pop-up because the hold screen is back up. A station that was offline during the clear does not upload its old scans when it reconnects: it applies the clear first. Without `HOLD_ENABLED=True` in `.env`, a clear leaves the hold screen as it is.

| Variable | Default | Description |
|----------|---------|-------------|
| `HOLD_ENABLED` | `False` | Start with the hold screen up. After an Esc release the saved `False` wins over `.env`, so re-arm with `Ctrl+Shift+H` or the admin toggle |
| `HOLD_CONTENT` | `image` | `image` / `video` |
| `VIDEO_LOOP_PAUSE_SECONDS` | `0` | Screensaver and hold screen video: seconds resting on the first frame (silent) between loops; `0` = loop without a break (max 300) |
| `VIDEO_END_FADE_SECONDS` | `0` | Video sound (screensaver and hold screen) fades in over the first N seconds and out over the last N of every play, so a loop does not cut off abruptly; `0` = off (max 10, `.env` only; capped at half the clip length) |
| `HOLD_SCANS` | `accept` | Scans while held: `accept` = recorded, normal result shown for about 8 s, then back to the hold screen; `block` = scans ignored and the camera greeting is muted, since it would ask people to scan (use when early scans must not count) |

Notes:
- While either overlay is showing, `Esc` only dismisses it; it does not close the app.
- The video plays in Qt's own media player (not the web page), so normal H.264/AAC MP4 and WebM both work. Camera `wake`/`sound` use the presence state of the camera detection plugin, so for far-away people lower `CAMERA_MIN_SIZE_PCT`, or on a wide-angle camera use `CAMERA_DETECTOR=person` (see Camera Detection).
- Stations must not sleep or turn off the display, or the overlay will not be seen.

## Voice

| Variable | Default | Description |
|----------|---------|-------------|
| `VOICE_ENABLED` | `True` | Play voice confirmation on successful scan |
| `VOICE_VOLUME` | `1.0` | Playback volume (0.0-1.0) |

## Admin

| Variable | Default | Description |
|----------|---------|-------------|
| `ADMIN_PIN` | *(empty)* | 4-6 digit PIN to enable admin panel. Leave empty to disable. |

Admin panel is accessible from the dashboard header (gear icon). Features: view cloud scan count, clear cloud + local database, runtime camera/voice/duplicate settings, reset camera to defaults, debug controls (log level, console output, debug panel).

## Camera Detection

| Variable | Default | Description |
|----------|---------|-------------|
| `ENABLE_CAMERA_DETECTION` | `False` | Enable camera proximity greeting plugin |
| `CAMERA_DEVICE_ID` | `0` | Camera index (`0` = default webcam) |
| `CAMERA_SHOW_OVERLAY` | `True` | Show floating camera preview (`False` = icon-only mode for production) |
| `CAMERA_GREETING_COOLDOWN_SECONDS` | `60` | Minimum seconds between greetings per person |
| `CAMERA_SCAN_BUSY_SECONDS` | `30` | Suppress greetings after a badge scan |
| `CAMERA_DETECTOR` | `face` | What counts as "someone is there": `face` (YuNet face + upper-body fallback, normal webcams) or `person` (YOLOX-Nano whole body, wide-angle cameras). Admin → Camera → Detect |
| `CAMERA_MIN_SIZE_PCT` | `0.20` | Faces: minimum face size as fraction of frame width ("Min Face") |
| `CAMERA_MIN_PERSON_PCT` | `0.30` | People: minimum person height as fraction of frame **height** ("Min Person", 0.10-0.90) |
| `CAMERA_PERSON_CONFIDENCE` | `0.50` | People: minimum model confidence for a person (0.30-0.90, `.env` only) |
| `CAMERA_ABSENCE_THRESHOLD_SECONDS` | `5` | Seconds with no person before kiosk resets to "empty" |
| `CAMERA_CONFIRM_FRAMES` | `3` | Consecutive detected frames required before greeting |
| `CAMERA_HAAR_MIN_NEIGHBORS` | `5` | Faces only: Haar cascade strictness (2-10, higher = fewer false positives) |
| `CAMERA_DETECTION_SCALE` | `0.5` | Faces only: detection frame downscale. People always uses the full frame |

Faces detection chain: YuNet DNN face → Upper body Haar → Frontal face Haar → Motion (frame differencing).

### Detect: Faces vs People

People mode runs YOLOX-Nano (Apache-2.0, `plugins/camera/models/NOTICE-YOLOX.md`) on
onnxruntime, about 30 ms per checked frame on 2 CPU threads. It finds whole bodies, so it
ignores furniture (the upper-body fallback counted a shelf as a person) and still finds people
whose face is small, turned away or out of the picture. Each mode keeps its own size setting;
switching in Admin applies at once, without a restart. If the model or onnxruntime cannot
load, the station runs Faces, logs why, and Admin shows "People detection unavailable".

Suggested values, measured on a Poly Studio R30 (wide lens) at 640x480: a person about 4-5 m
away facing the camera = 41% of frame height, people across the room = 14%, at the kiosk = 100%.

| Station | Detect | Size |
|---|---|---|
| Normal webcam, greeting only | Faces | Min Face 20% (default) |
| Wide-angle camera, video loop with camera `wake` / `sound` | People | Min Person 30% (default) |
| Busy hall, people walking close behind | People | Min Person 40-50% |
| Wake from further away | People | Min Person 20-25% (passers-by may wake it) |
| Wide-angle camera that must stay on Faces | Faces | Min Face 9-10% (expect furniture false alarms) |

Tune with the log: `State: empty → present (person, ..., box NN% of frame height)` and
`Person seen but too small: NN% of frame height (needs >= MM%)`. Background:
`ψ/memory/learnings/2026-11-26_person-detector-poc.md`.

## Logging & Debug

| Variable | Default | Description |
|----------|---------|-------------|
| `LOGGING_ENABLED` | `True` | Enable file logging |
| `LOGGING_FILE` | `logs/trackattendance.log` | Log file path |
| `LOGGING_LEVEL` | `INFO` | Log level: DEBUG, INFO, WARNING, ERROR, CRITICAL |
| `LOGGING_CONSOLE` | `True` | Also log to console/stdout |
| `LOG_SECRETS` | `False` | Log sensitive data (never enable in production) |
| `DEBUG` | `False` | Enable debug mode (disables focus lock for kiosk input) |

### Runtime Debug Controls (Admin Panel)

These settings are available in the admin panel under the **Debug** section and persist across restarts in the local SQLite database:

| Setting | Options | Description |
|---------|---------|-------------|
| **Log Level** | ERROR / WARN / INFO / DEBUG | Changes the runtime log level for all handlers (except the debug buffer, which always captures at DEBUG level) |
| **Console Output** | On / Off | Toggles stderr StreamHandler at runtime |
| **Debug Panel** | On / Off | Enables the live log streaming overlay in the kiosk UI |

**Debug Panel features:**
- Live Python log streaming via 500ms polling (thread-safe ring buffer, 200 lines)
- Color-coded log levels (red=ERROR, amber=WARN, cyan=DEBUG, white=INFO)
- Click any line to copy to clipboard
- "Copy All" button copies entire log buffer
- Clipboard fallback for QWebEngineView `file://` context (uses `execCommand('copy')`)
- When active, focus lock disengages — allows free clicking, text selection, and copy

## Application Paths

These are directory/file names relative to the application root. Actual paths are computed at runtime based on execution mode (dev vs frozen).

| Constant | Value | Description |
|----------|-------|-------------|
| `DATA_DIRECTORY_NAME` | `data` | Database and roster directory |
| `EXPORT_DIRECTORY_NAME` | `exports` | Excel export output directory |
| `LOGS_DIRECTORY_NAME` | `logs` | Log file directory |
| `DATABASE_FILENAME` | `database.db` | SQLite database file |
| `EMPLOYEE_WORKBOOK_FILENAME` | `employee.xlsx` | Employee roster file |
