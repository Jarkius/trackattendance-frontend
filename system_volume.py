"""Windows system (master/speaker) volume control.

This is a different volume knob from audio.py's VoicePlayer/greeting_player
QAudioOutput.setVolume(): that one is an *app-relative* gain (0.0-1.0 of
whatever the OS currently allows), so setting it to 100% still can't exceed
Windows' own master volume. If a laptop's system volume is sitting at 36%
(the actual default one station shipped with), the app's own 100% is capped
there and sounds quiet no matter what our slider says. This module raises
the OS-level ceiling itself.

Windows-only (pycaw wraps the Core Audio API, no non-Windows equivalent
is needed since this app only ships for Windows).
"""

from __future__ import annotations

import logging

LOGGER = logging.getLogger(__name__)


def set_system_volume_max() -> dict:
    """Set Windows' master speaker volume to 100% and unmute it.

    Returns {"ok": True, "previous_volume": float, "was_muted": bool} on
    success, or {"ok": False, "message": str} if pycaw/Core Audio is
    unavailable (e.g. running on a non-Windows dev machine, or a headless
    CI environment with no audio device at all).
    """
    try:
        from pycaw.pycaw import AudioUtilities
    except ImportError as exc:
        LOGGER.warning("[SystemVolume] pycaw not available: %s", exc)
        return {"ok": False, "message": "pycaw not installed"}

    try:
        speakers = AudioUtilities.GetSpeakers()
        endpoint_volume = speakers.EndpointVolume
        previous_volume = endpoint_volume.GetMasterVolumeLevelScalar()
        was_muted = bool(endpoint_volume.GetMute())

        endpoint_volume.SetMasterVolumeLevelScalar(1.0, None)
        # Always unmute unconditionally rather than branching on was_muted --
        # GetMute() was observed reverting its own readback (1 -> 0) within
        # ~0.5s of being set on this machine, so it's not reliable enough to
        # gate a conditional call on. SetMute(0, ...) on an already-unmuted
        # device is a harmless no-op.
        endpoint_volume.SetMute(0, None)

        LOGGER.info(
            "[SystemVolume] Set to 100%% (was %.0f%%%s)",
            previous_volume * 100,
            ", was muted" if was_muted else "",
        )
        return {"ok": True, "previous_volume": previous_volume, "was_muted": was_muted}
    except Exception as exc:  # noqa: BLE001 - Core Audio/COM errors vary by machine
        LOGGER.warning("[SystemVolume] Failed to set system volume: %s", exc)
        return {"ok": False, "message": str(exc)}


__all__ = ["set_system_volume_max"]
