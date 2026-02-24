"""Unit tests for ProximityDetector state machine.

Tests the presence state machine with synthetic frames by mocking cv2 and
mediapipe. Focuses on state transitions and confirm_frames filtering rather
than actual computer vision.

Usage:
    python tests/test_proximity_detector.py
"""

import os
import sys
import time
import types
import unittest
from unittest.mock import MagicMock, patch

# Add project root to path so `plugins.camera.*` can be imported
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import numpy as np

# ---------------------------------------------------------------------------
# Mock cv2 and mediapipe before importing ProximityDetector
# ---------------------------------------------------------------------------

_mock_cv2 = MagicMock()
_mock_cv2.cvtColor = MagicMock(side_effect=lambda frame, code: frame)
_mock_cv2.GaussianBlur = MagicMock(side_effect=lambda img, k, s: img)
_mock_cv2.absdiff = MagicMock(return_value=np.zeros((10, 10), dtype=np.uint8))
_mock_cv2.threshold = MagicMock(return_value=(25, np.zeros((10, 10), dtype=np.uint8)))
_mock_cv2.dilate = MagicMock(return_value=np.zeros((10, 10), dtype=np.uint8))
_mock_cv2.findContours = MagicMock(return_value=([], None))
_mock_cv2.COLOR_BGR2RGB = 4
_mock_cv2.COLOR_BGR2GRAY = 6
_mock_cv2.THRESH_BINARY = 0
_mock_cv2.RETR_EXTERNAL = 0
_mock_cv2.CHAIN_APPROX_SIMPLE = 1

sys.modules["cv2"] = _mock_cv2
sys.modules["numpy"] = np  # ensure real numpy is used
sys.modules["mediapipe"] = MagicMock()

# Now import — mediapipe init will fail (model files missing), falling back to motion
from plugins.camera.proximity_detector import ProximityDetector


def _make_frame():
    """Create a small synthetic BGR frame."""
    return np.zeros((10, 10, 3), dtype=np.uint8)


