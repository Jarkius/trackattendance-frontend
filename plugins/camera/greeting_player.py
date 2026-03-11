"""Greeting audio player for proximity detection.

Generates Thai/English greeting MP3s via edge-tts on first run,
then plays them randomly when a person is detected near the kiosk.
Fully self-contained — does not depend on the main app's VoicePlayer.

Thread-safe: play_random() can be called from any thread — actual
QMediaPlayer operations are marshalled to the Qt main thread.

Pre-loads the next greeting after each play to eliminate load delay.
"""

import logging
import random
import subprocess
import sys
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import QObject, QMetaObject, Qt as QtConst, pyqtSlot

LOGGER = logging.getLogger(__name__)

def _greetings_dir() -> Path:
    """Resolve greetings directory with fallback chain.

    Frozen exe: greetings/ next to .exe (override) → bundled in _MEIPASS (fallback)
    Dev mode:   plugins/camera/greetings/ (as-is)
    """
    if getattr(sys, 'frozen', False):
        # Check next to .exe first (user can drop custom mp3s here)
        exe_dir = Path(sys.executable).parent / "greetings"
        if exe_dir.is_dir() and any(exe_dir.glob("*.mp3")):
            return exe_dir
        # Fall back to bundled greetings inside exe
        return Path(sys._MEIPASS) / "plugins" / "camera" / "greetings"
    return Path(__file__).resolve().parent / "greetings"

GREETINGS_DIR = _greetings_dir()


