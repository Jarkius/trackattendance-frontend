"""
Configuration settings for Track Attendance application.

This module loads configuration from environment variables (.env file or system env).
Never commit secrets to git. Use .env file (ignored by git) for local development.
"""

import os
import sys
from pathlib import Path

# Load environment variables from .env file if it exists
# For frozen exe: check next to exe first, then bundled location
try:
    from dotenv import load_dotenv

    env_loaded = False

    # For frozen builds, check next to the exe first (user-editable)
    if getattr(sys, 'frozen', False):
        exe_dir = Path(sys.executable).parent
        exe_env = exe_dir / ".env"
        if exe_env.exists():
            load_dotenv(exe_env)
            env_loaded = True
            print(f"[Config] Loaded .env from: {exe_env}")

    # Fall back to script/bundled location
    if not env_loaded:
        script_env = Path(__file__).parent / ".env"
        if script_env.exists():
            load_dotenv(script_env)
            print(f"[Config] Loaded .env from: {script_env}")
except ImportError:
    # python-dotenv not available, will use system environment only
    pass


# =============================================================================
# Cloud API Configuration
# =============================================================================

# Production Cloud Run API endpoint
CLOUD_API_URL = os.getenv(
    "CLOUD_API_URL",
    "https://trackattendance-api-969370105809.asia-southeast1.run.app"
)

# API authentication key - REQUIRED
# Load from environment variable for security
# Fail fast if not provided
CLOUD_API_KEY = os.getenv("CLOUD_API_KEY")
if not CLOUD_API_KEY:
    print("\n" + "="*70)
    print("ERROR: CLOUD_API_KEY not set")
    print("="*70)
    print("\nTrackAttendance requires a cloud API key to sync data.")
    print("\nTo fix this:\n")
    print("  1. Copy .env.example to .env:")
    print("     cp .env.example .env\n")
    print("  2. Edit .env and fill in your CLOUD_API_KEY:\n")
    print("     CLOUD_API_KEY=your-actual-api-key-here\n")
    print("  3. Restart the application\n")
    print("For help, see: README.md > Cloud Synchronization > Configuration")
    print("="*70 + "\n")
    sys.exit(1)

# Number of scans to sync in each batch
CLOUD_SYNC_BATCH_SIZE = int(os.getenv("CLOUD_SYNC_BATCH_SIZE", "100"))


# =============================================================================
# Connection Health Check
# =============================================================================

def _parse_connection_interval_ms() -> int:
    """
    Parse connection interval from env.

    Supports either CONNECTION_CHECK_INTERVAL_SECONDS (preferred, seconds)
    or CONNECTION_CHECK_INTERVAL_MS (legacy, milliseconds). Returns ms.
    """
    seconds_raw = os.getenv("CONNECTION_CHECK_INTERVAL_SECONDS")
    if seconds_raw is not None:
        try:
            seconds_val = float(seconds_raw)
            return max(0, int(seconds_val * 1000))
        except ValueError:
            pass

    ms_raw = os.getenv("CONNECTION_CHECK_INTERVAL_MS", "10000")
    try:
        return max(0, int(ms_raw))
    except ValueError:
        return 10000


# Interval (ms) for UI connection status polling; set to 0 to disable polling.
# Prefer configuring CONNECTION_CHECK_INTERVAL_SECONDS in .env for clarity.
CONNECTION_CHECK_INTERVAL_MS = _parse_connection_interval_ms()

# Timeout (seconds) for cloud API health checks triggered by the UI
CONNECTION_CHECK_TIMEOUT_SECONDS = float(os.getenv("CONNECTION_CHECK_TIMEOUT_SECONDS", "1.5"))

# Initial connection check delay in milliseconds (converted from seconds)
# Default: 15 seconds. Indicator starts black (invisible), so no rush to check during startup
CONNECTION_CHECK_INITIAL_DELAY_MS = int(float(os.getenv("CONNECTION_CHECK_INITIAL_DELAY_SECONDS", "15")) * 1000)


# =============================================================================
# Auto-Sync Configuration
# =============================================================================

# Enable/disable automatic synchronization
AUTO_SYNC_ENABLED = os.getenv("AUTO_SYNC_ENABLED", "True").lower() in ("true", "1", "yes")

# Time in seconds to wait after last scan before allowing auto-sync
# This ensures auto-sync only happens during idle periods
AUTO_SYNC_IDLE_SECONDS = int(os.getenv("AUTO_SYNC_IDLE_SECONDS", "30"))

# Interval in seconds to check if auto-sync should run
# Auto-sync will check every N seconds if conditions are met
AUTO_SYNC_CHECK_INTERVAL_SECONDS = int(os.getenv("AUTO_SYNC_CHECK_INTERVAL_SECONDS", "60"))

# Minimum number of pending scans required to trigger auto-sync
# Set to 1 to sync as soon as any scan is pending
AUTO_SYNC_MIN_PENDING_SCANS = int(os.getenv("AUTO_SYNC_MIN_PENDING_SCANS", "1"))

# Show status message when auto-sync starts
AUTO_SYNC_SHOW_START_MESSAGE = os.getenv("AUTO_SYNC_SHOW_START_MESSAGE", "True").lower() in ("true", "1", "yes")

# Show status message when auto-sync completes
AUTO_SYNC_SHOW_COMPLETE_MESSAGE = os.getenv("AUTO_SYNC_SHOW_COMPLETE_MESSAGE", "True").lower() in ("true", "1", "yes")

