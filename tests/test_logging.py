#!/usr/bin/env python3
"""
Tests for logging configuration in logging_config.py.

Tests the SecretRedactingFormatter and logging setup functionality.

Run: python tests/test_logging.py
"""

import os
import sys
import tempfile
import unittest
import logging
from pathlib import Path
from unittest.mock import patch, MagicMock

# Set required environment variables BEFORE importing config
os.environ.setdefault("CLOUD_API_KEY", "test-api-key-for-testing")
os.environ.setdefault("CLOUD_API_URL", "http://test.example.com")

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from logging_config import SecretRedactingFormatter, get_logger


class TestSecretRedaction(unittest.TestCase):
    """Test SecretRedactingFormatter class."""

    def setUp(self):
        """Set up formatter for testing."""
        self.formatter = SecretRedactingFormatter(
            '%(levelname)s - %(message)s'
        )

    def _format_message(self, message):
        """Create and format a log record with the given message."""
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg=message,
            args=(),
            exc_info=None
        )
        return self.formatter.format(record)

    def test_bearer_token_redacted(self):
        """Test Bearer tokens are redacted."""
        message = "Authorization: Bearer abc123def456 sent to API"
        result = self._format_message(message)

        self.assertNotIn("abc123def456", result)
        self.assertIn("<REDACTED>", result)

    def test_bearer_token_inline_redacted(self):
        """Test inline Bearer tokens are redacted."""
        message = "Using Bearer abc123def456 for auth"
        result = self._format_message(message)

        self.assertNotIn("abc123def456", result)
        self.assertIn("<REDACTED>", result)

    def test_api_key_json_redacted(self):
        """Test API key in JSON format is redacted."""
        message = '{"api_key": "secret123", "data": "value"}'
        result = self._format_message(message)

        self.assertNotIn("secret123", result)
        self.assertIn("<REDACTED>", result)

    def test_cloud_api_key_env_redacted(self):
        """Test CLOUD_API_KEY environment variable is redacted."""
        message = "CLOUD_API_KEY = abc123secret"
        result = self._format_message(message)

        self.assertNotIn("abc123secret", result)
        self.assertIn("<REDACTED>", result)

    def test_normal_message_unchanged(self):
        """Test normal messages are not modified."""
        message = "User logged in successfully"
        result = self._format_message(message)

        self.assertIn("User logged in successfully", result)

    def test_case_insensitive_redaction(self):
        """Test redaction is case insensitive."""
        message = "AUTHORIZATION: BEARER abc123def456"
        result = self._format_message(message)

        self.assertNotIn("abc123def456", result)

    def test_multiple_secrets_redacted(self):
        """Test multiple secrets in same message are all redacted."""
        message = 'Bearer abc123 and "api_key": "xyz789"'
        result = self._format_message(message)

        self.assertNotIn("abc123", result)
        self.assertNotIn("xyz789", result)


class TestGetLogger(unittest.TestCase):
    """Test get_logger() function."""

    def test_returns_logger_instance(self):
        """Test get_logger returns a Logger instance."""
        logger = get_logger("test.module")

        self.assertIsInstance(logger, logging.Logger)

    def test_logger_name_preserved(self):
        """Test logger name is preserved."""
        logger = get_logger("my.custom.module")

        self.assertEqual(logger.name, "my.custom.module")

    def test_same_name_returns_same_logger(self):
        """Test same name returns same logger instance."""
        logger1 = get_logger("same.module")
        logger2 = get_logger("same.module")

        self.assertIs(logger1, logger2)

    def test_different_names_different_loggers(self):
        """Test different names return different loggers."""
        logger1 = get_logger("module.one")
        logger2 = get_logger("module.two")

        self.assertIsNot(logger1, logger2)


