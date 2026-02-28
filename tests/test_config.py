#!/usr/bin/env python3
"""
Tests for configuration loading and validation in config.py.

Tests the _safe_int() and _safe_float() helper functions and
environment variable parsing.

Run: python tests/test_config.py
"""

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

# Set required environment variables BEFORE importing anything
# This prevents config.py from calling sys.exit(1)
os.environ.setdefault("CLOUD_API_KEY", "test-api-key-for-testing")
os.environ.setdefault("CLOUD_API_URL", "http://test.example.com")

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestSafeInt(unittest.TestCase):
    """Test _safe_int helper function."""

    def _get_safe_int(self):
        """Import _safe_int fresh to avoid caching issues."""
        import importlib
        import config
        importlib.reload(config)
        return config._safe_int

    def test_valid_integer_string(self):
        """Test valid integer string is parsed correctly."""
        with patch.dict(os.environ, {"TEST_INT": "42"}):
            safe_int = self._get_safe_int()
            result = safe_int("TEST_INT", 0)
            self.assertEqual(result, 42)

    def test_missing_env_returns_default(self):
        """Test missing env var returns default value."""
        # Ensure TEST_MISSING is not set
        os.environ.pop("TEST_MISSING", None)
        safe_int = self._get_safe_int()
        result = safe_int("TEST_MISSING", 99)
        self.assertEqual(result, 99)

    def test_empty_string_returns_default(self):
        """Test empty string returns default value."""
        with patch.dict(os.environ, {"TEST_EMPTY": ""}):
            safe_int = self._get_safe_int()
            result = safe_int("TEST_EMPTY", 50)
            self.assertEqual(result, 50)

    def test_non_numeric_returns_default(self):
        """Test non-numeric string returns default."""
        with patch.dict(os.environ, {"TEST_NAN": "not_a_number"}):
            safe_int = self._get_safe_int()
            result = safe_int("TEST_NAN", 100)
            self.assertEqual(result, 100)

    def test_float_string_returns_default(self):
        """Test float string returns default (int() doesn't handle floats)."""
        with patch.dict(os.environ, {"TEST_FLOAT": "42.9"}):
            safe_int = self._get_safe_int()
            result = safe_int("TEST_FLOAT", 99)
            # int("42.9") raises ValueError, so default is returned
            self.assertEqual(result, 99)

    def test_negative_value(self):
        """Test negative value is parsed correctly."""
        with patch.dict(os.environ, {"TEST_NEG": "-10"}):
            safe_int = self._get_safe_int()
            result = safe_int("TEST_NEG", 0)
            self.assertEqual(result, -10)

    def test_min_value_clamps(self):
        """Test value below min is clamped to min."""
        with patch.dict(os.environ, {"TEST_LOW": "5"}):
            safe_int = self._get_safe_int()
            result = safe_int("TEST_LOW", 50, min_val=10)
            self.assertEqual(result, 10)

    def test_max_value_clamps(self):
        """Test value above max is clamped to max."""
        with patch.dict(os.environ, {"TEST_HIGH": "200"}):
            safe_int = self._get_safe_int()
            result = safe_int("TEST_HIGH", 50, max_val=100)
            self.assertEqual(result, 100)

    def test_min_and_max_together(self):
        """Test both min and max clamping."""
        safe_int = self._get_safe_int()

        # Below min
        with patch.dict(os.environ, {"TEST_RANGE": "5"}):
            result = safe_int("TEST_RANGE", 50, min_val=10, max_val=100)
            self.assertEqual(result, 10)

        # Above max
        with patch.dict(os.environ, {"TEST_RANGE": "200"}):
            result = safe_int("TEST_RANGE", 50, min_val=10, max_val=100)
            self.assertEqual(result, 100)

        # Within range
        with patch.dict(os.environ, {"TEST_RANGE": "50"}):
            result = safe_int("TEST_RANGE", 0, min_val=10, max_val=100)
            self.assertEqual(result, 50)

    def test_whitespace_trimmed(self):
        """Test whitespace in value is handled."""
        with patch.dict(os.environ, {"TEST_SPACE": "  42  "}):
            safe_int = self._get_safe_int()
            result = safe_int("TEST_SPACE", 0)
            # int() handles whitespace
            self.assertEqual(result, 42)

    def test_zero_value(self):
        """Test zero is valid."""
        with patch.dict(os.environ, {"TEST_ZERO": "0"}):
            safe_int = self._get_safe_int()
            result = safe_int("TEST_ZERO", 99)
            self.assertEqual(result, 0)


