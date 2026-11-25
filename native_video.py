"""Native video panel for the full-screen display (idle screensaver / hold screen).

PyQt6's QtWebEngine cannot decode H.264, the codec of almost every MP4; Qt Multimedia can.
So the video plays in a QVideoWidget stacked over the web page, inside the same frameless
full-screen window, while web/script.js keeps every decision (when to show/hide, Esc,
scans, camera, sound fades) and drives this panel through the bridge.

The panel must never take input: no keyboard focus and transparent to the mouse, so Esc,
badge scans, Ctrl+Shift+H and clicks still reach the page underneath. Spec:
docs/specs/native-video-playback.md.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable, Optional

from PyQt6.QtCore import QEvent, QObject, Qt, QTimer, QUrl, pyqtSignal
from PyQt6.QtMultimedia import QMediaPlayer
from PyQt6.QtWidgets import QApplication, QWidget

LOGGER = logging.getLogger(__name__)


def _default_audio():
    """An audio output on the *current* default device (a speaker switched after start-up)."""
    from PyQt6.QtMultimedia import QAudioOutput, QMediaDevices
    return QAudioOutput(QMediaDevices.defaultAudioOutput())


def _default_video_widget(parent: QWidget) -> QWidget:
    from PyQt6.QtMultimediaWidgets import QVideoWidget
    widget = QVideoWidget(parent)
    widget.setAspectRatioMode(Qt.AspectRatioMode.KeepAspectRatio)   # "contain", as before
    widget.setStyleSheet("background: #000;")
    return widget


class NativeVideoPanel(QObject):
    """A looping video over `page`, optionally resting on its first frame between loops."""

    failed = pyqtSignal(str)   # player error while playing; the panel is already hidden

    def __init__(self, window: QWidget, page: QWidget, *,
                 player: Optional[QMediaPlayer] = None,
                 make_audio: Optional[Callable[[], object]] = None,
                 video_widget: Optional[QWidget] = None,
                 loop_timer: Optional[QTimer] = None):
        super().__init__(window)
        self._page = page
        self._player = player if player is not None else QMediaPlayer(self)
        self._make_audio = make_audio or _default_audio
        self._audio = None
        self.widget = video_widget if video_widget is not None else _default_video_widget(window)
        self.widget.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.widget.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.widget.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.widget.hide()
        if hasattr(self._player, "setVideoOutput"):
            self._player.setVideoOutput(self.widget)

        self._loop_timer = loop_timer if loop_timer is not None else QTimer(self)
        self._loop_timer.setSingleShot(True)
        self._loop_timer.timeout.connect(self._resume_after_pause)
        self._loop_pause_ms = 0
        self.is_playing = False

        self._player.mediaStatusChanged.connect(self._on_status)
        self._player.errorOccurred.connect(self._on_error)
        page.installEventFilter(self)
        # Safety net: Esc always takes the panel down, even if the page stopped driving it.
        # Application-wide because the key goes to the page's focus widget, not to us.
        app = QApplication.instance()
        if app is not None:
            app.installEventFilter(self)

    # ── control ──
    def play(self, path: Path, volume: float, loop_pause_s: int) -> None:
        self._loop_timer.stop()
        self._loop_pause_ms = max(0, int(loop_pause_s)) * 1000
        self._audio = self._make_audio()
        self._audio.setVolume(_clamp(volume))
        self._player.setAudioOutput(self._audio)
        self._player.setLoops(QMediaPlayer.Loops.Infinite if self._loop_pause_ms == 0 else 1)
        self._player.setSource(QUrl.fromLocalFile(str(path)))
        self._follow_page()
        self.widget.show()
        self.widget.raise_()
        self.is_playing = True
        self._player.play()

    def stop(self) -> None:
        self._loop_timer.stop()
        self.is_playing = False
        self._player.stop()
        self.widget.hide()

    def set_volume(self, volume: float) -> None:
        if self._audio is not None:
            self._audio.setVolume(_clamp(volume))

    # ── loop with a rest between plays ──
    def _on_status(self, status) -> None:
        if status == QMediaPlayer.MediaStatus.EndOfMedia and self.is_playing and self._loop_pause_ms:
            self._player.setPosition(0)
            self._player.pause()                 # first frame stays up, no sound
            self._loop_timer.start(self._loop_pause_ms)

    def _resume_after_pause(self) -> None:
        if self.is_playing:
            self._player.play()

    def _on_error(self, _error, message: str) -> None:
        if not self.is_playing:
            return
        LOGGER.warning("[NativeVideo] Playback failed: %s", message)
        self.stop()
        self.failed.emit(message)

    # ── stay exactly over the page (resize, full screen) ──
    def _follow_page(self) -> None:
        self.widget.setGeometry(self._page.geometry())

    def eventFilter(self, obj, event) -> bool:
        etype = event.type()
        if obj is self._page and etype in (QEvent.Type.Resize, QEvent.Type.Move):
            QTimer.singleShot(0, self._follow_page)
        elif (etype == QEvent.Type.KeyPress and self.is_playing
              and event.key() == Qt.Key.Key_Escape):
            LOGGER.info("[NativeVideo] Esc: panel stopped")
            self.stop()
        return False   # never consume: Esc must still reach the page (hold release etc.)


class VideoProbe(QObject):
    """Find the first candidate Qt can really play: loads with a video track.

    Candidates are screensaver_media's {"url", "name", "source"} dicts, tried in order.
    `finished` fires exactly once with {"chosen": candidate | None, "rejected": [candidate +
    "why"]}. A file that neither loads nor fails within timeout_ms is rejected.
    """

    finished = pyqtSignal(object)

    def __init__(self, candidates, *, make_player: Optional[Callable[[], QMediaPlayer]] = None,
                 timeout_ms: int = 10_000, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._pending = list(candidates)
        self._make_player = make_player or (lambda: QMediaPlayer(self))
        self._rejected = []
        self._current = None
        self._player = None
        self._done = False
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(timeout_ms)
        self._timer.timeout.connect(lambda: self._reject("did not load in time"))

    def start(self) -> None:
        self._next()

    def _next(self) -> None:
        self._release_player()
        if not self._pending:
            self._finish(None)
            return
        self._current = self._pending.pop(0)
        self._player = self._make_player()
        self._player.mediaStatusChanged.connect(self._on_status)
        self._player.errorOccurred.connect(lambda _e, msg: self._reject(msg or "cannot be read"))
        self._timer.start()
        self._player.setSource(QUrl(self._current["url"]))

    def _on_status(self, status) -> None:
        if self._done or self._current is None:
            return
        if status in (QMediaPlayer.MediaStatus.LoadedMedia, QMediaPlayer.MediaStatus.BufferedMedia):
            if self._player.hasVideo():
                self._finish(self._current)
            else:
                self._reject("no video track")
        elif status == QMediaPlayer.MediaStatus.InvalidMedia:
            self._reject("cannot be read as a video")

    def _reject(self, why: str) -> None:
        if self._done or self._current is None:
            return
        self._rejected.append({**self._current, "why": why})
        self._current = None
        self._next()

    def _finish(self, chosen) -> None:
        if self._done:
            return
        self._done = True
        self._timer.stop()
        self._current = None
        self._release_player()
        self.finished.emit({"chosen": chosen, "rejected": self._rejected})

    def _release_player(self) -> None:
        self._timer.stop()
        player, self._player = self._player, None
        if player is None:
            return
        try:
            player.mediaStatusChanged.disconnect()
            player.errorOccurred.disconnect()
        except TypeError:
            pass
        if hasattr(player, "deleteLater"):
            player.deleteLater()


def _clamp(volume: float) -> float:
    return max(0.0, min(1.0, float(volume)))
