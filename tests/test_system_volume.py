#!/usr/bin/env python3
"""Unit tests for system_volume.set_system_volume_scalar()/set_system_volume_max().

Mocks pycaw entirely so tests never touch this machine's actual volume
(and pass in CI/non-Windows environments where pycaw isn't installed or
has no real audio endpoint to talk to).

Run: python tests/test_system_volume.py
"""

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import system_volume


class TestSystemVolume(unittest.TestCase):
    def _make_mock_speakers(self, current_volume=0.36, muted=False):
        endpoint_volume = MagicMock()
        endpoint_volume.GetMasterVolumeLevelScalar.return_value = current_volume
        endpoint_volume.GetMute.return_value = 1 if muted else 0
        speakers = MagicMock()
        speakers.EndpointVolume = endpoint_volume
        return speakers, endpoint_volume

    def _patch_pycaw(self, speakers):
        mock_audio_utilities = MagicMock()
        mock_audio_utilities.GetSpeakers.return_value = speakers
        mock_pycaw_module = MagicMock()
        mock_pycaw_module.AudioUtilities = mock_audio_utilities
        return patch.dict(sys.modules, {"pycaw": MagicMock(), "pycaw.pycaw": mock_pycaw_module})

    def test_set_scalar_sets_requested_level_and_unmutes(self):
        speakers, endpoint_volume = self._make_mock_speakers(current_volume=0.36, muted=False)
        with self._patch_pycaw(speakers):
            result = system_volume.set_system_volume_scalar(0.6)

        self.assertTrue(result["ok"])
        self.assertAlmostEqual(result["previous_volume"], 0.36)
        endpoint_volume.SetMasterVolumeLevelScalar.assert_called_once_with(0.6, None)
        endpoint_volume.SetMute.assert_called_once_with(0, None)

    def test_set_scalar_clamps_out_of_range_values(self):
        speakers, endpoint_volume = self._make_mock_speakers()
        with self._patch_pycaw(speakers):
            system_volume.set_system_volume_scalar(1.5)
        endpoint_volume.SetMasterVolumeLevelScalar.assert_called_once_with(1.0, None)

        speakers, endpoint_volume = self._make_mock_speakers()
        with self._patch_pycaw(speakers):
            system_volume.set_system_volume_scalar(-0.5)
        endpoint_volume.SetMasterVolumeLevelScalar.assert_called_once_with(0.0, None)

    def test_unmutes_unconditionally_even_when_getmute_reports_unmuted(self):
        """GetMute() was observed reverting its own readback (1 -> 0) within
        ~0.5s of being set on a real machine, so SetMute(0, ...) must always
        be called rather than gated on a GetMute() read -- verify the no-op
        unmute call still happens even when GetMute() reports 0 (unmuted)."""
        speakers, endpoint_volume = self._make_mock_speakers(current_volume=0.5, muted=False)
        with self._patch_pycaw(speakers):
            system_volume.set_system_volume_scalar(0.5)

        endpoint_volume.SetMute.assert_called_once_with(0, None)

    def test_max_is_a_scalar_set_to_1(self):
        speakers, endpoint_volume = self._make_mock_speakers(current_volume=0.36)
        with self._patch_pycaw(speakers):
            result = system_volume.set_system_volume_max()

        self.assertTrue(result["ok"])
        endpoint_volume.SetMasterVolumeLevelScalar.assert_called_once_with(1.0, None)

    def test_returns_error_dict_when_pycaw_not_installed(self):
        with patch.dict(sys.modules, {"pycaw": None, "pycaw.pycaw": None}):
            result = system_volume.set_system_volume_scalar(0.5)

        self.assertFalse(result["ok"])
        self.assertIn("message", result)

    def test_returns_error_dict_on_core_audio_exception(self):
        mock_audio_utilities = MagicMock()
        mock_audio_utilities.GetSpeakers.side_effect = OSError("No audio endpoint")
        mock_pycaw_module = MagicMock()
        mock_pycaw_module.AudioUtilities = mock_audio_utilities

        with patch.dict(sys.modules, {"pycaw": MagicMock(), "pycaw.pycaw": mock_pycaw_module}):
            result = system_volume.set_system_volume_scalar(0.5)

        self.assertFalse(result["ok"])
        self.assertIn("No audio endpoint", result["message"])


if __name__ == "__main__":
    unittest.main()
