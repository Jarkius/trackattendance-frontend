"""
Logging configuration for Track Attendance application.

Provides file and console logging with automatic secret redaction.
Logs all sync/export errors with timestamps for diagnostics.
"""

import logging
import logging.handlers
import os
import re
from pathlib import Path


class SecretRedactingFormatter(logging.Formatter):
    """Custom formatter that redacts sensitive information from logs."""

    # Patterns to redact
    SECRETS_PATTERNS = [
        (r'Bearer\s+[a-f0-9]+', 'Bearer <REDACTED>'),  # API keys
        (r'Authorization:\s*Bearer\s+[a-f0-9]+', 'Authorization: Bearer <REDACTED>'),
        (r'"api[_-]?key"\s*:\s*"[^"]*"', '"api_key": "<REDACTED>"'),
        (r'CLOUD_API_KEY\s*=\s*[^\s]*', 'CLOUD_API_KEY = <REDACTED>'),
    ]

    def format(self, record):
        """Format log record and redact secrets."""
        # Format the message
        msg = super().format(record)

        # Redact secrets
        for pattern, replacement in self.SECRETS_PATTERNS:
            msg = re.sub(pattern, replacement, msg, flags=re.IGNORECASE)

        return msg


def setup_logging():
    """
    Configure logging for Track Attendance application.

    Sets up:
    - File logging to logs/trackattendance.log
    - Console logging with color support
    - Automatic secret redaction
    - Timestamp formatting
    - Rotation at 10MB
    """
    from config import (
        LOGGING_ENABLED,
        LOGGING_FILE,
        LOGGING_LEVEL,
        LOGGING_CONSOLE,
        LOGS_DIRECTORY_NAME,
        LOG_SECRETS,
    )

    if not LOGGING_ENABLED:
        # Minimal logging if disabled
        logging.basicConfig(level=logging.WARNING)
        return

    # Create logs directory
    logs_dir = Path(LOGS_DIRECTORY_NAME)
    logs_dir.mkdir(parents=True, exist_ok=True)

    # Set up root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, LOGGING_LEVEL, logging.INFO))

    # Clear any existing handlers
    root_logger.handlers = []

    # Log format with timestamp
    log_format = '%(asctime)s [%(levelname)-8s] %(name)s - %(message)s'
    date_format = '%Y-%m-%d %H:%M:%S'

    # Create formatter
    if LOG_SECRETS:
        # Don't redact in debug mode
        formatter = logging.Formatter(log_format, datefmt=date_format)
    else:
        # Redact secrets by default
        formatter = SecretRedactingFormatter(log_format, datefmt=date_format)

    # File handler with rotation
    log_file = Path(LOGGING_FILE)
    log_file.parent.mkdir(parents=True, exist_ok=True)

    try:
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,  # Keep 5 rotated files
            encoding='utf-8',
        )
        file_handler.setLevel(getattr(logging, LOGGING_LEVEL, logging.INFO))
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
    except Exception as e:
        print(f"Warning: Could not set up file logging: {e}")

    # Console handler
    if LOGGING_CONSOLE:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(getattr(logging, LOGGING_LEVEL, logging.INFO))
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)

    # Log startup
    logger = logging.getLogger(__name__)
    logger.info("Logging configured - Level: %s, File: %s", LOGGING_LEVEL, LOGGING_FILE)
    if not LOG_SECRETS:
        logger.debug("Secret redaction enabled")


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance for a module."""
    return logging.getLogger(name)
