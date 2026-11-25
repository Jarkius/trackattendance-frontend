#!/usr/bin/env python3
"""Bridge between the page and the native video panel (spec: docs/specs/native-video-playback.md).

Run: python tests/test_screensaver_video_bridge.py
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("CLOUD_API_KEY", "test-api-key-for-testing")
os.environ.setdefault("CLOUD_API_URL", "http://test.example.com")

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from PyQt6.QtCore import QObject, pyqtSignal  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

import main as main_module  # noqa: E402
from main import Api  # noqa: E402

APP = QApplication.instance() or QApplication([])


class RecordingPanel(QObject):
    """Stand-in for NativeVideoPanel: records play/stop/volume."""
    failed = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.calls = []
        self.is_playing = False

    def play(self, path, volume, loop_pause_s):
        self.calls.append(("play", Path(path).name, volume, loop_pause_s))
        self.is_playing = True

    def stop(self):
        self.calls.append(("stop",))
        self.is_playing = False

    def set_volume(self, v):
        self.calls.append(("volume", v))


class ImmediateProbe(QObject):
    """Stand-in for VideoProbe: 'plays' every candidate whose name is not in `bad`."""
    finished = pyqtSignal(object)
    bad = set()

    def __init__(self, candidates):
        super().__init__()
        self._c = candidates

    def start(self):
        rejected = []
        for c in self._c:
            if c["name"] in self.bad:
                rejected.append({**c, "why": "Could not open file"})
                continue
            self.finished.emit({"chosen": c, "rejected": rejected})
            return
        self.finished.emit({"chosen": None, "rejected": rejected})


class BridgeTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        base = Path(self._tmp.name)
        self.event = base / "media"
        self.builtin = base / "assets" / "media"
        self.builtin.mkdir(parents=True)
        (self.builtin / "default-loop.webm").write_bytes(b"x")
        (self.builtin / "default-key-visual.png").write_bytes(b"x")
        self._dirs = (main_module.EVENT_MEDIA_DIRECTORY, main_module.BUILTIN_MEDIA_DIRECTORY)
        main_module.EVENT_MEDIA_DIRECTORY, main_module.BUILTIN_MEDIA_DIRECTORY = self.event, self.builtin

        self.api = Api.__new__(Api)
        QObject.__init__(self.api)
        self.panel = RecordingPanel()
        self.ready = []
        self.failures = []
        self.api.screensaver_media_ready.connect(self.ready.append)
        self.api.screensaver_video_failed.connect(self.failures.append)
        ImmediateProbe.bad = set()

    def tearDown(self):
        main_module.EVENT_MEDIA_DIRECTORY, main_module.BUILTIN_MEDIA_DIRECTORY = self._dirs
        self._tmp.cleanup()

    def start(self):
        Api.attach_native_video(self.api, self.panel)
        Api.start_screensaver_media_check(self.api, make_probe=ImmediateProbe)


class TestMediaState(BridgeTestCase):
    def test_pending_before_the_check_runs(self):
        Api.attach_native_video(self.api, self.panel)
        self.assertEqual(Api.get_screensaver_media(self.api), {"pending": True})

    def test_ready_state_names_the_chosen_video_and_lists_images(self):
        self.event.mkdir()
        (self.event / "event.mp4").write_bytes(b"x")
        self.start()
        state = Api.get_screensaver_media(self.api)
        self.assertEqual(state["video"], {"name": "event.mp4", "source": "media folder"})
        self.assertEqual(state["video_rejected"], [])
        self.assertEqual([c["name"] for c in state["image"]], ["default-key-visual.png"])
        self.assertEqual(state["folder"], str(self.event))
        self.assertEqual(self.ready, [state])            # pushed to the page as well
        self.assertNotIn("url", state["video"])          # the page never gets a video path

    def test_unplayable_event_video_falls_back_and_says_why(self):
        self.event.mkdir()
        (self.event / "broken.mp4").write_bytes(b"x")
        ImmediateProbe.bad = {"broken.mp4"}
        self.start()
        state = Api.get_screensaver_media(self.api)
        self.assertEqual(state["video"]["name"], "default-loop.webm")
        self.assertEqual([(r["name"], r["why"]) for r in state["video_rejected"]],
                         [("broken.mp4", "Could not open file")])


class TestPlayback(BridgeTestCase):
    def test_play_starts_the_chosen_video_only(self):
        self.start()
        result = Api.screensaver_video_play(self.api, 0.0, 30)
        self.assertTrue(result["ok"])
        self.assertEqual(self.panel.calls[-1], ("play", "default-loop.webm", 0.0, 30))

    def test_play_refuses_when_no_video_is_usable(self):
        (self.builtin / "default-loop.webm").unlink()
        self.start()
        self.assertFalse(Api.screensaver_video_play(self.api, 1.0, 0)["ok"])
        self.assertEqual(self.panel.calls, [])

    def test_play_refuses_before_the_check_finished(self):
        Api.attach_native_video(self.api, self.panel)
        self.assertFalse(Api.screensaver_video_play(self.api, 1.0, 0)["ok"])

    def test_pause_and_volume_inputs_are_bounded(self):
        self.start()
        Api.screensaver_video_play(self.api, 5.0, 99999)
        self.assertEqual(self.panel.calls[-1], ("play", "default-loop.webm", 1.0, 300))
        Api.screensaver_video_play(self.api, -1.0, -5)
        self.assertEqual(self.panel.calls[-1], ("play", "default-loop.webm", 0.0, 0))
        Api.screensaver_video_set_volume(self.api, 2.5)
        self.assertEqual(self.panel.calls[-1], ("volume", 1.0))

    def test_stop(self):
        self.start()
        Api.screensaver_video_play(self.api, 1.0, 0)
        Api.screensaver_video_stop(self.api)
        self.assertEqual(self.panel.calls[-1], ("stop",))

    def test_panel_failure_reaches_the_page(self):
        self.start()
        self.panel.failed.emit("decoder error")
        self.assertEqual(self.failures, ["decoder error"])


if __name__ == "__main__":
    unittest.main()