class GreetingPlayer(QObject):
    """Generates and plays proximity greeting audio via edge-tts + QMediaPlayer.

    Thread-safe: play_random() schedules playback on the Qt main thread.
    Pre-loads the next greeting so playback is instant on detection.
    """

    def __init__(self, volume: float = 1.0):
        super().__init__()
        self._volume = max(0.0, min(1.0, volume))
        self._player = None  # QMediaPlayer, created lazily
        self._audio_output = None  # QAudioOutput
        self._greeting_files: list[Path] = []
        self._last_played: Optional[Path] = None
        self._pending_file: Optional[Path] = None
        self._preloaded: bool = False  # True when next greeting is already loaded

    def start(self) -> bool:
        """Generate greetings if needed, init QMediaPlayer. Returns True on success."""
        try:
            from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
            from PyQt6.QtCore import QUrl

            self._QUrl = QUrl
            self._QMediaPlayer = QMediaPlayer
            self._player = QMediaPlayer()
            self._audio_output = QAudioOutput()
            self._audio_output.setVolume(self._volume)
            self._player.setAudioOutput(self._audio_output)
            # Log playback errors and state changes
            self._player.errorOccurred.connect(self._on_error)
            self._player.mediaStatusChanged.connect(self._on_media_status)
        except ImportError:
            LOGGER.warning("[Greeting] PyQt6.QtMultimedia not available")
            return False

        # Ensure greetings dir exists
        GREETINGS_DIR.mkdir(parents=True, exist_ok=True)

        # If no mp3 files exist, generate defaults via edge-tts
        existing = sorted(f for f in GREETINGS_DIR.glob("*.mp3") if f.stat().st_size > 0)
        if not existing:
            self._generate_greetings([
                ("greeting_th.mp3", "สวัสดีค่ะ กรุณาสแกนบัตรด้วยค่ะ", "th-TH-PremwadeeNeural"),
                ("greeting_en.mp3", "Welcome! Please scan your badge.", "en-US-JennyNeural"),
            ])
            existing = sorted(f for f in GREETINGS_DIR.glob("*.mp3") if f.stat().st_size > 0)

        self._greeting_files = existing

        if not self._greeting_files:
            LOGGER.warning("[Greeting] No greeting MP3s available")
            return False

        # Log audio output device for debugging
        dev = self._audio_output.device()
        LOGGER.info("[Greeting] Audio output: %s (volume=%.0f%%)", dev.description(), self._volume * 100)
        LOGGER.info("[Greeting] Ready with %d greeting(s)", len(self._greeting_files))

        # Pre-load first greeting so first detection plays instantly
        self._preload_next()
        return True

    def _generate_greetings(self, missing: list) -> None:
        """Generate missing greeting MP3s via edge-tts CLI subprocess."""
        for filename, text, voice in missing:
            mp3_path = GREETINGS_DIR / filename
            try:
                result = subprocess.run(
                    [
                        sys.executable, "-m", "edge_tts",
                        "--voice", voice,
                        "--text", text,
                        "--write-media", str(mp3_path),
                    ],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                if result.returncode == 0 and mp3_path.exists() and mp3_path.stat().st_size > 0:
                    self._greeting_files.append(mp3_path)
                    LOGGER.info("[Greeting] Generated: %s", filename)
                else:
                    LOGGER.warning(
                        "[Greeting] edge-tts failed for %s: %s",
                        filename, result.stderr.strip() or "unknown error",
                    )
            except FileNotFoundError:
                LOGGER.warning("[Greeting] edge-tts not installed, skipping generation")
                return
            except subprocess.TimeoutExpired:
                LOGGER.warning("[Greeting] edge-tts timed out for %s", filename)
            except Exception as exc:
                LOGGER.warning("[Greeting] Generation failed for %s: %s", filename, exc)

    def _pick_next(self) -> Path:
        """Pick a random greeting, avoiding consecutive repeats."""
        if len(self._greeting_files) > 1:
            candidates = [f for f in self._greeting_files if f != self._last_played]
            return random.choice(candidates)
        return self._greeting_files[0]

    def _preload_next(self) -> None:
        """Pre-load the next random greeting into QMediaPlayer so play() is instant."""
        if not self._player or not self._greeting_files:
            return
        choice = self._pick_next()
        self._last_played = choice
        self._pending_file = choice
        self._player.setSource(self._QUrl.fromLocalFile(str(choice.resolve())))
        self._preloaded = True
        LOGGER.debug("[Greeting] Pre-loaded: %s", choice.name)

    def play_random(self) -> None:
        """Play the pre-loaded greeting instantly. Schedules on main thread.

        Safe to call from any thread (camera thread, worker thread, etc.).
        """
        if not self._player or not self._greeting_files:
            return

        # Marshal to main thread — QMediaPlayer must only be touched there
        QMetaObject.invokeMethod(
            self, "_play_on_main_thread", QtConst.ConnectionType.QueuedConnection
        )

    @pyqtSlot()
    def _play_on_main_thread(self) -> None:
        """Play pre-loaded greeting, then pre-load the next one."""
        if not self._player:
            return

        from PyQt6.QtMultimedia import QMediaPlayer

        if self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self._player.stop()

        if not self._preloaded:
            # Fallback: load now if nothing pre-loaded
            choice = self._pick_next()
            self._last_played = choice
            self._player.setSource(self._QUrl.fromLocalFile(str(choice.resolve())))
            LOGGER.info("[Greeting] Playing (loaded on-demand): %s", choice.name)
        else:
            LOGGER.info("[Greeting] Playing (pre-loaded): %s", self._pending_file.name if self._pending_file else "?")

        self._player.play()
        self._preloaded = False
        self._pending_file = None

    @pyqtSlot("QMediaPlayer::Error", str)
    def _on_error(self, error, message):
        LOGGER.error("[Greeting] Playback error: %s — %s", error, message)

    @pyqtSlot("QMediaPlayer::MediaStatus")
    def _on_media_status(self, status):
        from PyQt6.QtMultimedia import QMediaPlayer
        status_names = {
            QMediaPlayer.MediaStatus.NoMedia: "NoMedia",
            QMediaPlayer.MediaStatus.LoadingMedia: "Loading",
            QMediaPlayer.MediaStatus.LoadedMedia: "Loaded",
            QMediaPlayer.MediaStatus.BufferedMedia: "Buffered",
            QMediaPlayer.MediaStatus.EndOfMedia: "EndOfMedia",
            QMediaPlayer.MediaStatus.InvalidMedia: "InvalidMedia",
        }
        name = status_names.get(status, str(status))
        if status == QMediaPlayer.MediaStatus.InvalidMedia:
            LOGGER.error("[Greeting] InvalidMedia — file may be corrupt or format unsupported")
        elif status == QMediaPlayer.MediaStatus.EndOfMedia:
            # Greeting finished — pre-load the next one for instant playback
            self._preload_next()
        else:
            LOGGER.debug("[Greeting] Media status: %s", name)

    def stop(self) -> None:
        """Stop playback and disarm pending invocations.

        Must be called from main thread (e.g. during shutdown).
        Clears _pending_file so any queued _play_on_main_thread calls become no-ops.
        """
        self._pending_file = None
        self._preloaded = False
        if self._player:
            self._player.stop()
