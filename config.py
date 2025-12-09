"""
Configuration settings for Track Attendance application.

This module loads configuration from environment variables (.env file or system env).
Never commit secrets to git. Use .env file (ignored by git) for local development.
"""

import os
import sys
from pathlib import Path

# Load environment variables from .env file if it exists
try:
    from dotenv import load_dotenv
    env_file = Path(__file__).parent / ".env"
    if env_file.exists():
        load_dotenv(env_file)
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
    print("For help, see: README.md → Cloud Synchronization → Configuration")
    print("="*70 + "\n")
    sys.exit(1)

# Number of scans to sync in each batch
CLOUD_SYNC_BATCH_SIZE = int(os.getenv("CLOUD_SYNC_BATCH_SIZE", "100"))


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

# Export behavior
AUTO_EXPORT_ON_SHUTDOWN = os.getenv("AUTO_EXPORT_ON_SHUTDOWN", "True").lower() in ("true", "1", "yes")
