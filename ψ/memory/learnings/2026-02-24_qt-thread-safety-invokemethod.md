# Qt Thread Safety: Marshal via QMetaObject.invokeMethod

**Date**: 2026-02-24
**Context**: Camera plugin greeting player called from background thread
**Project**: trackattendance-frontend

## Pattern

When a background thread (camera loop, worker, etc.) needs to trigger Qt operations (QMediaPlayer, QPixmap, QWidget updates), **never call Qt directly**. Instead:

1. Make the target class extend `QObject`
2. Store data in a plain Python field (thread-safe for simple assignments)
3. Call `QMetaObject.invokeMethod(self, "slot_name", Qt.ConnectionType.QueuedConnection)` to schedule the work on the main thread
4. The `@pyqtSlot` method reads the stored data and does the Qt operations

### Example (GreetingPlayer):
```python
class GreetingPlayer(QObject):
    def play_random(self):  # Called from camera thread
        self._pending_file = choice  # Plain Python — safe
        QMetaObject.invokeMethod(self, "_play_on_main_thread",
                                 Qt.ConnectionType.QueuedConnection)

    @pyqtSlot()
    def _play_on_main_thread(self):  # Runs on Qt main thread
        self._player.setSource(...)  # QMediaPlayer — safe here
        self._player.play()
```

### Anti-pattern: Cross-thread Qt reads
Even read-only access like `player.playbackState()` from a background thread is unsafe. Replace with time-based flags:
```python
# Main thread sets:
self._voice_playing_until = time.time() + 3.0
# Camera thread reads:
if time.time() < self._voice_playing_until: ...  # Plain float — safe
```

## Tags
`qt`, `thread-safety`, `qmediaplayer`, `qobject`, `pyqt6`, `camera`
