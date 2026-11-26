"""Presence reporting from ProximityGreetingManager (drives the idle-video wake-up)."""
import unittest

from plugins.camera.proximity_manager import ProximityGreetingManager


class PresenceCallbackTests(unittest.TestCase):
    def test_reports_only_changes(self):
        seen = []
        mgr = ProximityGreetingManager(presence_callback=seen.append)
        for state in (False, True, True, False, False, True):
            mgr._notify_presence(state)
        self.assertEqual(seen, [True, False, True])

    def test_stop_clears_presence(self):
        seen = []
        mgr = ProximityGreetingManager(presence_callback=seen.append)
        mgr._notify_presence(True)
        mgr.stop()
        self.assertEqual(seen, [True, False])

    def test_callback_error_does_not_propagate(self):
        def boom(_):
            raise RuntimeError("ui gone")
        mgr = ProximityGreetingManager(presence_callback=boom)
        mgr._notify_presence(True)  # must not raise

    def test_no_callback_is_fine(self):
        ProximityGreetingManager()._notify_presence(True)


if __name__ == "__main__":
    unittest.main()
