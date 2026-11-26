"""Camera greeting is muted while the hold screen blocks scans (it would invite an ignored scan)."""
import unittest

from plugins.camera.proximity_manager import ProximityGreetingManager


class FakeGreetingPlayer:
    def __init__(self):
        self.plays = 0

    def play_random(self):
        self.plays += 1


def make_manager(suppressed):
    mgr = ProximityGreetingManager(greeting_suppressed=suppressed)
    mgr._greeting_player = FakeGreetingPlayer()
    return mgr


class GreetingSuppressedTests(unittest.TestCase):
    def test_greets_when_not_suppressed(self):
        mgr = make_manager(lambda: False)
        mgr._on_person_detected()
        self.assertEqual(mgr._greeting_player.plays, 1)

    def test_silent_while_suppressed(self):
        mgr = make_manager(lambda: True)
        mgr._on_person_detected()
        self.assertEqual(mgr._greeting_player.plays, 0)

    def test_checked_at_call_time(self):
        state = {"blocked": True}
        mgr = make_manager(lambda: state["blocked"])
        mgr._on_person_detected()
        state["blocked"] = False
        mgr._on_person_detected()
        self.assertEqual(mgr._greeting_player.plays, 1)

    def test_no_check_greets(self):
        mgr = ProximityGreetingManager()
        mgr._greeting_player = FakeGreetingPlayer()
        mgr._on_person_detected()
        self.assertEqual(mgr._greeting_player.plays, 1)

    def test_check_error_greets(self):
        def boom():
            raise RuntimeError("config gone")
        mgr = make_manager(boom)
        mgr._on_person_detected()  # must not raise
        self.assertEqual(mgr._greeting_player.plays, 1)


if __name__ == "__main__":
    unittest.main()
