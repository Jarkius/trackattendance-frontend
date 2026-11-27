#!/usr/bin/env python3
"""Tests for native_video.NativeVideoPanel (spec: docs/specs/native-video-playback.md).

The panel's player, audio output, video widget and loop timer are injected: a recording
stand-in player (same surface as QMediaPlayer), a real QWidget and a real QTimer. No media
is decoded, so this runs headless in CI.

Run: python tests/test_native_video.py
"""

import os
import sys
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402
pytest.importorskip("PyQt6")  # CI installs no Qt; these run locally

from PyQt6.QtCore import QObject, Qt, QTimer, pyqtSignal  # noqa: E402
from PyQt6.QtMultimedia import QMediaPlayer  # noqa: E402
from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget  # noqa: E402

from native_video import NativeVideoPanel, VideoProbe  # noqa: E402

APP = QApplication.instance() or QApplication([])
Status = QMediaPlayer.MediaStatus


class RecordingPlayer(QObject):
    """Stand-in for QMediaPlayer: records what the panel asks it to do."""
    mediaStatusChanged = pyqtSignal(object)
    errorOccurred = pyqtSignal(object, str)
    positionChanged = pyqtSignal(int)

    def __init__(self):
        super().__init__()
        self.length_ms = 10_000
        self.calls = []
        self.source = None
        self.loops = None
        self.position = None
        self.audio = None

    def duration(self): return self.length_ms
    def setSource(self, url): self.source = url; self.calls.append("setSource")
    def setLoops(self, n): self.loops = n
    def setPosition(self, ms): self.position = ms; self.calls.append(f"setPosition({ms})")
    def setAudioOutput(self, a): self.audio = a
    def setVideoOutput(self, w): pass
    def play(self): self.calls.append("play")
    def pause(self): self.calls.append("pause")
    def stop(self): self.calls.append("stop")


class RecordingAudio:
    def __init__(self):
        self.volume = None

    def setVolume(self, v): self.volume = v


class PanelTestCase(unittest.TestCase):
    def setUp(self):
        self.window = QMainWindow()
        self.page = QWidget()
        self.window.setCentralWidget(self.page)
        self.window.resize(800, 600)
        self.player = RecordingPlayer()
        self.audios = []
        self.timer = QTimer()
        self.timer.setSingleShot(True)
        self.panel = NativeVideoPanel(
            self.window, self.page,
            player=self.player,
            make_audio=lambda: self.audios.append(RecordingAudio()) or self.audios[-1],
            video_widget=QWidget(self.window),
            loop_timer=self.timer,
        )
        self.video = Path(__file__)  # any existing file; nothing decodes it

    def tearDown(self):
        self.panel.stop()
        self.window.deleteLater()


class TestPanelNeverTakesInput(PanelTestCase):
    def test_widget_cannot_take_focus_or_mouse(self):
        w = self.panel.widget
        self.assertEqual(w.focusPolicy(), Qt.FocusPolicy.NoFocus)
        self.assertTrue(w.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents))


class TestPlay(PanelTestCase):
    def test_play_shows_panel_over_page_and_starts(self):
        self.window.show()
        self.panel.play(self.video, volume=0.8, loop_pause_s=0)
        self.assertTrue(self.panel.widget.isVisible())
        self.assertEqual(self.panel.widget.geometry(), self.page.geometry())
        self.assertEqual(Path(self.player.source.toLocalFile()), self.video)
        self.assertEqual(self.player.calls[-1], "play")
        self.assertEqual(self.audios[-1].volume, 0.8)

    def test_continuous_loop_when_no_pause(self):
        self.panel.play(self.video, volume=1, loop_pause_s=0)
        self.assertEqual(self.player.loops, QMediaPlayer.Loops.Infinite)

    def test_fresh_audio_output_per_play_follows_speaker_changes(self):
        self.panel.play(self.video, volume=1, loop_pause_s=0)
        self.panel.stop()
        self.panel.play(self.video, volume=1, loop_pause_s=0)
        self.assertEqual(len(self.audios), 2)
        self.assertIs(self.player.audio, self.audios[-1])

    def test_panel_follows_page_resize(self):
        self.window.show()
        self.panel.play(self.video, volume=1, loop_pause_s=0)
        self.window.resize(1000, 700)
        APP.processEvents()
        APP.processEvents()
        self.assertEqual(self.panel.widget.geometry(), self.page.geometry())


