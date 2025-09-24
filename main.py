import os
import sys
from typing import Callable, Optional, Sequence, Tuple

from PyQt6.QtCore import QEasingCurve, QPropertyAnimation, QUrl
from PyQt6.QtCore import QObject, Qt, pyqtSlot
from PyQt6.QtWidgets import QApplication, QMainWindow, QMessageBox
from PyQt6.QtWebChannel import QWebChannel
from PyQt6.QtWebEngineWidgets import QWebEngineView

FALLBACK_ERROR_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Interface Load Error</title>
    <style>
        body {
            margin: 0;
            font-family: "Segoe UI", Arial, sans-serif;
            display: flex;
            align-items: center;
            justify-content: center;
            height: 100vh;
            background-color: #f5f5f5;
            color: #333333;
        }
        .container {
            max-width: 560px;
            padding: 32px;
            text-align: center;
            border: 1px solid #e0e0e0;
            border-radius: 12px;
            background-color: #ffffff;
            box-shadow: 0 12px 32px rgba(0, 0, 0, 0.08);
        }
        h1 {
            margin-bottom: 12px;
            font-size: 1.6rem;
            color: #000000;
        }
        p {
            margin: 0;
            line-height: 1.5;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Interface Load Error</h1>
        <p>The attendance experience could not be loaded. Please verify that the local assets under <code>web/</code> are available, then restart the application.</p>
        <p>Press <strong>Alt+F4</strong> (or close the window from the taskbar) to exit.</p>
    </div>
</body>
</html>"""


class Api(QObject):
    """Expose desktop controls to the embedded web UI."""

    def __init__(self, quit_callback: Callable[[], None]):
        super().__init__()
        self._quit_callback = quit_callback

    @pyqtSlot()
    def close_window(self) -> None:
        """Shut down the QApplication when the web UI requests a close via QWebChannel."""
        if self._quit_callback:
            self._quit_callback()


def initialize_app(
    argv: Optional[Sequence[str]] = None,
    *,
    show_window: bool = True,
    show_full_screen: bool = True,
    enable_fade: bool = True,
    on_load_finished: Optional[Callable[[bool], None]] = None,
) -> Tuple[QApplication, QMainWindow, QWebEngineView, QPropertyAnimation]:
    """Prepare the PyQt application and interface without starting the event loop."""
    app = QApplication.instance()
    if app is None:
        args = list(argv) if argv is not None else sys.argv
        app = QApplication(args)

    window = QMainWindow()
    window.setWindowTitle('Deloitte Staff Attendance')
    window.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    window.setWindowFlags(Qt.WindowType.FramelessWindowHint)
    window.setWindowOpacity(0.0 if enable_fade and show_window else 1.0)

    view = QWebEngineView()
    view.page().setBackgroundColor(Qt.GlobalColor.transparent)

    animation = QPropertyAnimation(window, b"windowOpacity")
    animation.setDuration(400)
    animation.setStartValue(0.0)
    animation.setEndValue(1.0)
    animation.setEasingCurve(QEasingCurve.Type.InOutQuad)

    channel = QWebChannel()
    api = Api(app.quit)
    channel.registerObject('api', api)
    view.page().setWebChannel(channel)

    file_path = os.path.abspath(os.path.join(os.path.dirname(__file__), 'web', 'index.html'))
    window.setCentralWidget(view)

    def handle_load_finished(ok: bool) -> None:
        if ok:
            if not show_window:
                window.setWindowOpacity(1.0)
            else:
                if not enable_fade:
                    window.setWindowOpacity(1.0)
                if show_full_screen:
                    window.showFullScreen()
                else:
                    window.show()
                if enable_fade:
                    animation.start()
            if on_load_finished:
                on_load_finished(ok)
            return

        view.loadFinished.disconnect(handle_load_finished)
        print('Failed to load web interface from:', file=sys.stderr)
        print(file_path, file=sys.stderr)
        window.setWindowOpacity(1.0)
        if show_window:
            if show_full_screen:
                window.showFullScreen()
            else:
                window.show()
        view.setHtml(FALLBACK_ERROR_HTML)
        if show_window:
            QMessageBox.critical(
                window,
                'Load Error',
                'Unable to load the attendance interface. Please check the local assets and try again.'
            )
        if on_load_finished:
            on_load_finished(ok)

    view.loadFinished.connect(handle_load_finished)
    view.setUrl(QUrl.fromLocalFile(file_path))

    window._web_channel = channel  # type: ignore[attr-defined]
    window._api = api  # type: ignore[attr-defined]

    return app, window, view, animation


def main() -> None:
    app, _, _, _ = initialize_app()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
