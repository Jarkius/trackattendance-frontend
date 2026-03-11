# Qt Overlay Positioning: frameGeometry vs geometry

**Date**: 2026-03-11
**Context**: TrackAttendance camera icon was positioned too low, overlapping the title bar
**Confidence**: High

## Key Learning

When positioning floating Qt widgets (frameless overlays, tooltips, status icons) relative to a parent window, you must account for the window decoration (title bar). `QMainWindow.geometry()` returns the content area rectangle, while `QMainWindow.frameGeometry()` returns the full window rectangle including the title bar and borders.

If you use `geometry().y()` as your reference point, you're already past the title bar — so adding a margin puts you inside the content area correctly. But if you use `frameGeometry()` for x/y positioning (which gives the actual screen position of the window frame), you need to add the title bar height explicitly:

```python
title_bar_height = content_geo.y() - frame_geo.y()
y = frame_geo.y() + title_bar_height + margin
```

This is platform-dependent — macOS has a ~28px title bar, Windows varies with DPI scaling. Always compute dynamically, never hardcode.

## The Pattern

```python
def _reposition(self) -> None:
    frame_geo = self._parent_window.frameGeometry()
    content_geo = self._parent_window.geometry()
    title_bar_height = content_geo.y() - frame_geo.y()
    x = frame_geo.x() + MARGIN_LEFT
    y = frame_geo.y() + title_bar_height + MARGIN_TOP
    self.move(x, y)
```

## Why This Matters

Frameless floating widgets are common in kiosk applications (status indicators, camera overlays, notification badges). Getting the positioning wrong means UI elements overlap the title bar or sit in the wrong spot across platforms. This pattern ensures correct placement on any OS.

## Tags

`qt`, `pyqt6`, `overlay`, `positioning`, `frameGeometry`, `geometry`, `title-bar`, `kiosk-ui`
