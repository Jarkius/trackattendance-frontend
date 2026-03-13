"""
Person proximity detection using YuNet DNN face detector + upper body Haar cascade.
Falls back to frontal face Haar cascade, then motion detection if models unavailable.

Detection chain per frame:
  1. YuNet face (primary — fast DNN, handles angles)
  2. Upper body Haar cascade (catches torso when face not visible)
  3. Frontal face Haar cascade (fallback if YuNet unavailable)
  4. Motion detection (last resort — frame differencing)

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
    Person proximity detection using YuNet DNN face detector.
    Falls back to Haar cascade or motion detection if unavailable.

    Detection chain (best → worst):
    1. YuNet face — modern DNN face detector (2021), ~1-2ms on CPU, handles angles
    2. Upper body Haar — detects torso when face not visible (too tall/short/turned away)
    3. Frontal face Haar — classic face detector fallback (if YuNet unavailable)
    4. Motion fallback — frame differencing, catches movement only

    A person is "detected" when a face/body is found or motion exceeds threshold.
    """

    def __init__(self, sensitivity: int = 5000, cooldown: float = 5.0,
                 min_face_confidence: float = 0.5, min_pose_confidence: float = 0.5,
                 skip_frames: int = 2, absence_threshold: float = 3.0,
                 confirm_frames: int = 3, min_size_pct: float = 0.20,
                 haar_min_neighbors: int = 5, detection_scale: float = 1.0):
        self.sensitivity = sensitivity  # for motion fallback
        self.haar_min_neighbors = haar_min_neighbors  # Haar cascade strictness
        self.cooldown = cooldown  # minimum seconds between greetings
        self.min_face_confidence = min_face_confidence
        self.min_pose_confidence = min_pose_confidence
        self.min_size_pct = min_size_pct  # minimum detection size as fraction of frame
        self.skip_frames = skip_frames  # process every Nth frame to save CPU
        self.absence_threshold = absence_threshold  # seconds with no detection before state → empty
        self.confirm_frames = confirm_frames  # consecutive detections required before greeting
        self._detection_scale = max(0.25, min(1.0, detection_scale))  # downscale factor for detection
        self._frame_count = 0
        self._last_detection_time = 0
        self._consecutive_detections = 0  # count of consecutive frames with person
        self._background_frame: Optional[np.ndarray] = None
        self._detection_callbacks: List[Callable[[], None]] = []
        self._last_detection_method: Optional[str] = None
        self._last_faces: Optional[list] = None  # face rectangles for overlay

        # Detection backends
        self._yunet = None
        self._use_yunet = False
        self._haar_upperbody = None  # upper body cascade (secondary when face not visible)
        self._haar_cascade = None    # frontal face cascade (fallback if YuNet unavailable)

        # Presence state: "empty" or "present"
        # Greeting only fires on transition from empty → present
        self._presence_state: str = "empty"
        self._last_person_seen_time: float = 0.0

        # Model files directory — bundled inside exe or alongside this script
        if getattr(sys, 'frozen', False):
            models_dir = os.path.join(sys._MEIPASS, 'plugins', 'camera', 'models')
        else:
            models_dir = os.path.join(os.path.dirname(__file__), 'models')

        # Try YuNet DNN face detector (primary — modern, fast, accurate)
        yunet_model = os.path.join(models_dir, 'face_detection_yunet_2023mar.onnx')
        if cv2 is not None and os.path.exists(yunet_model):
            try:
                self._yunet = cv2.FaceDetectorYN.create(
                    model=yunet_model,
                    config="",
                    input_size=(320, 320),  # will be set per-frame
                    score_threshold=self.min_face_confidence,
                    nms_threshold=0.3,
                    top_k=5000,
                )
                self._use_yunet = True
                LOGGER.info("[Proximity] YuNet DNN face detector active (min_size_pct=%.2f)", self.min_size_pct)
            except Exception as e:
                LOGGER.warning("[Proximity] YuNet init failed (%s), trying Haar cascade", e)

        # Upper body Haar cascade — secondary detector for when face isn't visible
        # (person too tall/short for camera, turned away, looking down at badge)
        # Loaded alongside YuNet as a complement, not a replacement
        if cv2 is not None:
            try:
                upperbody_path = self._find_haar_cascade('haarcascade_upperbody.xml')
                if upperbody_path:
                    self._haar_upperbody = cv2.CascadeClassifier(upperbody_path)
                    if self._haar_upperbody.empty():
                        self._haar_upperbody = None
                    else:
                        LOGGER.info("[Proximity] Upper body Haar cascade loaded (secondary detector)")
            except Exception as e:
                LOGGER.warning("[Proximity] Upper body cascade init failed (%s)", e)

        # Fallback: OpenCV Haar cascade face detection (ships with cv2, no extra files)
        if not self._use_yunet:
            try:
                cascade_path = self._find_haar_cascade('haarcascade_frontalface_default.xml')
                if cascade_path:
                    self._haar_cascade = cv2.CascadeClassifier(cascade_path)
                    if self._haar_cascade.empty():
                        self._haar_cascade = None
                        LOGGER.warning("[Proximity] Haar cascade XML found but failed to load")
                    else:
                        LOGGER.info("[Proximity] OpenCV Haar cascade active (min_size_pct=%.2f, path=%s)", self.min_size_pct, cascade_path)
                else:
                    LOGGER.warning("[Proximity] Haar cascade XML not found")
            except Exception as e:
                LOGGER.warning("[Proximity] Haar cascade init failed (%s)", e)

    @property
    def detection_method(self) -> str:
        """Return which detection method was used last."""
        return self._last_detection_method or "none"

    @property
    def last_faces(self) -> Optional[list]:
        """Last detected face rectangles [[x, y, w, h], ...] for overlay drawing."""
        return self._last_faces

    def add_detection_callback(self, callback: Callable[[], None]):
        """Add callback for proximity detection."""
        self._detection_callbacks.append(callback)

    @staticmethod
    def _find_haar_cascade(filename: str) -> Optional[str]:
        """Find a Haar cascade XML file from OpenCV's bundled data directories."""
        candidates = []
        if hasattr(cv2, 'data') and hasattr(cv2.data, 'haarcascades'):
            candidates.append(cv2.data.haarcascades + filename)
        cv2_dir = os.path.dirname(cv2.__file__)
        candidates.append(os.path.join(cv2_dir, 'data', filename))
        if getattr(sys, 'frozen', False):
            meipass = getattr(sys, '_MEIPASS', '')
            candidates.append(os.path.join(meipass, 'cv2', 'data', filename))
        for candidate in candidates:
            if os.path.exists(candidate):
                return candidate
        return None

    def _detect_yunet_face(self, frame: np.ndarray) -> bool:
        """Detect face using OpenCV YuNet DNN detector.

        Stores face rectangles in self._last_faces for overlay rendering.
        YuNet returns Nx15 array: [x, y, w, h, ...landmarks..., score].
        """
        h, w = frame.shape[:2]
        self._yunet.setInputSize((w, h))
        _, faces = self._yunet.detect(frame)
        self._last_faces = None

        if faces is None:
            return False

        min_px = int(w * self.min_size_pct)
        valid = []
        for face in faces:
            fw = int(face[2])
            if fw >= min_px:
                valid.append([int(face[0]), int(face[1]), int(face[2]), int(face[3])])

        if valid:
            self._last_faces = valid
            return True
        return False

    def _detect_haar_face(self, frame: np.ndarray) -> bool:
        """Detect face using OpenCV Haar cascade.

        Stores face rectangles in self._last_faces for overlay rendering.
        """
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        frame_w = frame.shape[1]
        min_px = int(frame_w * self.min_size_pct)

        faces = self._haar_cascade.detectMultiScale(
            gray,
            scaleFactor=1.1,
            minNeighbors=self.haar_min_neighbors,
            minSize=(min_px, min_px),
        )

        self._last_faces = None
        if len(faces) > 0:
            self._last_faces = [[int(x), int(y), int(w), int(h)] for (x, y, w, h) in faces]
            return True
        return False

    def _detect_upperbody(self, frame: np.ndarray) -> bool:
        """Detect upper body/torso using Haar cascade.

        Used as secondary check when YuNet finds no face — catches people
        whose face isn't visible (too tall/short, turned away, looking down).
        Uses relaxed min_neighbors (3) since upper body is a broader pattern.
        Stores body rectangles in self._last_faces for overlay rendering.
        """
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        frame_w = frame.shape[1]
        # Use same min_size_pct as face — upper body is larger so this
        # naturally requires closer proximity than face detection
        min_px = int(frame_w * self.min_size_pct)

        bodies = self._haar_upperbody.detectMultiScale(
            gray,
            scaleFactor=1.05,
            minNeighbors=self.haar_min_neighbors,
            minSize=(min_px, min_px),
        )

        self._last_faces = None
        if len(bodies) > 0:
            self._last_faces = [[int(x), int(y), int(w), int(h)] for (x, y, w, h) in bodies]
            return True
        return False

    def _detect_motion(self, frame: np.ndarray, precomputed_gray=None) -> bool:
        """Fallback: simple motion detection via frame differencing.

        Also applies min_size_pct filter — the largest motion contour's
        bounding-box width must fill at least min_size_pct of the frame.
        Accepts optional precomputed_gray to avoid redundant grayscale conversion.
        """
        if precomputed_gray is not None:
            gray = precomputed_gray
        else:
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
        self._last_faces = None

        frame_w = frame.shape[1]
        for contour in contours:
            if cv2.contourArea(contour) > self.sensitivity:
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

        Detection chain: YuNet face → Upper body Haar → Frontal face Haar → Motion.
        """
        current_time = time.time()

        # Skip frames to save CPU (process every Nth frame)
        self._frame_count += 1
        if self._frame_count % (self.skip_frames + 1) != 0:
            return False

        # Downscale frame for detection to save CPU (display uses original)
        if self._detection_scale < 1.0:
            det_h = int(frame.shape[0] * self._detection_scale)
            det_w = int(frame.shape[1] * self._detection_scale)
            det_frame = cv2.resize(frame, (det_w, det_h))
        else:
            det_frame = frame

        # Detect person in this frame
        # Chain: YuNet face → upper body → frontal face Haar → motion
        person_in_frame = False
        self._last_faces = None

        if self._use_yunet:
            if self._detect_yunet_face(det_frame):
                person_in_frame = True
                self._last_detection_method = "yunet"
            elif self._haar_upperbody is not None:
                # Face not visible — try upper body (tall/short person, turned away)
                if self._detect_upperbody(det_frame):
                    person_in_frame = True
                    self._last_detection_method = "upperbody"
        elif self._haar_cascade is not None:
            if self._detect_haar_face(det_frame):
                person_in_frame = True
                self._last_detection_method = "haar"
            elif self._haar_upperbody is not None:
                if self._detect_upperbody(det_frame):
                    person_in_frame = True
                    self._last_detection_method = "upperbody"

        # Scale face rectangles back to original resolution for overlay
        if self._last_faces and self._detection_scale < 1.0:
            inv = 1.0 / self._detection_scale
            self._last_faces = [
                [int(x * inv), int(y * inv), int(w * inv), int(h * inv)]
                for (x, y, w, h) in self._last_faces
            ]

        # Motion fallback — only used when no face/body detector is available.
        # When real detectors exist, motion causes too many false greetings
        # (walking past at 2m+ creates large motion blobs that pass size filter).
        has_real_detector = self._use_yunet or self._haar_cascade is not None
        if not person_in_frame and not has_real_detector:
            if self._detect_motion(det_frame):
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
                LOGGER.info("[Proximity] State: empty → present (%s, %d consecutive frames)",
                            self._last_detection_method, self._consecutive_detections)

                # Enforce minimum gap between greetings (cooldown)
                since_last_greet = current_time - self._last_detection_time
                if since_last_greet < self.cooldown:
                    remaining = self.cooldown - since_last_greet
                    LOGGER.info("[Proximity] Greeting suppressed by cooldown (%.0fs remaining)", remaining)
                    return False

                # Greet the newcomer
                self._last_detection_time = current_time
                LOGGER.info("[Proximity] Greeting fired — next allowed in %.0fs", self.cooldown)
                for callback in self._detection_callbacks:
                    try:
                        callback()
                    except Exception as e:
                        LOGGER.error("[Proximity] Detection callback error: %s", e)
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
                LOGGER.info("[Proximity] State: present → empty (absent %.1fs)", elapsed)

        return False

    def reset(self):
        """Reset detector state."""
        self._background_frame = None
        self._last_detection_time = 0
        self._frame_count = 0
        self._last_detection_method = None
        self._last_faces = None

    def close(self):
        """Release resources."""
        pass