# Duration in milliseconds to show auto-sync messages
AUTO_SYNC_MESSAGE_DURATION_MS = int(os.getenv("AUTO_SYNC_MESSAGE_DURATION_MS", "3000"))

# Network connection timeout in seconds for connectivity checks
AUTO_SYNC_CONNECTION_TIMEOUT = int(os.getenv("AUTO_SYNC_CONNECTION_TIMEOUT", "5"))


# =============================================================================
# Sync Resilience Configuration
# =============================================================================

# Retry failed sync operations with exponential backoff
SYNC_RETRY_ENABLED = os.getenv("SYNC_RETRY_ENABLED", "True").lower() in ("true", "1", "yes")
SYNC_RETRY_MAX_ATTEMPTS = int(os.getenv("SYNC_RETRY_MAX_ATTEMPTS", "3"))
SYNC_RETRY_BACKOFF_SECONDS = int(os.getenv("SYNC_RETRY_BACKOFF_SECONDS", "5"))

# Auto-sync failure handling
AUTO_SYNC_MAX_CONSECUTIVE_FAILURES = int(os.getenv("AUTO_SYNC_MAX_CONSECUTIVE_FAILURES", "5"))
AUTO_SYNC_FAILURE_COOLDOWN_SECONDS = int(os.getenv("AUTO_SYNC_FAILURE_COOLDOWN_SECONDS", "300"))


# =============================================================================
# Roster Validation Configuration
# =============================================================================

# Expected column headers in employee.xlsx
REQUIRED_ROSTER_COLUMNS = [
    "Legacy ID",
    "Full Name",
    "SL L1 Desc",
    "Position Desc"
]

# Show warning if roster is missing or invalid
ROSTER_VALIDATION_ENABLED = os.getenv("ROSTER_VALIDATION_ENABLED", "True").lower() in ("true", "1", "yes")

# Skip import if any required columns are missing
ROSTER_STRICT_VALIDATION = os.getenv("ROSTER_STRICT_VALIDATION", "True").lower() in ("true", "1", "yes")


# =============================================================================
# Logging Configuration
# =============================================================================

# File logging for diagnostics
LOGGING_ENABLED = os.getenv("LOGGING_ENABLED", "True").lower() in ("true", "1", "yes")
LOGGING_FILE = os.getenv("LOGGING_FILE", "logs/trackattendance.log")
LOGGING_LEVEL = os.getenv("LOGGING_LEVEL", "INFO")
LOGGING_CONSOLE = os.getenv("LOGGING_CONSOLE", "True").lower() in ("true", "1", "yes")
LOG_SECRETS = os.getenv("LOG_SECRETS", "False").lower() in ("true", "1", "yes")


# =============================================================================
# Application Paths
# =============================================================================

# These are relative paths from the application root
# Actual paths are computed in main.py based on execution mode

DATA_DIRECTORY_NAME = "data"
EXPORT_DIRECTORY_NAME = "exports"
LOGS_DIRECTORY_NAME = "logs"
DATABASE_FILENAME = "database.db"
EMPLOYEE_WORKBOOK_FILENAME = "employee.xlsx"


# =============================================================================
# UI Configuration
# =============================================================================

# Window behavior
SHOW_FULL_SCREEN = os.getenv("SHOW_FULL_SCREEN", "True").lower() in ("true", "1", "yes")
ENABLE_FADE_ANIMATION = os.getenv("ENABLE_FADE_ANIMATION", "True").lower() in ("true", "1", "yes")

# Party/Event background image
SHOW_PARTY_BACKGROUND = os.getenv("SHOW_PARTY_BACKGROUND", "True").lower() in ("true", "1", "yes")

# Export behavior
AUTO_EXPORT_ON_SHUTDOWN = os.getenv("AUTO_EXPORT_ON_SHUTDOWN", "True").lower() in ("true", "1", "yes")


# =============================================================================
# Duplicate Badge Detection Configuration (Issue #20, #21)
# =============================================================================

# Enable/disable duplicate badge detection
# Prevents users from scanning the same badge multiple times in quick succession
DUPLICATE_BADGE_DETECTION_ENABLED = os.getenv("DUPLICATE_BADGE_DETECTION_ENABLED", "True").lower() in ("true", "1", "yes")

# Time window in seconds to consider scans as duplicates
# Example: If set to 60, scanning same badge within 60s is considered duplicate
DUPLICATE_BADGE_TIME_WINDOW_SECONDS = int(os.getenv("DUPLICATE_BADGE_TIME_WINDOW_SECONDS", "60"))

# Action to take when duplicate badge is detected
# 'warn': Accept scan + show yellow warning alert (default)
# 'block': Reject duplicate scan + show red error alert
# 'silent': Accept scan + no alert shown (for testing)
DUPLICATE_BADGE_ACTION = os.getenv("DUPLICATE_BADGE_ACTION", "warn").lower()

# Duration in milliseconds to show duplicate badge alert before auto-dismiss
DUPLICATE_BADGE_ALERT_DURATION_MS = int(os.getenv("DUPLICATE_BADGE_ALERT_DURATION_MS", "3000"))

# Duration in milliseconds to show employee name and "THANK YOU" after scan
# before returning to "Ready to scan..." state
SCAN_FEEDBACK_DURATION_MS = int(os.getenv("SCAN_FEEDBACK_DURATION_MS", "2000"))