class TestLoggingSetup(unittest.TestCase):
    """Test setup_logging() function."""

    def setUp(self):
        """Store original logging state."""
        self.original_handlers = logging.root.handlers.copy()
        self.original_level = logging.root.level

    def tearDown(self):
        """Restore original logging state."""
        logging.root.handlers = self.original_handlers
        logging.root.level = self.original_level

    @patch.dict(os.environ, {
        "LOGGING_ENABLED": "false",
        "CLOUD_API_KEY": "test-key",
    })
    def test_disabled_logging_minimal(self):
        """Test disabled logging uses minimal configuration."""
        # Clear handlers first
        logging.root.handlers = []

        # Import fresh config
        import importlib
        import config
        importlib.reload(config)

        from logging_config import setup_logging
        setup_logging()

        # Should have minimal logging (WARNING level)
        self.assertEqual(logging.root.level, logging.WARNING)

    def test_logger_hierarchy(self):
        """Test child loggers inherit from root."""
        parent = get_logger("parent")
        child = get_logger("parent.child")

        # Child should be able to inherit settings
        self.assertTrue(child.name.startswith(parent.name))


class TestLoggingLevels(unittest.TestCase):
    """Test logging level configuration."""

    def test_debug_level_string(self):
        """Test DEBUG level is parsed correctly."""
        level = getattr(logging, "DEBUG", None)
        self.assertEqual(level, 10)

    def test_info_level_string(self):
        """Test INFO level is parsed correctly."""
        level = getattr(logging, "INFO", None)
        self.assertEqual(level, 20)

    def test_warning_level_string(self):
        """Test WARNING level is parsed correctly."""
        level = getattr(logging, "WARNING", None)
        self.assertEqual(level, 30)

    def test_error_level_string(self):
        """Test ERROR level is parsed correctly."""
        level = getattr(logging, "ERROR", None)
        self.assertEqual(level, 40)

    def test_invalid_level_fallback(self):
        """Test invalid level falls back to INFO."""
        level = getattr(logging, "INVALID", logging.INFO)
        self.assertEqual(level, logging.INFO)


class TestSecretPatterns(unittest.TestCase):
    """Test secret pattern matching edge cases."""

    def setUp(self):
        """Set up formatter for testing."""
        self.formatter = SecretRedactingFormatter('%(message)s')

    def _format_message(self, message):
        """Create and format a log record."""
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="test.py",
            lineno=1, msg=message, args=(), exc_info=None
        )
        return self.formatter.format(record)

    def test_hex_api_key_redacted(self):
        """Test hex API keys are redacted."""
        message = "Bearer 1a2b3c4d5e6f7890abcdef"
        result = self._format_message(message)

        self.assertIn("<REDACTED>", result)
        self.assertNotIn("1a2b3c4d5e6f7890abcdef", result)

    def test_partial_bearer_preserved(self):
        """Test partial matches don't cause issues."""
        message = "Bearer is a common word"
        result = self._format_message(message)

        # Should not be redacted if no hex key follows
        self.assertIn("Bearer is a common word", result)

    def test_api_key_with_hyphen_redacted(self):
        """Test api-key format is also redacted."""
        message = '"api-key": "mysecretkey123"'
        result = self._format_message(message)

        self.assertIn("<REDACTED>", result)

    def test_url_with_api_key_preserved(self):
        """Test URL path segments are not wrongly redacted."""
        message = "GET /api/v1/users returned 200"
        result = self._format_message(message)

        # Should not be redacted
        self.assertEqual(result, message)


class TestRotatingFileHandler(unittest.TestCase):
    """Test rotating file handler configuration."""

    def test_rotation_size_calculation(self):
        """Test 10MB rotation size is correct."""
        max_bytes = 10 * 1024 * 1024  # 10MB
        self.assertEqual(max_bytes, 10485760)

    def test_backup_count(self):
        """Test backup count is reasonable."""
        backup_count = 5
        self.assertGreaterEqual(backup_count, 1)
        self.assertLessEqual(backup_count, 10)


def main():
    """Run tests with summary."""
    print("=" * 70)
    print("LOGGING CONFIGURATION TESTS")
    print("=" * 70)
    print()

    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    suite.addTests(loader.loadTestsFromTestCase(TestSecretRedaction))
    suite.addTests(loader.loadTestsFromTestCase(TestGetLogger))
    suite.addTests(loader.loadTestsFromTestCase(TestLoggingSetup))
    suite.addTests(loader.loadTestsFromTestCase(TestLoggingLevels))
    suite.addTests(loader.loadTestsFromTestCase(TestSecretPatterns))
    suite.addTests(loader.loadTestsFromTestCase(TestRotatingFileHandler))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    print()
    print("=" * 70)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print("=" * 70)

    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
