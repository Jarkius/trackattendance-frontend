"""Windows system (master/speaker) volume control.

This is a different volume knob from audio.py's VoicePlayer/greeting_player
QAudioOutput.setVolume(): that one is an *app-relative* gain (0.0-1.0 of
whatever the OS currently allows), so setting it to 100% still can't exceed
Windows' own master volume. If a laptop's system volume is sitting at 36%
(the actual default one station shipped with), the app's own 100% is capped
there and sounds quiet no matter what our slider says. This module lets the
admin Volume slider drive the OS-level volume directly instead.

Windows-only (pycaw wraps the Core Audio API, no non-Windows equivalent
is needed since this app only ships for Windows).
"""

from __future__ import annotations

import logging

LOGGER = logging.getLogger(__name__)


def set_system_volume_scalar(volume: float) -> dict:
    """Set Windows' master speaker volume directly (0.0-1.0), unmuting it.

    This is what the admin Volume slider now drives: dragging it to 60%
    sets the OS system volume to 60% (not just this app's own internal
    gain), so the slider is the single real "how loud is this station"
    control instead of being silently capped by whatever the OS volume
    happened to be left at.

    Returns {"ok": True, "previous_volume": float} on success, or
    {"ok": False, "message": str} if pycaw/Core Audio is unavailable
    (non-Windows dev machine, headless CI, no audio device, or any other
    Core Audio/COM error -- the real exception message is returned so a
    genuinely broken audio device on a laptop is debuggable, not masked).
    """
    try:
        from pycaw.pycaw import AudioUtilities
    except ImportError as exc:
        LOGGER.warning("[SystemVolume] pycaw not available: %s", exc)
        return {"ok": False, "message": str(exc)}

    volume = max(0.0, min(1.0, volume))
    try:
        endpoint_volume = AudioUtilities.GetSpeakers().EndpointVolume
        previous_volume = endpoint_volume.GetMasterVolumeLevelScalar()
        endpoint_volume.SetMasterVolumeLevelScalar(volume, None)
        # Always unmute unconditionally rather than branching on GetMute() --
        # GetMute() was observed reverting its own readback (1 -> 0) within
        # ~0.5s of being set on a real machine, so it's not reliable enough
        # to gate a conditional call on. SetMute(0, ...) on an
        # already-unmuted device is a harmless no-op.
        endpoint_volume.SetMute(0, None)
        LOGGER.info("[SystemVolume] Set to %.0f%% (was %.0f%%)", volume * 100, previous_volume * 100)
        return {"ok": True, "previous_volume": previous_volume}
    except Exception as exc:  # noqa: BLE001 - Core Audio/COM errors vary by machine
        LOGGER.warning("[SystemVolume] Failed to set system volume: %s", exc)
        return {"ok": False, "message": str(exc)}


def set_system_volume_max() -> dict:
    """Set Windows' master speaker volume to 100% and unmute it.

    Used on app startup (see main.py's load_saved_settings()) to open the
    OS-level ceiling fully before applying the persisted slider value as
    this app's own gain -- keeps a fresh launch's actual loudness matching
    whatever the slider was last set to, without needing to also persist
    and restore a separate OS-volume value across restarts.
    """
    return set_system_volume_scalar(1.0)


__all__ = ["set_system_volume_scalar", "set_system_volume_max"]
