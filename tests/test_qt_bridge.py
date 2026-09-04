#!/usr/bin/env python3
"""Tests for qt_bridge.call_without_freezing_ui.

Covers the fix for Dashboard/Settings freezing the whole app: several
QWebChannel-exposed slots called requests.*() directly on the Qt main
thread, blocking the entire event loop (rendering, keyboard input via
QWebEngineView, everything) for however long the network call took.

call_without_freezing_ui(fn) runs fn() on a worker thread and pumps a nested
QEventLoop on the calling thread while waiting, so the caller still gets a
synchronous return value but the UI thread's event loop keeps processing
other events in the meantime.

Each scenario runs in its own subprocess (same interpreter) rather than
in-process. A QApplication instance persists for the rest of a process once
constructed, so testing "no QApplication" and "with QApplication" behavior
in the same process would make the outcome depend on test/file execution
order — fragile. Fresh subprocesses avoid that entirely. As a side benefit,
if the no-QApplication fallback guard were ever broken, the failure mode
(QEventLoop.exec() never returning) becomes a clean bounded-timeout test
failure instead of hanging the whole test run.

Requires PyQt6. Tests are skipped with a clear message when PyQt6 is
unavailable, matching the existing skip pattern elsewhere in this suite.

Run: python tests/test_qt_bridge.py
"""

import subprocess
import sys
import textwrap
import unittest
from pathlib import Path

REPO_ROOT = str(Path(__file__).parent.parent)

try:
    from PyQt6.QtWidgets import QApplication  # noqa: F401
    PYQT6_AVAILABLE = True
except ImportError:
    PYQT6_AVAILABLE = False

SUBPROCESS_TIMEOUT_S = 15


def _run_script(body: str) -> subprocess.CompletedProcess:
    """Run `body` in a fresh interpreter with the repo root on sys.path.

    A hard timeout turns "the no-QApplication fallback is broken" (which
    would otherwise hang forever on a nested QEventLoop.exec() with no
    event-loop machinery to pump it) into a clean, fast test failure.
    """
    script = f"import sys; sys.path.insert(0, {REPO_ROOT!r})\n" + textwrap.dedent(body)
    return subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True, text=True, timeout=SUBPROCESS_TIMEOUT_S,
    )


@unittest.skipUnless(PYQT6_AVAILABLE, "PyQt6 not installed in this environment")
class TestCallWithoutFreezingUi(unittest.TestCase):
    def test_no_qapplication_calls_fn_directly(self):
        """No QApplication/QCoreApplication instance exists — the pytest
        case, and every environment that runs this test suite today.
        call_without_freezing_ui must fall back to calling fn() directly,
        identical to the pre-fix behavior."""
        proc = _run_script("""
            from PyQt6.QtWidgets import QApplication
            from qt_bridge import call_without_freezing_ui
            assert QApplication.instance() is None, "test premise violated"

            calls = []
            def fn():
                calls.append(1)
                return 42

            result = call_without_freezing_ui(fn)
            assert result == 42, f"expected 42, got {result!r}"
            assert calls == [1], f"expected fn called exactly once, got {calls!r}"
            print("OK")
        """)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("OK", proc.stdout)

    def test_no_qapplication_propagates_exception(self):
        proc = _run_script("""
            from qt_bridge import call_without_freezing_ui

            def fn():
                raise ValueError("boom")

            try:
                call_without_freezing_ui(fn)
                print("FAIL: no exception raised")
            except ValueError as e:
                print(f"OK: {e}")
        """)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("OK: boom", proc.stdout)

    def test_with_qapplication_returns_correct_value(self):
        proc = _run_script("""
            from PyQt6.QtWidgets import QApplication
            from qt_bridge import call_without_freezing_ui
            app = QApplication([])

            result = call_without_freezing_ui(lambda: 1 + 1)
            assert result == 2, f"expected 2, got {result!r}"
            print("OK")
        """)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("OK", proc.stdout)

    def test_with_qapplication_propagates_exception(self):
        proc = _run_script("""
            from PyQt6.QtWidgets import QApplication
            from qt_bridge import call_without_freezing_ui
            app = QApplication([])

            def fn():
                raise RuntimeError("network failed")

            try:
                call_without_freezing_ui(fn)
                print("FAIL: no exception raised")
            except RuntimeError as e:
                print(f"OK: {e}")
        """)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("OK: network failed", proc.stdout)

    def test_event_loop_stays_pumped_during_wait(self):
        """The regression proof: with a real QApplication, a QTimer
        scheduled just before the call fires WHILE call_without_freezing_ui
        is waiting on the worker thread — demonstrating the main thread's
        event loop is not frozen, unlike a direct blocking requests.get()
        call would leave it."""
        proc = _run_script("""
            import time
            from PyQt6.QtWidgets import QApplication
            from PyQt6.QtCore import QTimer
            from qt_bridge import call_without_freezing_ui
            app = QApplication([])

            timer_fired_during_wait = []
            QTimer.singleShot(50, lambda: timer_fired_during_wait.append(True))

            def slow_fn():
                time.sleep(0.3)
                return "done"

            result = call_without_freezing_ui(slow_fn)

            assert result == "done", f"expected 'done', got {result!r}"
            assert timer_fired_during_wait == [True], (
                "QTimer never fired during call_without_freezing_ui's wait "
                "-- the event loop was frozen, not pumped."
            )
            print("OK")
        """)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("OK", proc.stdout)


def main():
    print("=" * 70)
    print("QT_BRIDGE TESTS")
    print("=" * 70)
    if not PYQT6_AVAILABLE:
        print("\n[SKIP] PyQt6 is not installed in this environment.")
        print("All tests in this file are skipped — qt_bridge.py cannot be")
        print("imported without PyQt6. Run this file in a PyQt6-enabled")
        print("environment for real coverage.\n")
    print()

    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    suite.addTests(loader.loadTestsFromTestCase(TestCallWithoutFreezingUi))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    print()
    print("=" * 70)
    print(f"Tests run: {result.testsRun}")
    print(f"Skipped: {len(result.skipped)}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print("=" * 70)

    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