class TestProximityDetectorStateMachine(unittest.TestCase):
    """Test the presence state machine using a detector with mediapipe disabled."""

    def _make_detector(self, confirm_frames=3, absence_threshold=3.0, skip_frames=0):
        """Create a detector with mediapipe disabled and configurable params."""
        det = ProximityDetector.__new__(ProximityDetector)
        det.sensitivity = 5000
        det.cooldown = 5.0
        det.min_face_confidence = 0.5
        det.min_pose_confidence = 0.5
        det.skip_frames = skip_frames
        det.absence_threshold = absence_threshold
        det.confirm_frames = confirm_frames
        det._frame_count = 0
        det._last_detection_time = 0
        det._consecutive_detections = 0
        det._background_frame = None
        det._detection_callbacks = []
        det._last_detection_method = None
        det._presence_state = "empty"
        det._last_person_seen_time = 0.0
        det._mp_face = None
        det._mp_pose = None
        det._use_mediapipe = False
        det._mp = None
        return det

    def _feed_detection(self, det, person_in_frame: bool):
        """Simulate one processed frame with or without a person detected.

        Bypasses actual cv2 calls by directly manipulating the detection path.
        Returns the result of process_frame().
        """
        frame = _make_frame()

        # Patch _detect_motion to control detection result
        det._detect_motion = MagicMock(return_value=person_in_frame)

        return det.process_frame(frame)

    # ------------------------------------------------------------------
    # Core state machine transitions
    # ------------------------------------------------------------------

    def test_empty_to_present_on_confirm_frames(self):
        """empty → person detected N consecutive frames → present (greet fires)."""
        det = self._make_detector(confirm_frames=3)
        callback = MagicMock()
        det.add_detection_callback(callback)

        # First 2 detections: not enough to confirm
        self.assertFalse(self._feed_detection(det, True))
        self.assertEqual(det.presence_state, "empty")
        self.assertFalse(self._feed_detection(det, True))
        self.assertEqual(det.presence_state, "empty")

        # 3rd consecutive detection: confirmed → greet
        self.assertTrue(self._feed_detection(det, True))
        self.assertEqual(det.presence_state, "present")
        callback.assert_called_once()

    def test_no_repeat_greeting_while_present(self):
        """present + person still there → no repeat greeting."""
        det = self._make_detector(confirm_frames=1)
        callback = MagicMock()
        det.add_detection_callback(callback)

        # First detection triggers greeting
        self.assertTrue(self._feed_detection(det, True))
        self.assertEqual(callback.call_count, 1)

        # Subsequent detections while present should NOT trigger again
        for _ in range(5):
            self.assertFalse(self._feed_detection(det, True))
        self.assertEqual(callback.call_count, 1)

    def test_present_to_empty_after_absence_threshold(self):
        """present + no person for absence_threshold seconds → empty."""
        det = self._make_detector(confirm_frames=1, absence_threshold=2.0)
        callback = MagicMock()
        det.add_detection_callback(callback)

        # Enter present state
        self._feed_detection(det, True)
        self.assertEqual(det.presence_state, "present")

        # Person gone, but not long enough
        det._last_person_seen_time = time.time() - 1.0
        self._feed_detection(det, False)
        self.assertEqual(det.presence_state, "present")

        # Person gone for longer than absence_threshold
        det._last_person_seen_time = time.time() - 3.0
        self._feed_detection(det, False)
        self.assertEqual(det.presence_state, "empty")

    def test_re_greet_after_reset_to_empty(self):
        """After resetting to empty, a new person should trigger greeting again."""
        det = self._make_detector(confirm_frames=1, absence_threshold=1.0)
        callback = MagicMock()
        det.add_detection_callback(callback)

        # First person arrives
        self._feed_detection(det, True)
        self.assertEqual(callback.call_count, 1)

        # Person leaves (force absence)
        det._last_person_seen_time = time.time() - 2.0
        self._feed_detection(det, False)
        self.assertEqual(det.presence_state, "empty")

        # New person arrives → should greet again
        self._feed_detection(det, True)
        self.assertEqual(callback.call_count, 2)

    def test_empty_stays_empty_with_no_detection(self):
        """empty + no person → still empty, no callbacks."""
        det = self._make_detector(confirm_frames=3)
        callback = MagicMock()
        det.add_detection_callback(callback)

        for _ in range(10):
            self.assertFalse(self._feed_detection(det, False))

        self.assertEqual(det.presence_state, "empty")
        callback.assert_not_called()

    # ------------------------------------------------------------------
    # Confirm frames filtering
    # ------------------------------------------------------------------

    def test_single_frame_false_positive_no_greeting(self):
        """Single detection frame followed by no-detection should not greet."""
        det = self._make_detector(confirm_frames=3)
        callback = MagicMock()
        det.add_detection_callback(callback)

        # One detection then gone
        self._feed_detection(det, True)
        self._feed_detection(det, False)

        self.assertEqual(det.presence_state, "empty")
        callback.assert_not_called()

    def test_confirm_frames_counter_resets_on_gap(self):
        """Consecutive counter resets when a non-detection frame interrupts."""
        det = self._make_detector(confirm_frames=3)
        callback = MagicMock()
        det.add_detection_callback(callback)

        # 2 detections, then a gap, then 2 more — should NOT reach 3 consecutive
        self._feed_detection(det, True)
        self._feed_detection(det, True)
        self._feed_detection(det, False)  # resets counter
        self._feed_detection(det, True)
        self._feed_detection(det, True)

        self.assertEqual(det.presence_state, "empty")
        callback.assert_not_called()

        # Now 3 consecutive → should greet
        self._feed_detection(det, True)
        self.assertEqual(det.presence_state, "present")
        callback.assert_called_once()

    def test_confirm_frames_exactly_at_threshold(self):
        """Greeting fires on exactly the Nth consecutive detection."""
        for n in [1, 2, 5]:
            det = self._make_detector(confirm_frames=n)
            callback = MagicMock()
            det.add_detection_callback(callback)

            for i in range(n - 1):
                self.assertFalse(self._feed_detection(det, True),
                                 f"confirm_frames={n}: should not fire on frame {i+1}")
            self.assertTrue(self._feed_detection(det, True),
                            f"confirm_frames={n}: should fire on frame {n}")
            callback.assert_called_once()

    # ------------------------------------------------------------------
    # Frame skipping
    # ------------------------------------------------------------------

    def test_frame_skipping(self):
        """With skip_frames=2, only every 3rd frame is processed."""
        det = self._make_detector(confirm_frames=1, skip_frames=2)
        callback = MagicMock()
        det.add_detection_callback(callback)

        results = []
        for _ in range(9):
            results.append(self._feed_detection(det, True))

        # Only frames 3, 6, 9 are processed (0-indexed: frame_count 3, 6, 9)
        # Frame 3 is first processed frame → confirm_frames=1 → triggers
        # Frames 6, 9 → already present, no trigger
        self.assertEqual(results.count(True), 1)

    def test_skipped_frames_return_false(self):
        """Skipped frames should always return False without changing state."""
        det = self._make_detector(confirm_frames=1, skip_frames=1)
        callback = MagicMock()
        det.add_detection_callback(callback)

        # Frame 1: skipped
        result1 = self._feed_detection(det, True)
        self.assertFalse(result1)
        self.assertEqual(det.presence_state, "empty")

        # Frame 2: processed → trigger
        result2 = self._feed_detection(det, True)
        self.assertTrue(result2)
        self.assertEqual(det.presence_state, "present")

    # ------------------------------------------------------------------
    # Detection method tracking
    # ------------------------------------------------------------------

    def test_detection_method_tracks_motion_fallback(self):
        """Detection method should report 'motion' when using fallback."""
        det = self._make_detector(confirm_frames=1)
        self.assertEqual(det.detection_method, "none")

        self._feed_detection(det, True)
        self.assertEqual(det.detection_method, "motion")

    # ------------------------------------------------------------------
    # Callback error handling
    # ------------------------------------------------------------------

    def test_callback_exception_does_not_crash(self):
        """A failing callback should not prevent other callbacks from running."""
        det = self._make_detector(confirm_frames=1)
        bad_callback = MagicMock(side_effect=RuntimeError("boom"))
        good_callback = MagicMock()
        det.add_detection_callback(bad_callback)
        det.add_detection_callback(good_callback)

        self._feed_detection(det, True)

        bad_callback.assert_called_once()
        good_callback.assert_called_once()

    # ------------------------------------------------------------------
    # Reset
    # ------------------------------------------------------------------

    def test_reset_clears_state(self):
        """reset() should clear detection state but not presence state."""
        det = self._make_detector(confirm_frames=1)
        self._feed_detection(det, True)

        det.reset()
        self.assertIsNone(det._background_frame)
        self.assertEqual(det._frame_count, 0)
        self.assertIsNone(det._last_detection_method)


if __name__ == "__main__":
    unittest.main()
