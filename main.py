from __future__ import annotations

import sys
import json
from pathlib import Path
from typing import Callable, Optional, Sequence, Tuple

from PyQt6.QtCore import QEasingCurve, QObject, QPropertyAnimation, QUrl, Qt, pyqtSlot
from PyQt6.QtWidgets import QApplication, QMainWindow, QMessageBox
from PyQt6.QtWebChannel import QWebChannel
from PyQt6.QtWebEngineWidgets import QWebEngineView

from attendance import AttendanceService

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

BASE_DIR = Path(__file__).resolve().parent
DATA_DIRECTORY = BASE_DIR / "data"
DATABASE_PATH = DATA_DIRECTORY / "database.db"
EMPLOYEE_WORKBOOK_PATH = DATA_DIRECTORY / "employee.xlsx"
EXPORT_DIRECTORY = BASE_DIR / "exports"
UI_INDEX_HTML = BASE_DIR / "web" / "index.html"

DATA_DIRECTORY.mkdir(parents=True, exist_ok=True)


class Api(QObject):
    """Expose desktop controls to the embedded web UI."""

    def __init__(self, service: AttendanceService, quit_callback: Callable[[], None]):
        super().__init__()
        self._service = service
        self._quit_callback = quit_callback
        self._window = None

    def attach_window(self, window: QMainWindow) -> None:
        self._window = window

    @pyqtSlot(result="QVariant")
    def get_initial_data(self) -> dict:
        """Return initial metrics and history so the web UI can render the dashboard."""
        return self._service.get_initial_payload()

    @pyqtSlot(str, result="QVariant")
    def submit_scan(self, badge_id: str) -> dict:
        """Persist a badge scan and return the enriched result for UI feedback."""
        return self._service.register_scan(badge_id)

    @pyqtSlot(result="QVariant")
    def export_scans(self) -> dict:
        """Write the scan history to disk and provide the destination filename."""
        return self._service.export_scans()

    @pyqtSlot()
    def close_window(self) -> None:
        """Shut down the QApplication when the web UI requests a close via QWebChannel."""
        if self._quit_callback:
            self._quit_callback()


    @pyqtSlot()
    def finalize_export_close(self) -> None:
        if self._window is not None:
            self._window.setProperty('suppress_export_notification', True)
            self._window.close()
            if self._quit_callback:
                self._quit_callback()
            return
        if self._quit_callback:
            self._quit_callback()


def initialize_app(
    argv: Optional[Sequence[str]] = None,
    *,
    show_window: bool = True,
    show_full_screen: bool = True,
    enable_fade: bool = True,
    on_load_finished: Optional[Callable[[bool], None]] = None,
    load_ui: bool = True,
    api_factory: Optional[Callable[[Callable[[], None]], QObject]] = None,
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
    if api_factory is None:
        raise ValueError("An api_factory callable is required to initialize the web channel.")
    api = api_factory(app.quit)
    channel.registerObject('api', api)
    view.page().setWebChannel(channel)

    file_path = UI_INDEX_HTML
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
    if load_ui:
        view.setUrl(QUrl.fromLocalFile(str(file_path)))

    window._web_channel = channel  # type: ignore[attr-defined]
    window._api = api  # type: ignore[attr-defined]

    return app, window, view, animation


def main() -> None:
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)

    service = AttendanceService(
        database_path=DATABASE_PATH,
        employee_workbook_path=EMPLOYEE_WORKBOOK_PATH,
        export_directory=EXPORT_DIRECTORY,
    )

    def api_factory(quit_callback: Callable[[], None]) -> Api:
        return Api(service=service, quit_callback=quit_callback)

    app, window, view, _animation = initialize_app(api_factory=api_factory, load_ui=False)

    service.ensure_station_configured(window)

    view.setUrl(QUrl.fromLocalFile(str(UI_INDEX_HTML)))

    api_object = getattr(window, '_api', None)
    if isinstance(api_object, Api):
        api_object.attach_window(window)

    window.setProperty('suppress_export_notification', False)
    window.setProperty('export_notification_triggered', False)

    original_close_event = window.closeEvent

    def _handle_close_event(event) -> None:
        if window.property('suppress_export_notification'):
            if not window.property('export_notification_triggered'):
                try:
                    service.export_scans()
                except Exception:
                    pass
                window.setProperty('export_notification_triggered', True)
            return original_close_event(event)

        if window.property('export_notification_triggered'):
            event.ignore()
            return

        event.ignore()
        window.setProperty('export_notification_triggered', True)

        try:
            export_result = service.export_scans()
        except Exception as exc:
            payload = {
                'ok': False,
                'message': f'Unable to export attendance report: {exc}',
                'destination': '',
                'showConfirm': True,
                'autoHideMs': 0,
                'shouldClose': False,
            }
        else:
            if export_result.get('ok'):
                destination = export_result.get('absolutePath') or export_result.get('fileName') or ''
                payload = {
                    'ok': True,
                    'message': 'Attendance report exported successfully.',
                    'destination': destination,
                    'showConfirm': False,
                    'autoHideMs': 0,
                    'shouldClose': True,
                }
            else:
                payload = {
                    'ok': False,
                    'message': export_result.get('message', 'Unable to export attendance report.'),
                    'destination': export_result.get('absolutePath') or export_result.get('fileName') or '',
                    'showConfirm': True,
                    'autoHideMs': 0,
                    'shouldClose': False,
                }
        payload_js = json.dumps(payload)
        view.page().runJavaScript(f"window.__handleExportShutdown({payload_js});")

    window.closeEvent = _handle_close_event

    try:
        sys.exit(app.exec())
    finally:
        service.close()


if __name__ == '__main__':
    main()





