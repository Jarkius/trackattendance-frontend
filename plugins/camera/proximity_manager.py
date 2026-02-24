"""
Proximity greeting manager — integration glue between camera detection and voice greeting.

When a person is detected near the kiosk, plays a voice greeting prompting them
to scan their badge. Camera does NOT scan barcodes — badge scanning remains USB-only.
"""

import logging
import threading
import time
from typing import Optional, Tuple

LOGGER = logging.getLogger(__name__)


class ProximityGreetingManager:
    """Manage camera-based proximity detection and voice greeting playback."""

    def __init__(
        self,
        voice_player,
        camera_id: int = 0,
        cooldown: float = 10.0,
        resolution: Tuple[int, int] = (1280, 720),
    ):
        self._voice_player = voice_player
        self._camera_id = camera_id
        self._cooldown = cooldown
        self._resolution = resolution

        self._cap = None  # cv2.VideoCapture
        self._detector = None  # ProximityDetector
        self._thread: Optional[threading.Thread] = None
        self._running = False

    def start(self) -> bool:
        """Late-import deps, open camera, start daemon thread. Returns False on failure."""
        try:
            import cv2
            from plugins.camera.proximity_detector import ProximityDetector
        except ImportError as exc:
            LOGGER.warning("[Proximity] Missing dependency: %s", exc)
            return False

        try:
            self._cap = cv2.VideoCapture(self._camera_id)
            if not self._cap.isOpened():
                LOGGER.warning("[Proximity] Cannot open camera %d", self._camera_id)
                return False

            self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self._resolution[0])
            self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self._resolution[1])

            # Verify we can actually read a frame
            ret, _ = self._cap.read()
            if not ret:
                LOGGER.warning("[Proximity] Camera %d opened but cannot read frames", self._camera_id)
                self._cap.release()
                self._cap = None
                return False

            self._detector = ProximityDetector(cooldown=self._cooldown)
            self._detector.add_detection_callback(self._on_person_detected)

            self._running = True
            self._thread = threading.Thread(
                target=self._camera_loop,
                daemon=True,
                name="proximity-camera",
            )
            self._thread.start()
            return True

        except Exception as exc:
            LOGGER.warning("[Proximity] Start failed: %s", exc)
            if self._cap is not None:
                self._cap.release()
                self._cap = None
            return False

    def _on_person_detected(self) -> None:
        """Callback from ProximityDetector — play greeting via VoicePlayer."""
        method = self._detector.detection_method if self._detector else "unknown"
        LOGGER.info("[Proximity] Person detected (%s) — playing greeting", method)
        if self._voice_player:
            self._voice_player.play_random()

    def _camera_loop(self) -> None:
        """Read frames and feed to ProximityDetector (runs in daemon thread)."""
        import cv2

        while self._running:
            if self._cap is None or not self._cap.isOpened():
                LOGGER.warning("[Proximity] Camera lost, stopping loop")
                break

            ret, frame = self._cap.read()
            if not ret:
                time.sleep(0.1)
                continue

            try:
                self._detector.process_frame(frame)
            except Exception as exc:
                LOGGER.error("[Proximity] Frame processing error: %s", exc)

            # ~15 FPS is plenty for proximity detection
            time.sleep(0.066)

    def stop(self) -> None:
        """Stop thread, release camera and MediaPipe resources."""
        self._running = False

        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None

        if self._cap is not None:
            self._cap.release()
            self._cap = None

        if self._detector is not None:
            self._detector.close()
            self._detector = None

        LOGGER.info("[Proximity] Stopped")