class TestPauseBetweenLoops(PanelTestCase):
    def test_end_of_media_rests_on_first_frame_then_replays(self):
        self.panel.play(self.video, volume=1, loop_pause_s=30)
        self.assertEqual(self.player.loops, 1)
        self.player.calls.clear()

        self.player.mediaStatusChanged.emit(Status.EndOfMedia)
        self.assertEqual(self.player.calls, ["setPosition(0)", "pause"])
        self.assertTrue(self.timer.isActive())
        self.assertEqual(self.timer.interval(), 30_000)

        self.timer.timeout.emit()          # the pause is over
        self.assertEqual(self.player.calls[-1], "play")

    def test_stop_during_pause_cancels_the_replay(self):
        self.panel.play(self.video, volume=1, loop_pause_s=30)
        self.player.mediaStatusChanged.emit(Status.EndOfMedia)
        self.panel.stop()
        self.assertFalse(self.timer.isActive())
        self.player.calls.clear()
        self.timer.timeout.emit()          # a late expiry must not restart playback
        self.assertNotIn("play", self.player.calls)

    def test_end_of_media_ignored_when_looping_continuously(self):
        self.panel.play(self.video, volume=1, loop_pause_s=0)
        self.player.calls.clear()
        self.player.mediaStatusChanged.emit(Status.EndOfMedia)
        self.assertEqual(self.player.calls, [])
        self.assertFalse(self.timer.isActive())


class TestRestart(PanelTestCase):
    def test_restart_goes_back_to_first_frame_and_plays(self):
        self.panel.play(self.video, volume=1, loop_pause_s=0)
        self.player.positionChanged.emit(30_000)
        self.player.calls.clear()
        self.panel.restart()
        self.assertEqual(self.player.calls, ["setPosition(0)", "play"])

    def test_restart_skipped_when_already_near_the_start(self):
        self.panel.play(self.video, volume=1, loop_pause_s=0)
        self.player.positionChanged.emit(1_500)
        self.player.calls.clear()
        self.panel.restart()
        self.assertEqual(self.player.calls, [])

    def test_restart_ignored_when_not_playing(self):
        self.player.calls.clear()
        self.panel.restart()
        self.assertEqual(self.player.calls, [])

    def test_restart_during_rest_between_loops_resumes_now(self):
        self.panel.play(self.video, volume=1, loop_pause_s=30)
        self.player.positionChanged.emit(30_000)
        self.player.mediaStatusChanged.emit(Status.EndOfMedia)
        self.assertTrue(self.timer.isActive())
        self.player.calls.clear()
        self.panel.restart()
        self.assertFalse(self.timer.isActive())
        self.assertEqual(self.player.calls[-1], "play")


class TestEdgeFade(PanelTestCase):
    def _volume_at(self, pos_ms):
        self.player.positionChanged.emit(pos_ms)
        return self.audios[-1].volume

    def test_off_by_default_volume_untouched(self):
        self.panel.play(self.video, volume=0.8, loop_pause_s=0)
        self.assertEqual(self._volume_at(9_900), 0.8)

    def test_fades_in_at_start_and_out_at_end(self):
        self.panel.play(self.video, volume=0.8, loop_pause_s=0, end_fade_s=2)
        self.assertEqual(self.audios[-1].volume, 0.0)
        self.assertAlmostEqual(self._volume_at(1_000), 0.4)
        self.assertAlmostEqual(self._volume_at(5_000), 0.8)      # middle: full volume
        self.assertAlmostEqual(self._volume_at(9_000), 0.4)
        self.assertEqual(self._volume_at(10_000), 0.0)

    def test_page_volume_changes_scale_the_envelope(self):
        self.panel.play(self.video, volume=1, loop_pause_s=0, end_fade_s=2)
        self._volume_at(9_000)                                   # envelope 0.5
        self.panel.set_volume(0.5)
        self.assertAlmostEqual(self.audios[-1].volume, 0.25)

    def test_short_clip_fades_never_overlap(self):
        self.player.length_ms = 2_000
        self.panel.play(self.video, volume=1, loop_pause_s=0, end_fade_s=5)
        self.assertAlmostEqual(self._volume_at(1_000), 1.0)      # fade capped at half the clip


class TestStopVolumeAndErrors(PanelTestCase):
    def test_stop_hides_and_stops(self):
        self.window.show()
        self.panel.play(self.video, volume=1, loop_pause_s=0)
        self.panel.stop()
        self.assertFalse(self.panel.widget.isVisible())
        self.assertEqual(self.player.calls[-1], "stop")
        self.assertFalse(self.panel.is_playing)

    def test_set_volume_is_clamped(self):
        self.panel.play(self.video, volume=1, loop_pause_s=0)
        self.panel.set_volume(1.7)
        self.assertEqual(self.audios[-1].volume, 1.0)
        self.panel.set_volume(-3)
        self.assertEqual(self.audios[-1].volume, 0.0)

    def test_player_error_while_playing_hides_and_reports(self):
        reasons = []
        self.panel.failed.connect(reasons.append)
        self.window.show()
        self.panel.play(self.video, volume=1, loop_pause_s=0)
        self.player.errorOccurred.emit(QMediaPlayer.Error.FormatError, "bad file")
        self.assertEqual(reasons, ["bad file"])
        self.assertFalse(self.panel.widget.isVisible())
        self.assertFalse(self.panel.is_playing)


