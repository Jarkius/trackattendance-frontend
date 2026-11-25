#!/usr/bin/env python3
"""Tests for the camera/screensaver diagnostics: named camera probe, the web->log bridge
and the "face too small" reject log.

Run: python tests/test_media_diagnostics.py
"""

import logging
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

os.environ.setdefault("CLOUD_API_KEY", "test-api-key-for-testing")
os.environ.setdefault("CLOUD_API_URL", "http://test.example.com")

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from main import Api, LOGGER  # noqa: E402

LOGGER_NAME = LOGGER.name


def _fake_cv2(open_map):
    """open_map: index -> 'ok' | 'noframe' | 'closed'. Unlisted indices are closed."""
    cv2 = MagicMock()

    def make(i):
        cap = MagicMock()
        state = open_map.get(i, "closed")
        cap.isOpened.return_value = state != "closed"
        frame = MagicMock()
        frame.shape = (480, 640, 3)
        cap.read.return_value = (state == "ok", frame if state == "ok" else None)
        cap.getBackendName.return_value = "DSHOW"
        return cap

    cv2.VideoCapture.side_effect = make
    return cv2


class TestProbeCameras(unittest.TestCase):
    def test_labels_carry_windows_names_and_resolution(self):
        res = Api._probe_cameras(_fake_cv2({0: "ok", 1: "ok"}), 0, False,
                                 ["HP 5MP Camera", "Poly Studio R30 Video"])
        self.assertEqual([c["index"] for c in res["cameras"]], [0, 1])
        self.assertIn("Poly Studio R30 Video", res["cameras"][1]["name"])
        self.assertIn("640x480", res["cameras"][1]["name"])
        self.assertEqual(res["skipped"], [])

    def test_named_device_that_cannot_open_is_reported_as_skipped(self):
        res = Api._probe_cameras(_fake_cv2({0: "ok", 1: "closed", 2: "noframe"}), 0, False,
                                 ["HP", "Poly", "HP IR"])
        self.assertEqual([c["index"] for c in res["cameras"]], [0])
        self.assertTrue(any(s.startswith("1:Poly") and "cannot open" in s for s in res["skipped"]))
        self.assertTrue(any(s.startswith("2:HP IR") and "no frame" in s for s in res["skipped"]))

    def test_active_running_camera_is_not_reopened(self):
        cv2 = _fake_cv2({1: "ok"})
        res = Api._probe_cameras(cv2, 0, True, ["HP", "Poly"])
        self.assertIn("(active)", res["cameras"][0]["name"])
        opened = [c.args[0] for c in cv2.VideoCapture.call_args_list]
        self.assertNotIn(0, opened)

    def test_works_without_names(self):
        res = Api._probe_cameras(_fake_cv2({0: "ok"}), 5, False)
        self.assertEqual(res["cameras"][0]["name"], "Camera 0 640x480 (DSHOW)")
        self.assertEqual(res["devices"], [])


class TestClientLogBridge(unittest.TestCase):
    def setUp(self):
        self.api = Api.__new__(Api)

    def test_known_category_is_logged_on_one_line_and_capped(self):
        with self.assertLogs(LOGGER_NAME, level="INFO") as cm:
            Api.log_client_event(self.api, "screensaver", "a\nb\r\x00c" + "x" * 1000)
        self.assertEqual(len(cm.records), 1)
        line = cm.records[0].getMessage()
        self.assertTrue(line.startswith("[UI:screensaver] a b c"))
        self.assertNotIn("\n", line)
        self.assertLessEqual(len(line), len("[UI:screensaver] ") + 300)

    def test_unknown_category_is_ignored(self):
        logger = logging.getLogger(LOGGER_NAME)
        with self.assertNoLogs(logger, level="INFO"):
            Api.log_client_event(self.api, "../../etc", "nope")

    def test_percent_signs_are_not_treated_as_format_strings(self):
        with self.assertLogs(LOGGER_NAME, level="INFO") as cm:
            Api.log_client_event(self.api, "audio", "100% %s %d")
        self.assertIn("100% %s %d", cm.records[0].getMessage())


class TestFaceTooSmallLog(unittest.TestCase):
    def test_reject_is_logged_throttled(self):
        try:
            import numpy as np
            from plugins.camera.proximity_detector import ProximityDetector
        except ImportError:
            self.skipTest("numpy/opencv not available")
        det = ProximityDetector(min_size_pct=0.20, skip_frames=0)
        det._use_yunet = True
        det._haar_upperbody = None
        yunet = MagicMock()
        # one face, 40 px wide in a 640 px frame (6%), score 0.9
        yunet.detect.return_value = (None, np.array([[10, 10, 40, 40] + [0] * 10 + [0.9]], dtype=float))
        det._yunet = yunet
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        with self.assertLogs("plugins.camera.proximity_detector", level="INFO") as cm:
            for _ in range(5):
                det.process_frame(frame)
        msgs = [r.getMessage() for r in cm.records if "too small" in r.getMessage()]
        self.assertEqual(len(msgs), 1)  # throttled to one line per 5 s
        self.assertIn("6%", msgs[0])
        self.assertIn("20%", msgs[0])


if __name__ == "__main__":
    unittest.main()
