"""
Configuration settings for Track Attendance application.

This module contains all configuration parameters for cloud sync,
database settings, and application behavior.
"""

# =============================================================================
# Cloud API Configuration
# =============================================================================

# Production Cloud Run API endpoint
CLOUD_API_URL = "https://trackattendance-api-969370105809.asia-southeast1.run.app"

# API authentication key
CLOUD_API_KEY = "6541f2c7892b4e5287d50c2414d179f8"

# Number of scans to sync in each batch
CLOUD_SYNC_BATCH_SIZE = 100


# =============================================================================
# Auto-Sync Configuration
# =============================================================================

# Enable/disable automatic synchronization
AUTO_SYNC_ENABLED = True

# Time in seconds to wait after last scan before allowing auto-sync
# This ensures auto-sync only happens during idle periods
AUTO_SYNC_IDLE_SECONDS = 30

# Interval in seconds to check if auto-sync should run
# Auto-sync will check every N seconds if conditions are met
AUTO_SYNC_CHECK_INTERVAL_SECONDS = 60

# Minimum number of pending scans required to trigger auto-sync
# Set to 1 to sync as soon as any scan is pending
AUTO_SYNC_MIN_PENDING_SCANS = 1

# Show status message when auto-sync starts
AUTO_SYNC_SHOW_START_MESSAGE = True

# Show status message when auto-sync completes
AUTO_SYNC_SHOW_COMPLETE_MESSAGE = True

# Duration in milliseconds to show auto-sync messages
AUTO_SYNC_MESSAGE_DURATION_MS = 3000

# Network connection timeout in seconds for connectivity checks
AUTO_SYNC_CONNECTION_TIMEOUT = 5


# =============================================================================
# Application Paths
# =============================================================================

# These are relative paths from the application root
# Actual paths are computed in main.py based on execution mode

DATA_DIRECTORY_NAME = "data"
EXPORT_DIRECTORY_NAME = "exports"
DATABASE_FILENAME = "database.db"
EMPLOYEE_WORKBOOK_FILENAME = "employee.xlsx"


# =============================================================================
# UI Configuration
# =============================================================================

# Window behavior
SHOW_FULL_SCREEN = True
ENABLE_FADE_ANIMATION = True

# Export behavior
AUTO_EXPORT_ON_SHUTDOWN = True
