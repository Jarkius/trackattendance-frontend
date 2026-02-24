from __future__ import annotations

import sys
import json
import time
import logging
import threading
import os
from pathlib import Path
from typing import Callable, Optional, Sequence, Tuple, Dict

# Fix SSL certificates for PyInstaller frozen builds
# Use truststore to leverage Windows system certificate store
if getattr(sys, 'frozen', False):
    try:
        import truststore
        truststore.inject_into_ssl()
        print("[SSL] Using Windows system certificate store (truststore)")
    except ImportError:
        # Fallback to certifi if truststore not available
        import certifi
        _meipass = getattr(sys, '_MEIPASS', None)
        if _meipass:
            bundled_cert = os.path.join(_meipass, 'certifi', 'cacert.pem')
            if os.path.exists(bundled_cert):
                os.environ['SSL_CERT_FILE'] = bundled_cert
                os.environ['REQUESTS_CA_BUNDLE'] = bundled_cert
                print(f"[SSL] Using bundled certificate: {bundled_cert}")
            else:
                cert_path = certifi.where()
                os.environ['SSL_CERT_FILE'] = cert_path
                os.environ['REQUESTS_CA_BUNDLE'] = cert_path
                print(f"[SSL] Bundled cert not found, using certifi: {cert_path}")
        else:
            cert_path = certifi.where()
            os.environ['SSL_CERT_FILE'] = cert_path
            os.environ['REQUESTS_CA_BUNDLE'] = cert_path
            print(f"[SSL] Using certifi: {cert_path}")

from PyQt6.QtCore import QEasingCurve, QObject, QPropertyAnimation, QTimer, QUrl, Qt, pyqtSlot, pyqtSignal, QMetaObject
from PyQt6.QtWidgets import QApplication, QMainWindow, QMessageBox
from PyQt6.QtWebChannel import QWebChannel
from PyQt6.QtWebEngineWidgets import QWebEngineView
import requests

from attendance import AttendanceService
from audio import VoicePlayer
from sync import SyncService
from dashboard import DashboardService
import config

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
VOICES_DIRECTORY = RESOURCE_ROOT / "assets" / "voices"

DATA_DIRECTORY.mkdir(parents=True, exist_ok=True)
EXPORT_DIRECTORY.mkdir(parents=True, exist_ok=True)

LOGGER = logging.getLogger(__name__)


