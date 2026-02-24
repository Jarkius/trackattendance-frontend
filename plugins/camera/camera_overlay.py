"""Floating camera overlay widget.

Two modes:
  - preview: live camera feed (96x96 px) — for debugging
  - icon:    small camera status icon (32x32 px) — for production

Both are frameless Qt widgets positioned at the top-left corner
of the main window. Fully contained in the plugin — no web UI changes.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt, QTimer, pyqtSlot
from PyQt6.QtGui import QImage, QPixmap, QPainter, QColor
from PyQt6.QtWidgets import QLabel, QMainWindow

if TYPE_CHECKING:
    import numpy as np

LOGGER = logging.getLogger(__name__)

PREVIEW_SIZE = 96  # px for live feed mode
ICON_SIZE = 32  # px for icon-only mode
MARGIN_TOP = 8
MARGIN_LEFT = 8


class CameraOverlay(QLabel):
    """Frameless floating widget — live preview or status icon."""

    def __init__(self, parent_window: QMainWindow, mode: str = "preview"):
        """
        Args:
            parent_window: Main application window to attach to.
            mode: "preview" for live camera feed, "icon" for small status indicator.
        """
        super().__init__(parent_window)
        self._parent_window = parent_window
        self._mode = mode
        self._size = PREVIEW_SIZE if mode == "preview" else ICON_SIZE

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.setFixedSize(self._size, self._size)
        self.setScaledContents(True)

        if mode == "preview":
            self.setStyleSheet(
                "QLabel {"
                "  background-color: #111;"
                "  border: 1px solid rgba(255, 255, 255, 0.2);"
                "  border-radius: 8px;"
                "}"
            )
        else:
            self.setStyleSheet(
                "QLabel {"
                "  background-color: rgba(0, 0, 0, 0.5);"
                "  border: 1px solid rgba(255, 255, 255, 0.15);"
                "  border-radius: 6px;"
                "}"
            )
            self._set_camera_icon()

        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        parent_window.installEventFilter(self)

    def _set_camera_icon(self) -> None:
        """Draw a simple camera shape with green active dot onto a pixmap."""
        from PyQt6.QtCore import QRect, QRectF

        pixmap = QPixmap(self._size, self._size)
        pixmap.fill(QColor(0, 0, 0, 0))

        p = QPainter(pixmap)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Camera body (rounded rect)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(255, 255, 255, 180))
        body = QRectF(4, 10, 20, 14)
        p.drawRoundedRect(body, 2, 2)

        # Camera lens (circle)
        p.setBrush(QColor(50, 50, 50))
        p.drawEllipse(QRectF(9, 12, 10, 10))
        p.setBrush(QColor(255, 255, 255, 180))
        p.drawEllipse(QRectF(11, 14, 6, 6))

        # Flash/viewfinder bump
        p.setBrush(QColor(255, 255, 255, 180))
        p.drawRect(QRect(8, 7, 8, 4))

        # Green active dot — bottom-right corner
        p.setBrush(QColor(76, 175, 80))
        dot_size = 8
        p.drawEllipse(self._size - dot_size - 3, self._size - dot_size - 3,
                       dot_size, dot_size)

        p.end()
        self.setPixmap(pixmap)

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

        Safe to call from any thread. Only works in preview mode;
        icon mode ignores frame updates.
        """
        if self._mode != "preview":
            return

        try:
            import cv2
            from PyQt6.QtCore import QMetaObject, Qt as QtConst

            small = cv2.resize(frame, (PREVIEW_SIZE, PREVIEW_SIZE))
            rgb = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb.shape
            bytes_per_line = ch * w
            qimg = QImage(rgb.data, w, h, bytes_per_line, QImage.Format.Format_RGB888).copy()
            pixmap = QPixmap.fromImage(qimg)

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
