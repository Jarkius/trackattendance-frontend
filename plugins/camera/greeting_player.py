"""Greeting audio player for proximity detection.

Generates Thai/English greeting MP3s via edge-tts on first run,
then plays them randomly when a person is detected near the kiosk.
Fully self-contained — does not depend on the main app's VoicePlayer.
"""

import asyncio
import logging
import random
import subprocess
import sys
from pathlib import Path
from typing import Optional

LOGGER = logging.getLogger(__name__)

# Greeting definitions: (filename, text, voice)
# Greeting definitions: (filename, text, voice)
# - text+voice entries are generated via edge-tts if missing
# - entries with text=None are pre-recorded files (skipped by generator)
GREETINGS = [
    ("greeting_th.mp3", "สวัสดีค่ะ กรุณาสแกนบัตรด้วยค่ะ", "th-TH-PremwadeeNeural"),
    ("greeting_en.mp3", "Welcome! Please scan your badge.", "en-US-JennyNeural"),
    ("greeting_en_th.mp3", None, None),  # Pre-recorded bilingual greeting
]

GREETINGS_DIR = Path(__file__).resolve().parent / "greetings"


class GreetingPlayer:
    """Generates and plays proximity greeting audio via edge-tts + QMediaPlayer."""

    def __init__(self, volume: float = 1.0):
        self._volume = max(0.0, min(1.0, volume))
        self._player = None  # QMediaPlayer, created lazily
        self._audio_output = None  # QAudioOutput
        self._greeting_files: list[Path] = []
        self._last_played: Optional[Path] = None

    def start(self) -> bool:
        """Generate greetings if needed, init QMediaPlayer. Returns True on success."""
        try:
            from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
            from PyQt6.QtCore import QUrl

            self._QUrl = QUrl  # stash for play_random
            self._player = QMediaPlayer()
            self._audio_output = QAudioOutput()
            self._audio_output.setVolume(self._volume)
            self._player.setAudioOutput(self._audio_output)
        except ImportError:
            LOGGER.warning("[Greeting] PyQt6.QtMultimedia not available")
            return False

        # Ensure greetings dir exists
        GREETINGS_DIR.mkdir(parents=True, exist_ok=True)

        # Check which audio files already exist
        missing = []
        for filename, text, voice in GREETINGS:
            audio_path = GREETINGS_DIR / filename
            if audio_path.exists() and audio_path.stat().st_size > 0:
                self._greeting_files.append(audio_path)
            elif text is not None:
                # Only queue for generation if it has text+voice (not pre-recorded)
                missing.append((filename, text, voice))
            else:
                LOGGER.warning("[Greeting] Pre-recorded file missing: %s", filename)

        # Generate missing greetings via edge-tts
        if missing:
            self._generate_greetings(missing)

        if not self._greeting_files:
            LOGGER.warning("[Greeting] No greeting MP3s available")
            return False

        LOGGER.info("[Greeting] Ready with %d greeting(s)", len(self._greeting_files))
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

    def play_random(self) -> None:
        """Play a random greeting MP3."""
        if not self._player or not self._greeting_files:
            return

        # Pick random, avoid consecutive repeat
        if len(self._greeting_files) > 1:
            candidates = [f for f in self._greeting_files if f != self._last_played]
            choice = random.choice(candidates)
        else:
            choice = self._greeting_files[0]

        self._last_played = choice

        from PyQt6.QtMultimedia import QMediaPlayer

        if self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self._player.stop()

        self._player.setSource(self._QUrl.fromLocalFile(str(choice.resolve())))
        self._player.play()
        LOGGER.debug("[Greeting] Playing: %s", choice.name)

    def stop(self) -> None:
        """Stop playback."""
        if self._player:
            self._player.stop()
