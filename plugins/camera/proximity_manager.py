"""
Proximity greeting manager — integration glue between camera detection,
greeting TTS, and camera preview overlay.

When a person is detected near the kiosk, plays a Thai/English voice greeting
prompting them to scan their badge. A small floating camera preview shows in
the top-right corner. Camera does NOT scan barcodes — badge scanning remains
USB-only. Fully self-contained plugin — no dependency on main app's VoicePlayer.
"""

import logging
import threading
import time
from typing import Optional, Tuple

LOGGER = logging.getLogger(__name__)


class ProximityGreetingManager:
    """Manage camera-based proximity detection, greeting audio, and camera preview."""

    def __init__(
        self,
        parent_window=None,
        camera_id: int = 0,
        cooldown: float = 10.0,
        resolution: Tuple[int, int] = (1280, 720),
        greeting_volume: float = 1.0,
        scan_busy_seconds: float = 30.0,
        voice_player=None,
    ):
        self._parent_window = parent_window
        self._camera_id = camera_id
        self._cooldown = cooldown
        self._resolution = resolution
        self._greeting_volume = greeting_volume
        self._scan_busy_seconds = scan_busy_seconds
        self._voice_player = voice_player  # main app's VoicePlayer, to avoid audio overlap

        self._cap = None  # cv2.VideoCapture
        self._detector = None  # ProximityDetector
        self._greeting_player = None  # GreetingPlayer
        self._overlay = None  # CameraOverlay
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._busy_until: float = 0.0  # suppress greetings while queue is active

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

            # Initialize greeting player (edge-tts generated audio)
            try:
                from plugins.camera.greeting_player import GreetingPlayer
                self._greeting_player = GreetingPlayer(volume=self._greeting_volume)
                if not self._greeting_player.start():
                    LOGGER.warning("[Proximity] Greeting player failed to start, greetings will be silent")
                    self._greeting_player = None
            except Exception as exc:
                LOGGER.warning("[Proximity] Greeting player init failed: %s", exc)
                self._greeting_player = None

            # Initialize camera overlay (floating preview)
            if self._parent_window is not None:
                try:
                    from plugins.camera.camera_overlay import CameraOverlay
                    self._overlay = CameraOverlay(self._parent_window)
                    self._overlay.show_overlay()
                except Exception as exc:
                    LOGGER.warning("[Proximity] Camera overlay init failed: %s", exc)
                    self._overlay = None

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

    def notify_scan_activity(self) -> None:
        """Called when a badge is scanned. Suppresses greetings while queue is active."""
        self._busy_until = time.time() + self._scan_busy_seconds
        LOGGER.debug("[Proximity] Scan activity — greetings suppressed for %.0fs", self._scan_busy_seconds)

    def _is_scan_voice_playing(self) -> bool:
        """Check if the main app's scan voice is currently playing."""
        if self._voice_player is None:
            return False
        try:
            from PyQt6.QtMultimedia import QMediaPlayer
            return self._voice_player._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState
        except Exception:
            return False

    def _on_person_detected(self) -> None:
        """Callback from ProximityDetector — play greeting (unless busy or voice playing)."""
        # Suppress greeting while scans are happening (queue is active)
        if time.time() < self._busy_until:
            LOGGER.debug("[Proximity] Person detected but suppressed (queue active)")
            return

        # Don't overlap with scan "thank you" voice
        if self._is_scan_voice_playing():
            LOGGER.debug("[Proximity] Person detected but scan voice is playing, skipping")
            return

        method = self._detector.detection_method if self._detector else "unknown"
        LOGGER.info("[Proximity] Person detected (%s) — playing greeting", method)
        if self._greeting_player:
            self._greeting_player.play_random()

    def _camera_loop(self) -> None:
        """Read frames and feed to ProximityDetector + overlay (runs in daemon thread)."""
        import cv2

        overlay_interval = 0.2  # ~5 FPS for preview (saves CPU + avoids GC pressure)
        last_overlay_time = 0.0

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

            # Feed frame to overlay at ~5 FPS (throttled to reduce GC pressure)
            now = time.time()
            if self._overlay is not None and (now - last_overlay_time) >= overlay_interval:
                last_overlay_time = now
                try:
                    self._overlay.update_frame(frame)
                except Exception:
                    pass

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

        if self._overlay is not None:
            self._overlay.hide_overlay()
            self._overlay = None

        if self._greeting_player is not None:
            self._greeting_player.stop()
            self._greeting_player = None

        LOGGER.info("[Proximity] Stopped")