class AutoSyncManager(QObject):
    """
    Manages automatic synchronization of pending scans to the cloud.

    Features:
    - Idle detection: Only syncs when user hasn't scanned for a while
    - Network checking: Verifies actual API connectivity before syncing
    - Non-blocking: Uses Qt's event loop for async operations
    - Status updates: Sends status messages to UI for user feedback
    """

    # Signal emitted when auto-sync completes (for UI updates)
    sync_completed = pyqtSignal(dict)

    def __init__(self, sync_service: Optional[SyncService], web_view):
        super().__init__()
        self.sync_service = sync_service
        self.web_view = web_view
        self.last_scan_time: Optional[float] = None
        self.is_syncing = False
        self.enabled = config.AUTO_SYNC_ENABLED
        self._sync_lock = threading.Lock()

        # Create timer for periodic auto-sync checks
        self.timer = QTimer()
        self.timer.timeout.connect(self.check_and_sync)

    def start(self) -> None:
        """Start the auto-sync timer."""
        if not self.enabled or not self.sync_service:
            print("[AutoSync] Auto-sync is disabled or sync service not available")
            return

        print(f"[AutoSync] Starting auto-sync (check interval: {config.AUTO_SYNC_CHECK_INTERVAL_SECONDS}s, idle threshold: {config.AUTO_SYNC_IDLE_SECONDS}s)")
        self.timer.start(config.AUTO_SYNC_CHECK_INTERVAL_SECONDS * 1000)

    def stop(self) -> None:
        """Stop the auto-sync timer."""
        print("[AutoSync] Stopping auto-sync")
        self.timer.stop()

    def on_scan(self) -> None:
        """
        Update last scan time when user scans a badge.
        This is called from the Api.submit_scan method.
        """
        self.last_scan_time = time.time()

    def is_idle(self) -> bool:
        """Check if system has been idle long enough to trigger auto-sync."""
        if self.last_scan_time is None:
            # No scans yet, consider idle
            return True

        idle_time = time.time() - self.last_scan_time
        return idle_time >= config.AUTO_SYNC_IDLE_SECONDS

    def check_internet_connection(self) -> bool:
        """Test actual API connectivity by hitting the root endpoint."""
        try:
            # Use root endpoint like sync.py test_connection() does
            # Root endpoint is public and doesn't require authentication
            response = requests.get(
                f"{config.CLOUD_API_URL}/",
                timeout=config.AUTO_SYNC_CONNECTION_TIMEOUT
            )
            return response.status_code == 200
        except requests.RequestException:
            return False
        except Exception:
            return False

    def check_and_sync(self) -> None:
        """
        Main auto-sync logic called by timer.
        Checks all conditions and triggers sync if appropriate.
        """
        # Skip if already syncing
        if self.is_syncing:
            return

        # Skip if not idle
        if not self.is_idle():
            return

        # Check pending scans
        if not self.sync_service:
            return

        try:
            stats = self.sync_service.db.get_sync_statistics()
            pending_count = stats.get('pending', 0)

            if pending_count < config.AUTO_SYNC_MIN_PENDING_SCANS:
                return
        except Exception as e:
            print(f"[AutoSync] Error checking pending scans: {e}")
            return

        # Check internet connection
        if not self.check_internet_connection():
            print(f"[AutoSync] No internet connection, skipping auto-sync")
            return

        # Check authentication before attempting sync
        auth_ok, auth_msg = self.sync_service.test_authentication()
        if not auth_ok:
            print(f"[AutoSync] Authentication failed: {auth_msg}")
            return

        # All conditions met - trigger auto-sync
        print(f"[AutoSync] Conditions met: idle={self.is_idle()}, pending={pending_count}, connected=True, auth=OK")
        self.trigger_auto_sync()

    def trigger_auto_sync(self) -> None:
        """Execute auto-sync directly (no threading to avoid SQLite issues)."""
        if not self._sync_lock.acquire(blocking=False):
            return
        self.is_syncing = True

        # Show start message if enabled
        if config.AUTO_SYNC_SHOW_START_MESSAGE:
            self.show_status_message("Auto-syncing pending scans...", "info")

        try:
            print("[AutoSync] Starting sync...")

            # Perform the sync directly (no threading needed - sync is fast)
            result = self.sync_service.sync_pending_scans()

            # Emit signal with result
            self.sync_completed.emit(result)

            # Show completion message if enabled
            if config.AUTO_SYNC_SHOW_COMPLETE_MESSAGE:
                synced_count = result.get('synced', 0)
                failed_count = result.get('failed', 0)

                if synced_count > 0:
                    message = f"Auto-sync complete: {synced_count} scan(s) synced"
                    if failed_count > 0:
                        message += f", {failed_count} failed"
                        self.show_status_message(message, "warning")
                    else:
                        self.show_status_message(message, "success")
                elif failed_count > 0:
                    self.show_status_message(f"Auto-sync: {failed_count} scan(s) failed", "error")

            # Update UI stats directly with the result we got
            self.update_sync_stats(result)

            print(f"[AutoSync] Completed: synced={result.get('synced', 0)}, failed={result.get('failed', 0)}, pending={result.get('pending', 0)}")

        except Exception as e:
            print(f"[AutoSync] Error during sync: {e}")
            if config.AUTO_SYNC_SHOW_COMPLETE_MESSAGE:
                self.show_status_message(f"Auto-sync failed: {str(e)}", "error")
        finally:
            self.is_syncing = False
            self._sync_lock.release()

    def show_status_message(self, message: str, message_type: str = "info") -> None:
        """
        Display status message in the UI.

        Args:
            message: The message text to display
            message_type: Type of message ("info", "success", "error")
        """
        color_map = {
            "info": "#00A3E0",  # Bright blue (starting auto-sync)
            "success": "var(--deloitte-green)",  # Green (auto-sync success)
            "warning": "#FFA500",  # Orange (partial success)
            "error": "red",  # Red (errors)
        }

        color = color_map.get(message_type, "#00A3E0")

        script = f"""
        (function() {{
            console.log('[AutoSync UI] Updating status message: {message}');
            var messageEl = document.getElementById('sync-status-message');
            if (messageEl) {{
                messageEl.textContent = "{message}";
                messageEl.style.color = "{color}";
                console.log('[AutoSync UI] Message element updated successfully');

                // Auto-clear after duration
                setTimeout(function() {{
                    if (messageEl.textContent === "{message}") {{
                        messageEl.textContent = "";
                    }}
                }}, {config.AUTO_SYNC_MESSAGE_DURATION_MS});
            }} else {{
                console.error('[AutoSync UI] Message element not found!');
            }}
        }})();
        """

        print(f"[AutoSync] Injecting status message JS: {message}")
        self.web_view.page().runJavaScript(script)

    def update_sync_stats(self, result: dict) -> None:
        """
        Update sync statistics in the UI directly with provided stats.

        Args:
            result: Dictionary containing 'pending', 'synced', 'failed' counts
        """
        # Get current total stats from database
        stats = self.sync_service.db.get_sync_statistics()

        pending = stats.get('pending', 0)
        synced = stats.get('synced', 0)
        failed = stats.get('failed', 0)

        # Update DOM directly without creating new QWebChannel (avoids conflicts)
        script = f"""
        (function() {{
            console.log('[AutoSync UI] Updating sync statistics...');
            var pendingEl = document.getElementById('sync-pending');
            var syncedEl = document.getElementById('sync-synced');
            var failedEl = document.getElementById('sync-failed');

            if (pendingEl) {{
                pendingEl.textContent = Number({pending}).toLocaleString();
            }}
            if (syncedEl) {{
                syncedEl.textContent = Number({synced}).toLocaleString();
            }}
            if (failedEl) {{
                failedEl.textContent = Number({failed}).toLocaleString();
            }}
            console.log('[AutoSync UI] Sync stats updated successfully');
        }})();
        """
        print(f"[AutoSync] Updating UI stats: pending={pending}, synced={synced}, failed={failed}")
        self.web_view.page().runJavaScript(script)


