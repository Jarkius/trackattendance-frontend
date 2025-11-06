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
from sync import SyncService

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

if getattr(sys, 'frozen', False):
    EXEC_ROOT = Path(sys.executable).resolve().parent
    RESOURCE_ROOT = Path(getattr(sys, '_MEIPASS', EXEC_ROOT))
else:
    RESOURCE_ROOT = Path(__file__).resolve().parent
    EXEC_ROOT = RESOURCE_ROOT

DATA_DIRECTORY = EXEC_ROOT / "data"
EXPORT_DIRECTORY = EXEC_ROOT / "exports"
DATABASE_PATH = DATA_DIRECTORY / "database.db"
EMPLOYEE_WORKBOOK_PATH = DATA_DIRECTORY / "employee.xlsx"
UI_INDEX_HTML = RESOURCE_ROOT / "web" / "index.html"

DATA_DIRECTORY.mkdir(parents=True, exist_ok=True)
EXPORT_DIRECTORY.mkdir(parents=True, exist_ok=True)


class Api(QObject):
    """Expose desktop controls to the embedded web UI."""

    def __init__(
        self,
        service: AttendanceService,
        quit_callback: Callable[[], None],
        sync_service: Optional[SyncService] = None,
    ):
        super().__init__()
        self._service = service
        self._quit_callback = quit_callback
        self._sync_service = sync_service
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

    @pyqtSlot(result="QVariant")
    def test_cloud_connection(self) -> dict:
        """Test connection to cloud API and return status."""
        if not self._sync_service:
            return {
                "ok": False,
                "message": "Sync service not configured",
            }
        success, message = self._sync_service.test_connection()
        return {
            "ok": success,
            "message": message,
        }

    @pyqtSlot(result="QVariant")
    def sync_now(self) -> dict:
        """Manually trigger sync and return results."""
        if not self._sync_service:
            return {
                "ok": False,
                "message": "Sync service not configured",
                "synced": 0,
                "failed": 0,
                "pending": 0,
            }

        # First test connection
        success, message = self._sync_service.test_connection()
        if not success:
            return {
                "ok": False,
                "message": f"Cannot connect: {message}",
                "synced": 0,
                "failed": 0,
                "pending": 0,
            }

        # Perform sync
        result = self._sync_service.sync_pending_scans()
        return {
            "ok": True,
            "message": f"Synced {result['synced']} scans successfully",
            "synced": result["synced"],
            "failed": result["failed"],
            "pending": result["pending"],
        }

    @pyqtSlot(result="QVariant")
    def get_sync_status(self) -> dict:
        """Get current sync statistics."""
        if not self._sync_service:
            return {
                "pending": 0,
                "synced": 0,
                "failed": 0,
                "lastSyncAt": None,
            }

        stats = self._sync_service.db.get_sync_statistics()
        return {
            "pending": stats["pending"],
            "synced": stats["synced"],
            "failed": stats["failed"],
            "lastSyncAt": stats["last_sync_time"],
        }

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
    window.setWindowTitle('Track Attendance')
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

    # Initialize sync service for cloud integration
    # TODO: Move these to configuration file or environment variables
    CLOUD_API_URL = "https://trackattendance-api-969370105809.asia-southeast1.run.app"
    CLOUD_API_KEY = "6541f2c7892b4e5287d50c2414d179f8"

    sync_service = SyncService(
        db=service._db,
        api_url=CLOUD_API_URL,
        api_key=CLOUD_API_KEY,
        batch_size=100,
    )

    roster_missing = not service.employees_loaded()
    example_workbook_path: Optional[Path] = None
    if roster_missing:
        example_workbook_path = service.ensure_example_employee_workbook()

    def api_factory(quit_callback: Callable[[], None]) -> Api:
        return Api(service=service, quit_callback=quit_callback, sync_service=sync_service)

    app, window, view, _animation = initialize_app(api_factory=api_factory, load_ui=False)

    if roster_missing:
        sample_path_display = str((example_workbook_path or service.ensure_example_employee_workbook()).resolve())
        QMessageBox.warning(
            window,
            'Employee roster missing',
            (
                f'Unable to locate the employee roster at {EMPLOYEE_WORKBOOK_PATH}.\n\n'
                f'A sample workbook was created at {sample_path_display}.\n'
                'Update the sample and save it as employee.xlsx to enable attendee matching.\n\n'
                'The application will continue, but unmatched scans will be flagged for follow-up.'
            ),
        )

    service.ensure_station_configured(window)

    if roster_missing:
        overlay_payload = {
            'ok': False,
            'message': (
                'Employee roster not found. A sample workbook was created. '
                'Update the sample and save it as employee.xlsx to enable matching.'
            ),
            'destination': str((example_workbook_path or service.ensure_example_employee_workbook()).resolve()),
            'showConfirm': False,
            'autoHideMs': 7000,
            'shouldClose': False,
            'title': 'Employee Roster Missing',
        }

        def _show_missing_roster_overlay(ok: bool) -> None:
            if not ok:
                return
            payload_js = json.dumps(overlay_payload)
            view.page().runJavaScript(
                f"if (window.__handleExportShutdown) {{ window.__handleExportShutdown({payload_js}); }}"
            )
            try:
                view.loadFinished.disconnect(_show_missing_roster_overlay)
            except TypeError:
                pass

        view.loadFinished.connect(_show_missing_roster_overlay)

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





