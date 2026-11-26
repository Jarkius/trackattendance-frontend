"""Read-only camera/audio device diagnostics for the log.

OpenCV only knows cameras by index, so the admin list says "Camera 1" and the log can't
say which physical device that is. Qt lists the same devices by name, in the same
DirectShow order on Windows, so index N is matched to the N-th name as a best-effort
label. Everything here swallows errors: diagnostics must never break the kiosk.
"""
from __future__ import annotations

import logging
from typing import List

from PyQt6.QtCore import QObject

LOGGER = logging.getLogger(__name__)


def video_input_names() -> List[str]:
    """Names of the video capture devices Windows reports, in enumeration order."""
    try:
        from PyQt6.QtMultimedia import QMediaDevices
        return [d.description() for d in QMediaDevices.videoInputs()]
    except Exception as exc:  # Qt multimedia missing or no QGuiApplication yet
        LOGGER.debug("[Media] Cannot list video inputs: %s", exc)
        return []


def audio_output_names() -> List[str]:
    try:
        from PyQt6.QtMultimedia import QMediaDevices
        return [d.description() for d in QMediaDevices.audioOutputs()]
    except Exception as exc:
        LOGGER.debug("[Media] Cannot list audio outputs: %s", exc)
        return []


def default_audio_output_name() -> str:
    try:
        from PyQt6.QtMultimedia import QMediaDevices
        return QMediaDevices.defaultAudioOutput().description() or "(none)"
    except Exception as exc:
        LOGGER.debug("[Media] Cannot read default audio output: %s", exc)
        return "(unknown)"


def log_media_snapshot(reason: str) -> None:
    """One-shot dump of the devices the OS currently offers."""
    LOGGER.info("[Media] %s: video inputs=%s", reason, video_input_names() or "none")
    LOGGER.info("[Media] %s: audio outputs=%s, default=%s",
                reason, audio_output_names() or "none", default_audio_output_name())


class MediaDeviceWatcher(QObject):
    """Logs camera/speaker hot-plug and default-output changes while the app runs."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._devices = None
        try:
            from PyQt6.QtMultimedia import QMediaDevices
            self._devices = QMediaDevices(self)
            self._devices.videoInputsChanged.connect(
                lambda: LOGGER.info("[Media] Video inputs changed: %s", video_input_names() or "none"))
            self._devices.audioOutputsChanged.connect(
                lambda: LOGGER.info("[Media] Audio outputs changed: %s (default=%s)",
                                    audio_output_names() or "none", default_audio_output_name()))
        except Exception as exc:
            LOGGER.debug("[Media] Device watcher unavailable: %s", exc)