class TestEscapeSafetyNet(PanelTestCase):
    """Esc must take the panel down even if the page stopped responding, and must still
    reach the page (it releases the hold screen there)."""

    def press(self, key):
        from PyQt6.QtGui import QKeyEvent
        from PyQt6.QtCore import QEvent
        seen = []

        class Recorder(QObject):
            def eventFilter(self_, obj, ev):
                if obj is self.page and ev.type() == QEvent.Type.KeyPress:
                    seen.append(ev.key())
                return False

        rec = Recorder()
        self.page.installEventFilter(rec)
        QApplication.sendEvent(self.page, QKeyEvent(QEvent.Type.KeyPress, key, Qt.KeyboardModifier.NoModifier))
        self.page.removeEventFilter(rec)
        return seen

    def test_escape_stops_the_panel_and_still_reaches_the_page(self):
        self.window.show()
        self.panel.play(self.video, volume=1, loop_pause_s=0)
        seen = self.press(Qt.Key.Key_Escape)
        self.assertFalse(self.panel.is_playing)
        self.assertFalse(self.panel.widget.isVisible())
        self.assertEqual(seen, [Qt.Key.Key_Escape])

    def test_other_keys_do_not_stop_the_panel(self):
        self.panel.play(self.video, volume=1, loop_pause_s=0)
        self.press(Qt.Key.Key_1)                         # a badge scan digit
        self.assertTrue(self.panel.is_playing)


class ProbePlayer(RecordingPlayer):
    """Stand-in player for the probe: the test decides what loading the file results in."""
    def __init__(self):
        super().__init__()
        self.has_video = True

    def hasVideo(self): return self.has_video


class TestChoosePlayableVideo(unittest.TestCase):
    CANDS = [
        {"url": "file:///C:/k/media/new.mp4", "name": "new.mp4", "source": "media folder"},
        {"url": "file:///C:/k/media/old.webm", "name": "old.webm", "source": "media folder"},
        {"url": "file:///C:/k/assets/media/default-loop.webm", "name": "default-loop.webm",
         "source": "built-in"},
    ]

    def setUp(self):
        self.players = []
        self.results = []

    def make_player(self):
        self.players.append(ProbePlayer())
        return self.players[-1]

    def probe(self, candidates, timeout_ms=10_000):
        p = VideoProbe(candidates, make_player=self.make_player, timeout_ms=timeout_ms)
        p.finished.connect(self.results.append)
        p.start()
        return p

    def test_first_candidate_that_loads_with_video_wins(self):
        self.probe(self.CANDS)
        self.assertEqual(self.players[0].source.toString(), self.CANDS[0]["url"])
        self.players[0].mediaStatusChanged.emit(Status.LoadedMedia)
        self.assertEqual(self.results[0]["chosen"]["name"], "new.mp4")
        self.assertEqual(self.results[0]["rejected"], [])
        self.assertEqual(len(self.players), 1)           # later candidates never opened

    def test_unreadable_file_falls_back_to_next_with_reason(self):
        self.probe(self.CANDS)
        self.players[0].errorOccurred.emit(QMediaPlayer.Error.FormatError, "Unsupported codec")
        self.players[1].mediaStatusChanged.emit(Status.InvalidMedia)
        self.players[2].mediaStatusChanged.emit(Status.LoadedMedia)
        r = self.results[0]
        self.assertEqual(r["chosen"]["name"], "default-loop.webm")
        self.assertEqual([(x["name"], x["why"]) for x in r["rejected"]], [
            ("new.mp4", "Unsupported codec"),
            ("old.webm", "cannot be read as a video"),
        ])

    def test_file_without_video_track_is_rejected(self):
        self.probe(self.CANDS[:1])
        self.players[0].has_video = False                # e.g. an audio-only .mp4
        self.players[0].mediaStatusChanged.emit(Status.LoadedMedia)
        self.assertIsNone(self.results[0]["chosen"])
        self.assertEqual(self.results[0]["rejected"][0]["why"], "no video track")

    def test_file_that_never_loads_times_out(self):
        p = self.probe(self.CANDS[:1], timeout_ms=50)
        p._timer.timeout.emit()                          # the 10 s guard firing
        self.assertIsNone(self.results[0]["chosen"])
        self.assertEqual(self.results[0]["rejected"][0]["why"], "did not load in time")

    def test_no_candidates_finishes_with_nothing(self):
        self.probe([])
        self.assertEqual(self.results, [{"chosen": None, "rejected": []}])

    def test_finishes_once_even_if_the_player_reports_twice(self):
        self.probe(self.CANDS[:1])
        self.players[0].mediaStatusChanged.emit(Status.LoadedMedia)
        self.players[0].mediaStatusChanged.emit(Status.BufferedMedia)
        self.assertEqual(len(self.results), 1)


if __name__ == "__main__":
    unittest.main()