class TestSafeFloat(unittest.TestCase):
    """Test _safe_float helper function."""

    def _get_safe_float(self):
        """Import _safe_float fresh."""
        import importlib
        import config
        importlib.reload(config)
        return config._safe_float

    def test_valid_float_string(self):
        """Test valid float string is parsed."""
        with patch.dict(os.environ, {"TEST_FLOAT": "3.14"}):
            safe_float = self._get_safe_float()
            result = safe_float("TEST_FLOAT", 0.0)
            self.assertAlmostEqual(result, 3.14, places=2)

    def test_integer_string_as_float(self):
        """Test integer string converts to float."""
        with patch.dict(os.environ, {"TEST_INT": "42"}):
            safe_float = self._get_safe_float()
            result = safe_float("TEST_INT", 0.0)
            self.assertEqual(result, 42.0)

    def test_missing_returns_default(self):
        """Test missing env var returns default."""
        os.environ.pop("TEST_MISSING_FLOAT", None)
        safe_float = self._get_safe_float()
        result = safe_float("TEST_MISSING_FLOAT", 1.5)
        self.assertEqual(result, 1.5)

    def test_non_numeric_returns_default(self):
        """Test non-numeric returns default."""
        with patch.dict(os.environ, {"TEST_NAN": "not_a_float"}):
            safe_float = self._get_safe_float()
            result = safe_float("TEST_NAN", 2.5)
            self.assertEqual(result, 2.5)

    def test_min_clamps(self):
        """Test value below min is clamped."""
        with patch.dict(os.environ, {"TEST_LOW": "0.1"}):
            safe_float = self._get_safe_float()
            result = safe_float("TEST_LOW", 1.0, min_val=0.5)
            self.assertEqual(result, 0.5)

    def test_max_clamps(self):
        """Test value above max is clamped."""
        with patch.dict(os.environ, {"TEST_HIGH": "10.0"}):
            safe_float = self._get_safe_float()
            result = safe_float("TEST_HIGH", 1.0, max_val=5.0)
            self.assertEqual(result, 5.0)

    def test_scientific_notation(self):
        """Test scientific notation is parsed."""
        with patch.dict(os.environ, {"TEST_SCI": "1.5e2"}):
            safe_float = self._get_safe_float()
            result = safe_float("TEST_SCI", 0.0)
            self.assertEqual(result, 150.0)

    def test_negative_float(self):
        """Test negative float is parsed."""
        with patch.dict(os.environ, {"TEST_NEG": "-3.14"}):
            safe_float = self._get_safe_float()
            result = safe_float("TEST_NEG", 0.0)
            self.assertAlmostEqual(result, -3.14, places=2)


class TestBooleanParsing(unittest.TestCase):
    """Test boolean configuration parsing patterns."""

    def test_true_values(self):
        """Test various 'true' value representations."""
        true_values = ["True", "true", "TRUE", "1", "yes", "YES"]

        for val in true_values:
            result = val.lower() in ("true", "1", "yes")
            self.assertTrue(result, f"'{val}' should be True")

    def test_false_values(self):
        """Test various 'false' value representations."""
        false_values = ["False", "false", "FALSE", "0", "no", "NO", ""]

        for val in false_values:
            result = val.lower() in ("true", "1", "yes")
            self.assertFalse(result, f"'{val}' should be False")


