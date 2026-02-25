"""Voice playback service for attendance confirmation."""

import logging
import random
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import QUrl
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput

LOGGER = logging.getLogger(__name__)


class VoicePlayer:
    """Plays a random MP3 voice clip on successful badge scans."""

    def __init__(self, voices_dir: Path, enabled: bool = True, volume: float = 1.0):
        self.voices_dir = voices_dir
        self.enabled = enabled
        self._volume = max(0.0, min(1.0, volume))
        self.voice_files: list[Path] = []
        self._last_played: Optional[Path] = None

        self._player = QMediaPlayer()
        self._audio_output = QAudioOutput()
        self._audio_output.setVolume(self._volume)
        self._player.setAudioOutput(self._audio_output)
        self._player.errorOccurred.connect(self._on_error)

        self._load_voice_files()
        self._prewarm()

        LOGGER.info(
            "VoicePlayer initialized: enabled=%s, volume=%.2f, files=%d",
            self.enabled, self._volume, len(self.voice_files),
        )

    def _load_voice_files(self) -> None:
        if not self.voices_dir.exists():
            LOGGER.warning("Voices directory not found: %s", self.voices_dir)
            return
        self.voice_files = sorted(self.voices_dir.glob("*.mp3"))
        if not self.voice_files:
            LOGGER.warning("No MP3 files found in: %s", self.voices_dir)

    def _prewarm(self) -> None:
        """Pre-warm the audio pipeline so the first real play has no cold-start delay."""
        if not self.voice_files:
            return
        # Temporarily mute, load first file, start+stop to init codec and audio device
        self._audio_output.setVolume(0.0)
        self._player.setSource(QUrl.fromLocalFile(str(self.voice_files[0].resolve())))
        self._player.play()
        self._player.stop()
        # Restore volume
        self._audio_output.setVolume(self._volume)
        LOGGER.debug("Audio pipeline pre-warmed")

    def _pick_random(self) -> Path:
        """Pick a random voice file, avoiding consecutive repeats when possible."""
        if len(self.voice_files) == 1:
            return self.voice_files[0]

        candidates = [f for f in self.voice_files if f != self._last_played]
        return random.choice(candidates)

    def play_random(self) -> None:
        if not self.enabled or not self.voice_files:
            return

        voice_file = self._pick_random()
        self._last_played = voice_file

        if self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self._player.stop()

        self._player.setSource(QUrl.fromLocalFile(str(voice_file.resolve())))
        self._player.play()
        LOGGER.debug("Playing voice: %s", voice_file.name)

    def is_playing(self) -> bool:
        """Return True if a voice clip is currently playing."""
        return self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState

    def _on_error(self, error, error_string: str) -> None:
        LOGGER.error("Voice playback error: %s (%s)", error_string, error)
