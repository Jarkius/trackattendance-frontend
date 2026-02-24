"""Floating camera preview overlay widget.

Displays a small ~1x1 inch (96x96 px) live camera feed in the
top-right corner of the main window. Frameless, always on top,
fully contained in the plugin — no web UI changes needed.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt, QTimer, pyqtSlot
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import QLabel, QMainWindow

if TYPE_CHECKING:
    import numpy as np

LOGGER = logging.getLogger(__name__)

OVERLAY_SIZE = 96  # px (~1 inch at 96 DPI)
MARGIN_TOP = 8  # px from top of parent
MARGIN_LEFT = 8  # px from left of parent


class CameraOverlay(QLabel):
    """Frameless floating widget showing live camera preview."""

    def __init__(self, parent_window: QMainWindow):
        super().__init__(parent_window)
        self._parent_window = parent_window

        # Frameless, tool window (no taskbar entry), stays on top of parent
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)

        self.setFixedSize(OVERLAY_SIZE, OVERLAY_SIZE)
        self.setScaledContents(True)

        # Styling: dark background, rounded corners, thin border
        self.setStyleSheet(
            "QLabel {"
            "  background-color: #111;"
            "  border: 1px solid rgba(255, 255, 255, 0.2);"
            "  border-radius: 8px;"
            "}"
        )
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Install event filter on parent to track move/resize
        parent_window.installEventFilter(self)

    def show_overlay(self) -> None:
        """Position and show the overlay."""
        self._reposition()
        self.show()
        self.raise_()

    def _reposition(self) -> None:
        """Place overlay at top-left of parent window."""
        parent_geo = self._parent_window.geometry()
        x = parent_geo.x() + MARGIN_LEFT
        y = parent_geo.y() + MARGIN_TOP
        self.move(x, y)

    def eventFilter(self, obj, event) -> bool:
        """Track parent window move/resize to reposition overlay."""
        from PyQt6.QtCore import QEvent
        if obj is self._parent_window and event.type() in (
            QEvent.Type.Move, QEvent.Type.Resize,
            QEvent.Type.WindowStateChange,
        ):
            if self.isVisible():
                QTimer.singleShot(0, self._reposition)
        return False

    @pyqtSlot()
    def update_frame_slot(self) -> None:
        """Called on main thread to paint the pending frame."""
        if self._pending_frame is not None:
            self.setPixmap(self._pending_frame)
            self._pending_frame = None

    def update_frame(self, frame: "np.ndarray") -> None:
        """Convert a BGR numpy frame to QPixmap and schedule UI update.

        Safe to call from any thread — the actual setPixmap happens on
        the main thread via QMetaObject.invokeMethod.
        """
        try:
            import cv2
            from PyQt6.QtCore import QMetaObject, Qt as QtConst

            # Resize to overlay size (fast)
            small = cv2.resize(frame, (OVERLAY_SIZE, OVERLAY_SIZE))
            # BGR → RGB and ensure contiguous memory
            rgb = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb.shape
            bytes_per_line = ch * w
            # .copy() forces Qt to own the pixel data, preventing segfault
            # when the numpy buffer is garbage-collected before the main
            # thread paints the pixmap.
            qimg = QImage(rgb.data, w, h, bytes_per_line, QImage.Format.Format_RGB888).copy()
            pixmap = QPixmap.fromImage(qimg)

            # Store pending frame and invoke slot on main thread
            self._pending_frame = pixmap
            QMetaObject.invokeMethod(
                self, "update_frame_slot", QtConst.ConnectionType.QueuedConnection
            )
        except Exception as exc:
            LOGGER.debug("[CameraOverlay] Frame update error: %s", exc)

    _pending_frame: QPixmap | None = None

    def hide_overlay(self) -> None:
        """Hide the overlay."""
        self.hide()