class TestConfigurationValues(unittest.TestCase):
    """Test actual configuration values are within expected ranges."""

    def test_batch_size_reasonable(self):
        """Test CLOUD_SYNC_BATCH_SIZE is reasonable."""
        with patch.dict(os.environ, {"CLOUD_API_KEY": "test-key"}):
            import importlib
            import config
            importlib.reload(config)

            self.assertGreaterEqual(config.CLOUD_SYNC_BATCH_SIZE, 1)
            self.assertLessEqual(config.CLOUD_SYNC_BATCH_SIZE, 1000)

    def test_timeout_reasonable(self):
        """Test CONNECTION_CHECK_TIMEOUT_SECONDS is reasonable."""
        with patch.dict(os.environ, {"CLOUD_API_KEY": "test-key"}):
            import importlib
            import config
            importlib.reload(config)

            self.assertGreaterEqual(config.CONNECTION_CHECK_TIMEOUT_SECONDS, 0.5)
            self.assertLessEqual(config.CONNECTION_CHECK_TIMEOUT_SECONDS, 30.0)

    def test_auto_sync_idle_reasonable(self):
        """Test AUTO_SYNC_IDLE_SECONDS is reasonable."""
        with patch.dict(os.environ, {"CLOUD_API_KEY": "test-key"}):
            import importlib
            import config
            importlib.reload(config)

            self.assertGreaterEqual(config.AUTO_SYNC_IDLE_SECONDS, 5)
            self.assertLessEqual(config.AUTO_SYNC_IDLE_SECONDS, 3600)

    def test_duplicate_time_window_reasonable(self):
        """Test DUPLICATE_BADGE_TIME_WINDOW_SECONDS is reasonable."""
        with patch.dict(os.environ, {"CLOUD_API_KEY": "test-key"}):
            import importlib
            import config
            importlib.reload(config)

            self.assertGreaterEqual(config.DUPLICATE_BADGE_TIME_WINDOW_SECONDS, 1)
            self.assertLessEqual(config.DUPLICATE_BADGE_TIME_WINDOW_SECONDS, 3600)


class TestDuplicateActionConfig(unittest.TestCase):
    """Test duplicate badge action configuration."""

    def test_default_action(self):
        """Test default duplicate action is 'warn'."""
        with patch.dict(os.environ, {"CLOUD_API_KEY": "test-key"}, clear=False):
            os.environ.pop("DUPLICATE_BADGE_ACTION", None)
            import importlib
            import config
            importlib.reload(config)

            self.assertEqual(config.DUPLICATE_BADGE_ACTION, "warn")

    def test_block_action(self):
        """Test 'block' action is recognized."""
        with patch.dict(os.environ, {
            "CLOUD_API_KEY": "test-key",
            "DUPLICATE_BADGE_ACTION": "block"
        }):
            import importlib
            import config
            importlib.reload(config)

            self.assertEqual(config.DUPLICATE_BADGE_ACTION, "block")

    def test_silent_action(self):
        """Test 'silent' action is recognized."""
        with patch.dict(os.environ, {
            "CLOUD_API_KEY": "test-key",
            "DUPLICATE_BADGE_ACTION": "silent"
        }):
            import importlib
            import config
            importlib.reload(config)

            self.assertEqual(config.DUPLICATE_BADGE_ACTION, "silent")

    def test_case_insensitive(self):
        """Test action is case-insensitive."""
        with patch.dict(os.environ, {
            "CLOUD_API_KEY": "test-key",
            "DUPLICATE_BADGE_ACTION": "BLOCK"
        }):
            import importlib
            import config
            importlib.reload(config)

            self.assertEqual(config.DUPLICATE_BADGE_ACTION, "block")


def main():
    """Run tests with summary."""
    print("=" * 70)
    print("CONFIGURATION TESTS")
    print("=" * 70)
    print()

    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    suite.addTests(loader.loadTestsFromTestCase(TestSafeInt))
    suite.addTests(loader.loadTestsFromTestCase(TestSafeFloat))
    suite.addTests(loader.loadTestsFromTestCase(TestBooleanParsing))
    suite.addTests(loader.loadTestsFromTestCase(TestConfigurationValues))
    suite.addTests(loader.loadTestsFromTestCase(TestDuplicateActionConfig))

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