class Api(QObject):
    """Expose desktop controls to the embedded web UI."""

    # Use QVariant so QWebChannel can deliver payloads to JS reliably
    connection_status_changed = pyqtSignal("QVariant")

    def __init__(
        self,
        service: AttendanceService,
        quit_callback: Callable[[], None],
        sync_service: Optional[SyncService] = None,
        auto_sync_manager: Optional[AutoSyncManager] = None,
        dashboard_service: Optional[DashboardService] = None,
        voice_player: Optional[VoicePlayer] = None,
    ):
        super().__init__()
        self._service = service
        self._quit_callback = quit_callback
        self._sync_service = sync_service
        self._auto_sync_manager = auto_sync_manager
        self._dashboard_service = dashboard_service
        self._voice_player = voice_player
        self._proximity_manager = None  # set after construction if camera plugin loaded
        self._window = None
        self._connection_check_inflight = False
        self._last_connection_result: Dict[str, object] = {
            "ok": False,
            "message": "Connection not checked yet",
        }
        # Emit initial state so the UI can bind immediately
        QTimer.singleShot(0, lambda: self.connection_status_changed.emit(self._last_connection_result))

    @pyqtSlot()
    def _do_emit_signal(self) -> None:
        """Helper slot to emit signal on main thread."""
        LOGGER.debug("Emitting signal from main thread")
        self.connection_status_changed.emit(self._last_connection_result)

    def _emit_connection_status(self, payload: Dict[str, object]) -> None:
        """
        Emit connection status back to the UI on the Qt main thread.

        This ensures the signal reaches QWebChannel even if the check
        completes in a worker thread.
        """
        self._last_connection_result = payload
        LOGGER.info(
            "Emitting connection status to UI: ok=%s, message=%s",
            payload.get("ok"),
            payload.get("message"),
        )
        # Schedule emission on main thread using QTimer
        # This is thread-safe and guarantees signal reaches QWebChannel
        QTimer.singleShot(0, self._do_emit_signal)

    def attach_window(self, window: QMainWindow) -> None:
        self._window = window

    @pyqtSlot(result="QVariant")
    def get_initial_data(self) -> dict:
        """Return initial metrics and history so the web UI can render the dashboard."""
        return self._service.get_initial_payload()

    @pyqtSlot(str, result="QVariant")
    def submit_scan(self, badge_id: str) -> dict:
        """Persist a badge scan and return the enriched result for UI feedback."""
        result = self._service.register_scan(badge_id)

        # Play voice confirmation on successful match (skip duplicates)
        if self._voice_player and result.get("matched") and not result.get("is_duplicate"):
            self._voice_player.play_random()

        # Notify auto-sync manager that a scan occurred
        if self._auto_sync_manager:
            self._auto_sync_manager.on_scan()

        # Suppress camera greeting while queue is active
        if self._proximity_manager:
            self._proximity_manager.notify_scan_activity()

        return result

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
        """Kick off a non-blocking cloud API health check and return last known status."""
        LOGGER.info("UI requested cloud health check")

        if self._connection_check_inflight:
            LOGGER.info("Health check already in flight; returning cached status")
            self._emit_connection_status(self._last_connection_result)
            return self._last_connection_result

        def _run_check() -> None:
            payload = {
                "ok": False,
                "message": "Sync service not configured",
            }
            try:
                if not self._sync_service:
                    LOGGER.warning("Health check skipped: sync service not configured")
                else:
                    LOGGER.info("Dispatching async health check...")
                    ok, msg = self._sync_service.test_connection()
                    payload = {"ok": ok, "message": msg}
                    LOGGER.info("Cloud health check result: ok=%s, message=%s", ok, msg)
            except Exception as exc:  # noqa: BLE001
                LOGGER.exception("Health check failed: %s", exc)
                payload = {"ok": False, "message": f"Check failed: {exc}"}
            finally:
                self._last_connection_result = payload
                self._connection_check_inflight = False
                self._emit_connection_status(payload)

        self._connection_check_inflight = True
        threading.Thread(target=_run_check, daemon=True, name="cloud-health-check").start()
        return self._last_connection_result

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

        # Then test authentication
        auth_ok, auth_msg = self._sync_service.test_authentication()
        if not auth_ok:
            return {
                "ok": False,
                "message": f"Authentication failed: {auth_msg}",
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

    # Dashboard methods (Issue #27)
    @pyqtSlot(result="QVariant")
    def get_dashboard_data(self) -> dict:
        """Fetch multi-station dashboard data from cloud and local database."""
        if not self._dashboard_service:
            return {
                "registered": 0,
                "scanned": 0,
                "total_scans": 0,
                "attendance_rate": 0.0,
                "stations": [],
                "last_updated": "",
                "error": "Dashboard service not configured",
            }
        return self._dashboard_service.get_dashboard_data()

    @pyqtSlot(result="QVariant")
    def export_dashboard_excel(self) -> dict:
        """Export dashboard data to Excel file (auto-generates filename)."""
        if not self._dashboard_service:
            return {
                "ok": False,
                "message": "Dashboard service not configured",
                "file_path": "",
                "fileName": "",
            }
        return self._dashboard_service.export_to_excel()

    @pyqtSlot(result="QVariant")
    def is_admin_enabled(self) -> dict:
        """Check if admin features are available."""
        return {"enabled": config.ADMIN_FEATURES_ENABLED}

    @pyqtSlot(str, result="QVariant")
    def verify_admin_pin(self, pin: str) -> dict:
        """Verify admin PIN."""
        if not config.ADMIN_FEATURES_ENABLED:
            return {"ok": False, "message": "Admin features disabled"}
        if pin == config.ADMIN_PIN:
            return {"ok": True}
        return {"ok": False, "message": "Incorrect PIN"}

    @pyqtSlot(result="QVariant")
    def admin_get_cloud_scan_count(self) -> dict:
        """Get count of scans in cloud database (for confirmation dialog)."""
        if not self._sync_service:
            return {"ok": False, "count": 0, "message": "Sync service not configured"}
        ok, count, message = self._sync_service.get_cloud_scan_count()
        return {"ok": ok, "count": count, "message": message}

    @pyqtSlot(str, result="QVariant")
    def admin_clear_cloud_data(self, pin: str) -> dict:
        """Clear cloud + local scan data after PIN verification."""
        if not config.ADMIN_FEATURES_ENABLED:
            return {"ok": False, "message": "Admin features disabled", "cloud_deleted": 0, "local_deleted": 0}
        if pin != config.ADMIN_PIN:
            return {"ok": False, "message": "Incorrect PIN", "cloud_deleted": 0, "local_deleted": 0}

        results = {"ok": True, "cloud_deleted": 0, "local_deleted": 0, "message": ""}

        # Clear cloud data
        if self._sync_service:
            cloud_result = self._sync_service.clear_cloud_scans()
            if not cloud_result["ok"]:
                return {
                    "ok": False,
                    "message": f"Cloud clear failed: {cloud_result['message']}",
                    "cloud_deleted": 0,
                    "local_deleted": 0,
                }
            results["cloud_deleted"] = cloud_result.get("deleted", 0)

        # Clear local scans
        try:
            local_count = self._service._db.clear_all_scans()
            results["local_deleted"] = local_count
        except Exception as e:
            results["message"] = f"Cloud cleared but local clear failed: {e}"
            results["ok"] = False
            return results

        results["message"] = f"Cleared {results['cloud_deleted']} cloud + {results['local_deleted']} local records"
        LOGGER.info(f"Admin clear: cloud={results['cloud_deleted']}, local={results['local_deleted']}")
        return results

    @pyqtSlot(str)
    def open_export_folder(self, file_path: str) -> None:
        """Open Windows Explorer with the exported file selected."""
        import subprocess
        try:
            subprocess.Popen(["explorer", "/select,", file_path.replace("/", "\\")])
        except Exception as e:
            LOGGER.error("Failed to open export folder: %s", e)


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
            # Party background is on by default in HTML; remove if disabled
            if not config.SHOW_PARTY_BACKGROUND:
                view.page().runJavaScript("document.body.classList.remove('party-bg');")

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
    # Initialize logging first thing
    from logging_config import setup_logging
    setup_logging()

    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)

    service = AttendanceService(
        database_path=DATABASE_PATH,
        employee_workbook_path=EMPLOYEE_WORKBOOK_PATH,
        export_directory=EXPORT_DIRECTORY,
    )

    # Initialize sync service for cloud integration
    sync_service = SyncService(
        db=service._db,
        api_url=config.CLOUD_API_URL,
        api_key=config.CLOUD_API_KEY,
        batch_size=config.CLOUD_SYNC_BATCH_SIZE,
        connection_timeout=config.CONNECTION_CHECK_TIMEOUT_SECONDS,
    )
    LOGGER.info(
        "Connection status checks: interval=%sms, timeout=%.2fs",
        config.CONNECTION_CHECK_INTERVAL_MS,
        config.CONNECTION_CHECK_TIMEOUT_SECONDS,
    )

    # Initialize dashboard service for multi-station reports (Issue #27)
    # Uses the same Cloud API as sync service (no direct Neon connection needed)
    dashboard_service = DashboardService(
        db_manager=service._db,
        api_url=config.CLOUD_API_URL,
        api_key=config.CLOUD_API_KEY,
        export_directory=EXPORT_DIRECTORY,
    )
    LOGGER.info("Dashboard service initialized with Cloud API and export directory")

    # Initialize voice player for scan confirmation audio
    voice_player = VoicePlayer(
        voices_dir=VOICES_DIRECTORY,
        enabled=config.VOICE_ENABLED,
        volume=config.VOICE_VOLUME,
    )

    roster_missing = not service.employees_loaded()
    example_workbook_path: Optional[Path] = None
    if roster_missing:
        example_workbook_path = service.ensure_example_employee_workbook()

    # AutoSyncManager will be created after view is available
    auto_sync_manager_ref = [None]  # Use list to allow mutation in closure

    def api_factory(quit_callback: Callable[[], None]) -> Api:
        return Api(
            service=service,
            quit_callback=quit_callback,
            sync_service=sync_service,
            auto_sync_manager=auto_sync_manager_ref[0],
            dashboard_service=dashboard_service,
            voice_player=voice_player,
        )

    app, window, view, _animation = initialize_app(api_factory=api_factory, load_ui=False)

    # Now that view is created, instantiate AutoSyncManager
    auto_sync_manager = AutoSyncManager(sync_service=sync_service, web_view=view)
    auto_sync_manager_ref[0] = auto_sync_manager

    # Update the API object to use the auto_sync_manager
    api_object = getattr(window, '_api', None)
    if isinstance(api_object, Api):
        api_object._auto_sync_manager = auto_sync_manager

    # Load camera proximity plugin (optional)
    proximity_manager = None
    if config.ENABLE_CAMERA_DETECTION:
        _plugins_camera = Path(__file__).resolve().parent / "plugins" / "camera"
        if _plugins_camera.is_dir():
            try:
                from plugins.camera.proximity_manager import ProximityGreetingManager
                proximity_manager = ProximityGreetingManager(
                    parent_window=window,
                    camera_id=config.CAMERA_DEVICE_ID,
                    cooldown=config.CAMERA_GREETING_COOLDOWN_SECONDS,
                    resolution=(config.CAMERA_RESOLUTION_WIDTH, config.CAMERA_RESOLUTION_HEIGHT),
                    greeting_volume=config.VOICE_VOLUME,
                    scan_busy_seconds=config.CAMERA_SCAN_BUSY_SECONDS,
                    absence_threshold=config.CAMERA_ABSENCE_THRESHOLD_SECONDS,
                    confirm_frames=config.CAMERA_CONFIRM_FRAMES,
                    show_overlay=config.CAMERA_SHOW_OVERLAY,
                    voice_player=voice_player,
                )
                LOGGER.info("[Proximity] Plugin loaded")
                # Wire proximity manager into the API so scans suppress greetings
                if isinstance(api_object, Api):
                    api_object._proximity_manager = proximity_manager
            except Exception as exc:
                LOGGER.warning("[Proximity] Plugin load failed: %s. App continues normally.", exc)
        else:
            LOGGER.warning("[Proximity] ENABLE_CAMERA_DETECTION=true but plugins/camera/ folder not found")

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

    # Start services after UI loads
    def _start_services_on_load(ok: bool) -> None:
        if ok:
            if auto_sync_manager:
                print("[Main] Starting auto-sync manager...")
                auto_sync_manager.start()
            if proximity_manager:
                started = proximity_manager.start()
                if started:
                    LOGGER.info("[Proximity] Greeting active on camera %d", config.CAMERA_DEVICE_ID)
                else:
                    LOGGER.warning("[Proximity] Camera not available. App continues normally.")
        try:
            view.loadFinished.disconnect(_start_services_on_load)
        except TypeError:
            pass

    view.loadFinished.connect(_start_services_on_load)

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

        # === SYNC PHASE ===
        if sync_service:
            try:
                # Check if there are pending scans
                stats = sync_service.db.get_sync_statistics()
                pending_count = stats.get('pending', 0)

                if pending_count > 0:
                    # Check authentication before attempting sync (fail fast)
                    auth_ok, auth_msg = sync_service.test_authentication()
                    if not auth_ok:
                        # Auth failed - show error but proceed with export
                        auth_error_payload = {
                            'stage': 'sync',
                            'ok': False,
                            'message': f'Sync skipped: {auth_msg}. Proceeding with export...',
                            'destination': '',
                            'showConfirm': False,
                            'autoHideMs': 0,
                            'shouldClose': False,
                        }
                        payload_js = json.dumps(auth_error_payload)
                        view.page().runJavaScript(f"window.__handleSyncExportShutdown({payload_js});")
                        time.sleep(0.5)
                    else:
                        # Show "syncing" overlay
                        sync_payload = {
                            'stage': 'sync',
                            'ok': True,
                            'message': f'Syncing {pending_count} pending scan(s)...',
                            'destination': '',
                            'showConfirm': False,
                            'autoHideMs': 0,
                            'shouldClose': False,
                        }
                        payload_js = json.dumps(sync_payload)
                        view.page().runJavaScript(f"window.__handleSyncExportShutdown({payload_js});")

                        # Perform sync - sync ALL pending scans before closing
                        # Use sync_all=True to ensure all batches are uploaded (not just first 100)
                        sync_result = sync_service.sync_pending_scans(sync_all=True)

                        # Determine sync outcome message
                        synced_count = sync_result.get('synced', 0)
                        failed_count = sync_result.get('failed', 0)

                        if synced_count > 0 and failed_count == 0:
                            sync_msg = f'Synced {synced_count} scan(s) successfully. Proceeding with export...'
                            sync_ok = True
                        elif synced_count > 0 and failed_count > 0:
                            sync_msg = f'Synced {synced_count} scan(s), {failed_count} failed. Proceeding with export...'
                            sync_ok = True
                        elif failed_count > 0:
                            sync_msg = f'Sync failed for {failed_count} scan(s). Proceeding with export...'
                            sync_ok = False
                        else:
                            sync_msg = 'No scans synced. Proceeding with export...'
                            sync_ok = True

                        # Show brief sync result (don't wait for user confirmation)
                        sync_done_payload = {
                            'stage': 'sync',
                            'ok': sync_ok,
                            'message': sync_msg,
                            'destination': '',
                            'showConfirm': False,
                            'autoHideMs': 0,
                            'shouldClose': False,
                        }
                        payload_js = json.dumps(sync_done_payload)
                        view.page().runJavaScript(f"window.__handleSyncExportShutdown({payload_js});")

                        # Brief delay to show sync result (500ms)
                        time.sleep(0.5)
            except Exception as exc:
                # Sync failed - log error but continue with export
                error_payload = {
                    'stage': 'sync',
                    'ok': False,
                    'message': f'Sync error: {str(exc)}. Proceeding with export...',
                    'destination': '',
                    'showConfirm': False,
                    'autoHideMs': 0,
                    'shouldClose': False,
                }
                payload_js = json.dumps(error_payload)
                view.page().runJavaScript(f"window.__handleSyncExportShutdown({payload_js});")
                time.sleep(0.5)

        # === EXPORT PHASE ===
        # Check if there are any scans to export
        scan_count = service._db.count_scans_total() if hasattr(service, '_db') else 0

        if scan_count == 0:
            # No scans to export - close immediately without overlay
            original_close_event(event)
            return

        # Show "exporting" overlay
        export_start_payload = {
            'stage': 'export',
            'ok': True,
            'message': 'Generating attendance report...',
            'destination': '',
            'showConfirm': False,
            'autoHideMs': 0,
            'shouldClose': False,
        }
        payload_js = json.dumps(export_start_payload)
        view.page().runJavaScript(f"window.__handleSyncExportShutdown({payload_js});")

        try:
            export_result = service.export_scans()
        except Exception as exc:
            payload = {
                'stage': 'export',
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
                    'stage': 'complete',
                    'ok': True,
                    'message': 'Attendance report exported successfully.',
                    'destination': destination,
                    'showConfirm': False,
                    'autoHideMs': 0,
                    'shouldClose': True,
                }
            else:
                payload = {
                    'stage': 'export',
                    'ok': False,
                    'message': export_result.get('message', 'Unable to export attendance report.'),
                    'destination': export_result.get('absolutePath') or export_result.get('fileName') or '',
                    'showConfirm': True,
                    'autoHideMs': 0,
                    'shouldClose': False,
                }
        payload_js = json.dumps(payload)
        view.page().runJavaScript(f"window.__handleSyncExportShutdown({payload_js});")

    window.closeEvent = _handle_close_event

    try:
        sys.exit(app.exec())
    finally:
        if proximity_manager:
            proximity_manager.stop()
        service.close()


if __name__ == '__main__':
    main()
