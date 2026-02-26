"""
Person proximity detection using MediaPipe (face + pose).
Falls back to simple motion detection if MediaPipe is unavailable.

Extracted from poc/camera/camera_scanner.py for production use.
Camera does NOT scan barcodes — badge scanning remains USB-only.
"""

from __future__ import annotations

import logging
import os
import sys
import time
from typing import Callable, List, Optional, TYPE_CHECKING

LOGGER = logging.getLogger(__name__)

if TYPE_CHECKING:
    import numpy as np

# cv2 and numpy are late-imported by the manager before this module is loaded,
# but we also guard here so the module can be imported for inspection without
# hard-failing when the deps are absent.
try:
    import cv2
    import numpy
except ImportError:
    cv2 = None  # type: ignore[assignment]
    numpy = None  # type: ignore[assignment]


class ProximityDetector:
    """
    Person proximity detection using MediaPipe (face + pose).
    Falls back to simple motion detection if MediaPipe is unavailable.

    Detection strategy (handles varying heights and laptop positions):
    1. Face detection — works when face is visible (any angle/distance)
    2. Pose detection — works when body is visible (even without face)
    3. Motion fallback — catches movement if MediaPipe fails

    A person is "detected" when either a face OR a body pose is found.
    """

    def __init__(self, sensitivity: int = 5000, cooldown: float = 5.0,
                 min_face_confidence: float = 0.5, min_pose_confidence: float = 0.5,
                 skip_frames: int = 2, absence_threshold: float = 3.0,
                 confirm_frames: int = 3, min_size_pct: float = 0.20):
        self.sensitivity = sensitivity  # for motion fallback
        self.cooldown = cooldown  # minimum seconds between greetings
        self.min_face_confidence = min_face_confidence
        self.min_pose_confidence = min_pose_confidence
        self.min_size_pct = min_size_pct  # minimum detection size as fraction of frame
        self.skip_frames = skip_frames  # process every Nth frame to save CPU
        self.absence_threshold = absence_threshold  # seconds with no detection before state → empty
        self.confirm_frames = confirm_frames  # consecutive detections required before greeting
        self._frame_count = 0
        self._last_detection_time = 0
        self._consecutive_detections = 0  # count of consecutive frames with person
        self._background_frame: Optional[np.ndarray] = None
        self._detection_callbacks: List[Callable[[], None]] = []
        self._last_detection_method: Optional[str] = None

        # Presence state: "empty" or "present"
        # Greeting only fires on transition from empty → present
        self._presence_state: str = "empty"
        self._last_person_seen_time: float = 0.0

        # Try to initialize MediaPipe (tasks API — v0.10.x+)
        self._mp_face = None
        self._mp_pose = None
        self._use_mediapipe = False
        self._mp = None  # mediapipe module reference

        # Model files directory — bundled inside exe or alongside this script
        if getattr(sys, 'frozen', False):
            models_dir = os.path.join(sys._MEIPASS, 'plugins', 'camera', 'models')
        else:
            models_dir = os.path.join(os.path.dirname(__file__), 'models')

        try:
            import mediapipe as mp
            self._mp = mp

            face_model = os.path.join(models_dir, 'blaze_face_short_range.tflite')
            pose_model = os.path.join(models_dir, 'pose_landmarker_lite.task')

            if not os.path.exists(face_model) or not os.path.exists(pose_model):
                raise FileNotFoundError(
                    f"Model files missing in {models_dir}. "
                    "Download blaze_face_short_range.tflite and pose_landmarker_lite.task"
                )

            base_opts_face = mp.tasks.BaseOptions(model_asset_path=face_model)
            face_opts = mp.tasks.vision.FaceDetectorOptions(
                base_options=base_opts_face,
                running_mode=mp.tasks.vision.RunningMode.IMAGE,
                min_detection_confidence=self.min_face_confidence,
            )
            self._mp_face = mp.tasks.vision.FaceDetector.create_from_options(face_opts)

            base_opts_pose = mp.tasks.BaseOptions(model_asset_path=pose_model)
            pose_opts = mp.tasks.vision.PoseLandmarkerOptions(
                base_options=base_opts_pose,
                running_mode=mp.tasks.vision.RunningMode.IMAGE,
                min_pose_detection_confidence=self.min_pose_confidence,
            )
            self._mp_pose = mp.tasks.vision.PoseLandmarker.create_from_options(pose_opts)

            self._use_mediapipe = True
            LOGGER.info("[Proximity] MediaPipe face+pose detection active (min_size_pct=%.2f)", self.min_size_pct)
        except ImportError:
            LOGGER.warning("[Proximity] MediaPipe not available, using motion fallback (min_size_pct=%.2f)", self.min_size_pct)
        except Exception as e:
            LOGGER.warning("[Proximity] MediaPipe init failed (%s), using motion fallback", e)

    @property
    def detection_method(self) -> str:
        """Return which detection method was used last."""
        return self._last_detection_method or "none"

    def add_detection_callback(self, callback: Callable[[], None]):
        """Add callback for proximity detection."""
        self._detection_callbacks.append(callback)

    def _detect_person_mediapipe(self, frame: np.ndarray) -> Optional[str]:
        """Detect person using MediaPipe face and pose detection (tasks API).
        Returns detection method string or None."""
        mp = self._mp
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)

        frame_w = frame.shape[1]

        # Try face detection first (faster)
        if self._mp_face:
            face_results = self._mp_face.detect(mp_image)
            for det in (face_results.detections or []):
                # Filter by bounding box width relative to frame
                bbox_w = det.bounding_box.width
                if bbox_w / frame_w >= self.min_size_pct:
                    return "face"

        # Try pose detection (catches body even without visible face)
        if self._mp_pose:
            pose_results = self._mp_pose.detect(mp_image)
            for landmarks in (pose_results.pose_landmarks or []):
                # Use horizontal spread of landmarks as size proxy
                xs = [lm.x for lm in landmarks]
                spread = max(xs) - min(xs)
                if spread >= self.min_size_pct:
                    return "pose"

        return None

    def _detect_motion(self, frame: np.ndarray) -> bool:
        """Fallback: simple motion detection via frame differencing.

        Also applies min_size_pct filter — the largest motion contour's
        bounding-box width must fill at least min_size_pct of the frame.
        """
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (21, 21), 0)

        if self._background_frame is None:
            self._background_frame = gray
            return False

        frame_delta = cv2.absdiff(self._background_frame, gray)
        thresh = cv2.threshold(frame_delta, 25, 255, cv2.THRESH_BINARY)[1]
        thresh = cv2.dilate(thresh, None, iterations=2)
        contours, _ = cv2.findContours(thresh.copy(), cv2.RETR_EXTERNAL,
                                        cv2.CHAIN_APPROX_SIMPLE)

        self._background_frame = gray

        frame_w = frame.shape[1]
        for contour in contours:
            if cv2.contourArea(contour) > self.sensitivity:
                # Apply size filter — motion region must be close enough
                _, _, w, _ = cv2.boundingRect(contour)
                if w / frame_w >= self.min_size_pct:
                    return True
        return False

    @property
    def presence_state(self) -> str:
        """Current presence state: 'empty' or 'present'."""
        return self._presence_state

    def process_frame(self, frame: np.ndarray) -> bool:
        """Process frame for person detection with presence-aware state machine.

        State transitions:
          empty   + person seen  → present (fire callbacks = greet)
          present + person seen  → present (no callbacks = stay quiet)
          present + no person for absence_threshold seconds → empty
          empty   + no person    → empty   (no change)

        Uses MediaPipe face+pose when available, falls back to motion detection.
        """
        current_time = time.time()

        # Skip frames to save CPU (process every Nth frame)
        self._frame_count += 1
        if self._frame_count % (self.skip_frames + 1) != 0:
            return False

        # Detect person in this frame
        person_in_frame = False
        if self._use_mediapipe:
            method = self._detect_person_mediapipe(frame)
            if method:
                person_in_frame = True
                self._last_detection_method = method
        else:
            if self._detect_motion(frame):
                person_in_frame = True
                self._last_detection_method = "motion"

        if person_in_frame:
            self._last_person_seen_time = current_time
            self._consecutive_detections += 1

            if self._presence_state == "empty":
                # Require N consecutive detections to confirm a real person
                if self._consecutive_detections < self.confirm_frames:
                    return False

                # Confirmed: empty → present
                self._presence_state = "present"

                # Enforce minimum gap between greetings (cooldown)
                since_last_greet = current_time - self._last_detection_time
                if since_last_greet < self.cooldown:
                    return False

                # Greet the newcomer
                self._last_detection_time = current_time
                for callback in self._detection_callbacks:
                    try:
                        callback()
                    except Exception as e:
                        print(f"Detection callback error: {e}")
                return True
            # Already present — stay quiet
            return False

        # No person in frame — reset consecutive counter
        self._consecutive_detections = 0

        # Check if absent long enough to reset presence state
        if self._presence_state == "present":
            elapsed = current_time - self._last_person_seen_time
            if elapsed >= self.absence_threshold:
                self._presence_state = "empty"

        return False

    def reset(self):
        """Reset detector state."""
        self._background_frame = None
        self._last_detection_time = 0
        self._frame_count = 0
        self._last_detection_method = None

    def close(self):
        """Release MediaPipe resources."""
        if self._mp_face:
            self._mp_face.close()
        if self._mp_pose:
            self._mp_pose.close()
