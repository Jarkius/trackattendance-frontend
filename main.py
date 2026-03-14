from __future__ import annotations

import sys
import json
import time
import logging
import logging.handlers
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
def _voices_dir() -> Path:
    """Resolve voices directory with fallback chain.

    Frozen exe: voices/ next to .exe (override) → bundled in assets/voices (fallback)
    Dev mode:   assets/voices/ (as-is)
    """
    if getattr(sys, 'frozen', False):
        override = EXEC_ROOT / "voices"
        if override.is_dir() and any(override.glob("*.mp3")):
            return override
    return RESOURCE_ROOT / "assets" / "voices"

VOICES_DIRECTORY = _voices_dir()

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


class DebugLogBuffer(logging.Handler):
    """Ring-buffer logging handler that stores recent log lines for UI polling."""

    def __init__(self, capacity: int = 200):
        super().__init__()
        self._buffer: list[str] = []
        self._capacity = capacity
        self._cursor = 0  # monotonic counter for polling
        self._lock = threading.Lock()

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            with self._lock:
                self._buffer.append(msg)
                self._cursor += 1
                if len(self._buffer) > self._capacity:
                    self._buffer.pop(0)
        except Exception:
            pass

    def get_lines_since(self, since_cursor: int) -> dict:
        """Return new lines since the given cursor."""
        with self._lock:
            total = self._cursor
            available = len(self._buffer)
            start_cursor = total - available
            if since_cursor < start_cursor:
                since_cursor = start_cursor
            offset = since_cursor - start_cursor
            lines = self._buffer[offset:]
            return {"lines": lines, "cursor": total}


# Global debug buffer — attached to root logger when debug panel is enabled
_debug_log_buffer = DebugLogBuffer(capacity=200)


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
        self._roster_synced = False  # one-time roster push after first successful health check
        # Pre-fetch BU data on main thread (SQLite not thread-safe)
        try:
            self._cached_bu_data = self._service._db.get_employees_by_bu()
        except Exception:
            self._cached_bu_data = []
        self._last_connection_result: Dict[str, object] = {
            "ok": False,
            "message": "Connection not checked yet",
        }
        # Snapshot config defaults before saved settings override them
        self._config_defaults = {
            "dup_alert_ms": config.DUPLICATE_BADGE_ALERT_DURATION_MS,
            "voice_volume": config.VOICE_VOLUME,
            "camera_device_id": config.CAMERA_DEVICE_ID,
            "greeting_cooldown": config.CAMERA_GREETING_COOLDOWN_SECONDS,
            "min_size_pct": config.CAMERA_MIN_SIZE_PCT,
            "absence_threshold": config.CAMERA_ABSENCE_THRESHOLD_SECONDS,
            "confirm_frames": config.CAMERA_CONFIRM_FRAMES,
            "haar_min_neighbors": config.CAMERA_HAAR_MIN_NEIGHBORS,
            "scan_feedback_ms": config.SCAN_FEEDBACK_DURATION_MS,
            "connection_check_s": config.CONNECTION_CHECK_INTERVAL_MS / 1000,
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
            # Tell camera plugin BEFORE playing (closes race window with greeting)
            if self._proximity_manager:
                self._proximity_manager.notify_voice_playing()
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
                    # Push roster BU counts on first successful connection
                    if ok and not self._roster_synced and self._cached_bu_data:
                        self._roster_synced = True
                        try:
                            from sync import sync_roster_summary_from_data
                            from config import CLOUD_API_URL, CLOUD_API_KEY
                            sync_roster_summary_from_data(self._cached_bu_data, CLOUD_API_URL, CLOUD_API_KEY)
                        except Exception as e:
                            LOGGER.warning(f"Roster sync after health check failed: {e}")
                            self._roster_synced = False  # retry next check
                    # Check clear_epoch and send heartbeat (on main thread for SQLite safety)
                    if ok:
                        QMetaObject.invokeMethod(self, "_handle_clear_epoch_and_heartbeat_slot", Qt.ConnectionType.QueuedConnection)
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
    def get_camera_status(self) -> dict:
        """Return camera detection feature status."""
        if not self._proximity_manager:
            LOGGER.info("[Camera] get_camera_status: no proximity_manager, returning disabled")
            return {"enabled": False, "running": False}
        result = {
            "enabled": True,
            "running": bool(self._proximity_manager._running),
            "overlay": bool(self._proximity_manager._show_overlay),
        }
        LOGGER.info("[Camera] get_camera_status: %s", result)
        return result

    @pyqtSlot(result="QVariant")
    def enumerate_cameras(self) -> dict:
        """Probe camera indices 0-10, return list of available cameras."""
        LOGGER.info("[Camera] enumerate_cameras called")
        cameras = []
        try:
            import cv2
        except ImportError:
            return {"ok": False, "cameras": [], "message": "OpenCV not available"}

        active_id = config.CAMERA_DEVICE_ID
        active_running = (self._proximity_manager
                          and self._proximity_manager._running)

        for i in range(4):  # macOS/Windows rarely have more than 3 cameras
            # Skip probing the active camera if it's running (exclusive access on Windows)
            if i == active_id and active_running:
                cameras.append({"index": i, "name": f"Camera {i} (active)"})
                continue
            cap = cv2.VideoCapture(i)
            if cap.isOpened():
                # Some USB/external cameras need a few reads to warm up
                ret = False
                for _ in range(3):
                    ret, _ = cap.read()
                    if ret:
                        break
                if ret:
                    backend = cap.getBackendName() if hasattr(cap, 'getBackendName') else ""
                    label = f"Camera {i}"
                    if backend:
                        label += f" ({backend})"
                    cameras.append({"index": i, "name": label})
                cap.release()

        LOGGER.info("[Camera] enumerate_cameras result: %d cameras found, selected=%d", len(cameras), active_id)
        return {"ok": True, "cameras": cameras, "selected": active_id}

    @pyqtSlot(int, result="QVariant")
    def admin_select_camera(self, index: int) -> dict:
        """Select camera by device index. Restarts camera if running. Persisted."""
        index = max(0, min(10, index))
        config.CAMERA_DEVICE_ID = index
        self._save_setting("camera_device_id", str(index))

        if self._proximity_manager:
            was_running = self._proximity_manager._running
            self._proximity_manager._camera_id = index
            if was_running:
                self._proximity_manager.stop()
                # Delay restart to let old camera fully release
                import threading
                threading.Thread(
                    target=self._deferred_camera_restart,
                    daemon=True, name="camera-restart",
                ).start()

        LOGGER.info("[Admin] Camera selected: index %d", index)
        return {"ok": True, "index": index}

    def _deferred_camera_restart(self):
        """Wait briefly, then restart camera on main thread."""
        time.sleep(0.5)
        from PyQt6.QtCore import QMetaObject, Qt
        QMetaObject.invokeMethod(
            self, "_do_camera_restart",
            Qt.ConnectionType.QueuedConnection,
        )

    @pyqtSlot()
    def _do_camera_restart(self):
        """Restart camera on main thread after device change."""
        if self._proximity_manager and not self._proximity_manager._running:
            started = self._proximity_manager.start()
            LOGGER.info("[Admin] Camera restart after device change: %s",
                        "ok" if started else "failed")

    @pyqtSlot(result="QVariant")
    def toggle_camera(self) -> dict:
        """Toggle camera detection on/off at runtime (1s debounce)."""
        if not self._proximity_manager:
            return {"ok": False, "running": False, "message": "Camera not configured"}
        now = time.time()
        if now - getattr(self, '_camera_toggle_at', 0) < 1.0:
            running = self._proximity_manager._running
            return {"ok": False, "running": running, "message": "Please wait"}
        self._camera_toggle_at = now
        if self._proximity_manager._running:
            self._proximity_manager.stop()
            self._save_setting("camera_running", "False")
            LOGGER.info("[Camera] Toggled OFF by user")
            return {"ok": True, "running": False, "message": "Camera stopped"}
        started = self._proximity_manager.start()
        if started:
            self._save_setting("camera_running", "True")
            LOGGER.info("[Camera] Toggled ON by user")
        return {
            "ok": started,
            "running": started,
            "message": "Camera started" if started else "Camera failed to start",
        }

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
        """Clear ALL stations: cloud scans + roster + local data. Sets clear_epoch."""
        if not config.ADMIN_FEATURES_ENABLED:
            return {"ok": False, "message": "Admin features disabled"}
        if pin != config.ADMIN_PIN:
            return {"ok": False, "message": "Incorrect PIN"}

        # Auto-export backup before clearing
        backup_path = ""
        try:
            export_result = self._service.export_scans()
            if export_result.get("ok"):
                backup_path = export_result.get("absolutePath", "")
                LOGGER.info(f"Admin clear: backup exported to {backup_path}")
        except Exception as e:
            LOGGER.warning(f"Admin clear: backup export failed (continuing): {e}")

        # Clear cloud data (scans + roster + set clear_epoch)
        if self._sync_service:
            cloud_result = self._sync_service.clear_cloud_scans()
            if not cloud_result["ok"]:
                return {"ok": False, "message": f"Cloud clear failed: {cloud_result['message']}"}
            cloud_deleted = cloud_result.get("deleted", 0)
            clear_epoch = cloud_result.get("clear_epoch", "")
        else:
            cloud_deleted = 0
            clear_epoch = ""

        # Clear local scans
        try:
            local_count = self._service._db.clear_all_scans()
        except Exception as e:
            return {"ok": False, "message": f"Cloud cleared but local clear failed: {e}"}

        # Update local clear_epoch and send heartbeat immediately
        if clear_epoch:
            self._service._db.set_meta("last_clear_epoch", clear_epoch)
            if self._sync_service:
                station = self._service._db.get_station_name() or "Unknown"
                self._sync_service.send_heartbeat(station, clear_epoch, 0)
                # Schedule follow-up heartbeats to prevent going offline
                # (the clear truncates station_heartbeat; if periodic heartbeats
                # fail silently, the station goes stale after 120s)
                sync_svc = self._sync_service
                def _schedule_followup_heartbeat(delay_s, svc, sta, epoch):
                    def _fire():
                        # Read scan count on main thread (SQLite safe), then send in bg
                        count = self._service._db.count_scans_total()
                        threading.Thread(
                            target=lambda: svc.send_heartbeat(sta, epoch, count),
                            daemon=True, name="heartbeat-followup",
                        ).start()
                    QTimer.singleShot(delay_s * 1000, _fire)
                _schedule_followup_heartbeat(30, sync_svc, station, clear_epoch)
                _schedule_followup_heartbeat(90, sync_svc, station, clear_epoch)

        msg = f"Cleared {cloud_deleted} cloud + {local_count} local records + roster"
        LOGGER.info(f"Admin clear-all: {msg}")
        return {
            "ok": True,
            "cloud_deleted": cloud_deleted,
            "local_deleted": local_count,
            "backup_path": backup_path,
            "message": msg,
        }

    @pyqtSlot(str, result="QVariant")
    def admin_clear_station_data(self, pin: str) -> dict:
        """Clear THIS station only: local scans + this station's cloud scans."""
        if not config.ADMIN_FEATURES_ENABLED:
            return {"ok": False, "message": "Admin features disabled"}
        if pin != config.ADMIN_PIN:
            return {"ok": False, "message": "Incorrect PIN"}

        station = self._service._db.get_station_name() or "Unknown"

        # Auto-export backup
        backup_path = ""
        try:
            export_result = self._service.export_scans()
            if export_result.get("ok"):
                backup_path = export_result.get("absolutePath", "")
        except Exception as e:
            LOGGER.warning(f"Station clear: backup export failed (continuing): {e}")

        # Delete this station's scans from cloud
        cloud_deleted = 0
        if self._sync_service:
            cloud_result = self._sync_service.clear_station_scans(station)
            if not cloud_result.get("ok"):
                return {"ok": False, "message": f"Cloud clear failed: {cloud_result.get('message', 'unknown')}"}
            cloud_deleted = cloud_result.get("deleted", 0)

        # Clear local scans
        try:
            local_count = self._service._db.clear_all_scans()
        except Exception as e:
            return {"ok": False, "message": f"Cloud cleared but local clear failed: {e}"}

        msg = f"Cleared {cloud_deleted} cloud + {local_count} local records for {station}"
        LOGGER.info(f"Admin clear-station: {msg}")
        return {
            "ok": True,
            "cloud_deleted": cloud_deleted,
            "local_deleted": local_count,
            "backup_path": backup_path,
            "station": station,
            "message": msg,
        }

    @pyqtSlot(result="QVariant")
    def admin_get_station_status(self) -> dict:
        """Get all station statuses for the admin panel live view."""
        if not self._sync_service:
            return {"error": "Sync service not configured"}
        return self._sync_service.get_station_status()

    @pyqtSlot(result="QVariant")
    def admin_get_local_scan_count(self) -> dict:
        """Get local scan count for admin panel display."""
        try:
            count = self._service._db.count_scans_total()
            return {"count": count}
        except Exception:
            return {"count": 0}

    @pyqtSlot(result="QVariant")
    def admin_get_dashboard_refresh(self) -> dict:
        """Get current dashboard refresh interval from cloud."""
        if not self._sync_service:
            return {"ok": False, "interval": 60, "message": "Sync not configured"}
        ok, interval, message = self._sync_service.get_dashboard_refresh()
        return {"ok": ok, "interval": interval, "message": message}

    @pyqtSlot(int, result="QVariant")
    def admin_set_dashboard_refresh(self, interval: int) -> dict:
        """Set dashboard refresh interval on cloud."""
        if not self._sync_service:
            return {"ok": False, "message": "Sync not configured"}
        ok, message = self._sync_service.set_dashboard_refresh(interval)
        return {"ok": ok, "message": message}

    @pyqtSlot(result="QVariant")
    def admin_get_local_settings(self) -> dict:
        """Return all runtime-adjustable local settings."""
        LOGGER.info("[Admin] admin_get_local_settings called, camera_enabled=%s", self._proximity_manager is not None)
        camera_running = False
        camera_overlay = config.CAMERA_SHOW_OVERLAY
        greeting_cooldown = config.CAMERA_GREETING_COOLDOWN_SECONDS
        min_size_pct = config.CAMERA_MIN_SIZE_PCT
        absence_threshold = config.CAMERA_ABSENCE_THRESHOLD_SECONDS
        confirm_frames = config.CAMERA_CONFIRM_FRAMES
        haar_min_neighbors = config.CAMERA_HAAR_MIN_NEIGHBORS
        if self._proximity_manager:
            camera_running = bool(self._proximity_manager._running)
            camera_overlay = bool(self._proximity_manager._show_overlay)
            greeting_cooldown = self._proximity_manager._cooldown
            min_size_pct = self._proximity_manager._min_size_pct
            absence_threshold = self._proximity_manager._absence_threshold
            confirm_frames = self._proximity_manager._confirm_frames
            haar_min_neighbors = self._proximity_manager._haar_min_neighbors
        # Build dashboard URL from cloud API base
        dashboard_url = ""
        if config.CLOUD_API_URL:
            dashboard_url = config.CLOUD_API_URL.rstrip("/") + "/dashboard/"
        return {
            "duplicate_detection_enabled": config.DUPLICATE_BADGE_DETECTION_ENABLED,
            "duplicate_window": config.DUPLICATE_BADGE_TIME_WINDOW_SECONDS,
            "duplicate_action": config.DUPLICATE_BADGE_ACTION,
            "duplicate_alert_ms": config.DUPLICATE_BADGE_ALERT_DURATION_MS,
            "voice_enabled": self._voice_player.enabled if self._voice_player else False,
            "voice_volume": self._voice_player._volume if self._voice_player else 1.0,
            "camera_enabled": self._proximity_manager is not None,
            "camera_device_id": config.CAMERA_DEVICE_ID,
            "camera_running": camera_running,
            "camera_overlay": camera_overlay,
            "greeting_cooldown": greeting_cooldown,
            "min_size_pct": min_size_pct,
            "absence_threshold": absence_threshold,
            "confirm_frames": confirm_frames,
            "haar_min_neighbors": haar_min_neighbors,
            "scan_feedback_ms": config.SCAN_FEEDBACK_DURATION_MS,
            "connection_check_s": config.CONNECTION_CHECK_INTERVAL_MS / 1000,
            "dashboard_url": dashboard_url,
            "monitoring_mode": config.CLOUD_READ_ONLY,
            "live_sync_enabled": config.LIVE_SYNC_ENABLED and not config.CLOUD_READ_ONLY,
            "live_sync_window_minutes": config.LIVE_SYNC_DUP_WINDOW_MINUTES,
            "log_level": config.LOGGING_LEVEL,
            "console_logging": config.LOGGING_CONSOLE,
            "debug_panel": _debug_log_buffer in logging.getLogger().handlers,
            "defaults": self._config_defaults,
            "api_key_configured": bool(config.CLOUD_API_KEY),
            "api_key_masked": (config.CLOUD_API_KEY[:8] + "..." + config.CLOUD_API_KEY[-4:])
                if config.CLOUD_API_KEY and len(config.CLOUD_API_KEY) > 16
                else ("***" if config.CLOUD_API_KEY else ""),
        }

    # ------------------------------------------------------------------
    # All admin settings persist to SQLite via _save_setting()
    # ------------------------------------------------------------------

    @pyqtSlot(int, result="QVariant")
    def admin_set_duplicate_window(self, seconds: int) -> dict:
        """Set duplicate badge time window. Persisted across restarts."""
        seconds = max(1, min(86400, seconds))
        config.DUPLICATE_BADGE_TIME_WINDOW_SECONDS = seconds
        self._save_setting("duplicate_window", str(seconds))
        LOGGER.info("[Admin] Duplicate window set to %ds", seconds)
        return {"ok": True, "value": seconds}

    @pyqtSlot(str, result="QVariant")
    def admin_set_duplicate_action(self, action: str) -> dict:
        """Set duplicate badge action: block, warn, or silent. Persisted across restarts."""
        action = action.lower()
        if action not in ("block", "warn", "silent"):
            return {"ok": False, "message": f"Invalid action: {action}"}
        config.DUPLICATE_BADGE_ACTION = action
        self._save_setting("duplicate_action", action)
        LOGGER.info("[Admin] Duplicate action set to '%s'", action)
        return {"ok": True, "value": action}

    @pyqtSlot(bool, result="QVariant")
    def admin_set_duplicate_detection_enabled(self, enabled: bool) -> dict:
        """Enable/disable duplicate badge detection. Persisted across restarts."""
        config.DUPLICATE_BADGE_DETECTION_ENABLED = enabled
        self._save_setting("duplicate_detection_enabled", str(enabled))
        LOGGER.info("[Admin] Duplicate detection %s", "enabled" if enabled else "disabled")
        return {"ok": True, "value": enabled}

    @pyqtSlot(int, result="QVariant")
    def admin_set_duplicate_alert_duration(self, ms: int) -> dict:
        """Set duplicate alert display duration in ms. Persisted across restarts."""
        ms = max(500, min(30000, ms))
        config.DUPLICATE_BADGE_ALERT_DURATION_MS = ms
        self._save_setting("duplicate_alert_ms", str(ms))
        LOGGER.info("[Admin] Duplicate alert duration set to %dms", ms)
        return {"ok": True, "value": ms}

    @pyqtSlot(bool, result="QVariant")
    def admin_set_voice_enabled(self, enabled: bool) -> dict:
        """Enable/disable voice confirmation. Persisted across restarts."""
        if not self._voice_player:
            return {"ok": False, "message": "Voice not configured"}
        self._voice_player.enabled = enabled
        self._save_setting("voice_enabled", str(enabled))
        LOGGER.info("[Admin] Voice %s", "enabled" if enabled else "disabled")
        return {"ok": True, "enabled": enabled}

    @pyqtSlot(float, result="QVariant")
    def admin_set_voice_volume(self, volume: float) -> dict:
        """Set voice volume 0.0-1.0. Persisted across restarts."""
        if not self._voice_player:
            return {"ok": False, "message": "Voice not configured"}
        volume = max(0.0, min(1.0, volume))
        self._voice_player._volume = volume
        self._voice_player._audio_output.setVolume(volume)
        # Also update greeting player volume if camera proximity is active
        if self._proximity_manager and hasattr(self._proximity_manager, '_greeting_player'):
            gp = self._proximity_manager._greeting_player
            if gp and hasattr(gp, '_audio_output') and gp._audio_output:
                gp._volume = volume
                gp._audio_output.setVolume(volume)
        self._save_setting("voice_volume", str(round(volume, 2)))
        LOGGER.info("[Admin] Voice volume set to %.0f%%", volume * 100)
        return {"ok": True, "volume": volume}

    def _save_setting(self, key: str, value: str) -> None:
        """Persist a setting to the local SQLite key-value store."""
        try:
            self._service._db.set_meta(f"setting:{key}", value)
            LOGGER.info("[Admin] Saved setting:%s = %s", key, value)
        except Exception as exc:
            LOGGER.warning("[Admin] Failed to persist setting %s: %s", key, exc)

    def load_saved_settings(self) -> None:
        """Load persisted settings from SQLite and override config defaults."""
        db = self._service._db
        count = 0
        # Scanning settings
        v = db.get_meta("setting:duplicate_detection_enabled")
        if v is not None:
            config.DUPLICATE_BADGE_DETECTION_ENABLED = v.lower() in ("true", "1")
            count += 1
        v = db.get_meta("setting:duplicate_window")
        if v is not None:
            try:
                config.DUPLICATE_BADGE_TIME_WINDOW_SECONDS = max(1, min(86400, int(v)))
                count += 1
            except ValueError:
                pass
        v = db.get_meta("setting:duplicate_action")
        if v is not None and v in ("block", "warn", "silent"):
            config.DUPLICATE_BADGE_ACTION = v
            count += 1
        v = db.get_meta("setting:duplicate_alert_ms")
        if v is not None:
            try:
                config.DUPLICATE_BADGE_ALERT_DURATION_MS = max(500, min(30000, int(v)))
                count += 1
            except ValueError:
                pass
        # Audio settings — apply directly to VoicePlayer
        v = db.get_meta("setting:voice_enabled")
        if v is not None and self._voice_player:
            self._voice_player.enabled = v.lower() in ("true", "1")
            count += 1
        v = db.get_meta("setting:voice_volume")
        if v is not None and self._voice_player:
            try:
                vol = max(0.0, min(1.0, float(v)))
                self._voice_player._volume = vol
                self._voice_player._audio_output.setVolume(vol)
                count += 1
            except ValueError:
                pass
        # Camera settings
        v = db.get_meta("setting:camera_device_id")
        if v is not None:
            try:
                config.CAMERA_DEVICE_ID = max(0, min(10, int(v)))
                count += 1
            except ValueError:
                pass
        v = db.get_meta("setting:camera_overlay")
        if v is not None:
            config.CAMERA_SHOW_OVERLAY = v.lower() in ("true", "1")
            count += 1
        v = db.get_meta("setting:greeting_cooldown")
        if v is not None:
            try:
                config.CAMERA_GREETING_COOLDOWN_SECONDS = max(5.0, min(300.0, float(v)))
                count += 1
            except ValueError:
                pass
        v = db.get_meta("setting:scan_feedback_ms")
        if v is not None:
            try:
                config.SCAN_FEEDBACK_DURATION_MS = max(500, min(30000, int(v)))
                count += 1
            except ValueError:
                pass
        v = db.get_meta("setting:connection_check_s")
        if v is not None:
            try:
                config.CONNECTION_CHECK_INTERVAL_MS = max(0, int(float(v) * 1000))
                count += 1
            except ValueError:
                pass
        v = db.get_meta("setting:min_size_pct")
        if v is not None:
            try:
                config.CAMERA_MIN_SIZE_PCT = max(0.05, min(0.80, float(v)))
                count += 1
            except ValueError:
                pass
        v = db.get_meta("setting:absence_threshold")
        if v is not None:
            try:
                config.CAMERA_ABSENCE_THRESHOLD_SECONDS = max(1.0, min(30.0, float(v)))
                count += 1
            except ValueError:
                pass
        v = db.get_meta("setting:confirm_frames")
        if v is not None:
            try:
                config.CAMERA_CONFIRM_FRAMES = max(1, min(15, int(v)))
                count += 1
            except ValueError:
                pass
        v = db.get_meta("setting:haar_min_neighbors")
        if v is not None:
            try:
                config.CAMERA_HAAR_MIN_NEIGHBORS = max(2, min(10, int(v)))
                count += 1
            except ValueError:
                pass
        # Cloud sync settings
        v = db.get_meta("setting:cloud_read_only")
        if v is not None:
            config.CLOUD_READ_ONLY = v.lower() in ("true", "1")
            count += 1
        v = db.get_meta("setting:live_sync_enabled")
        if v is not None:
            config.LIVE_SYNC_ENABLED = v.lower() in ("true", "1")
            count += 1
        v = db.get_meta("setting:live_sync_window_minutes")
        if v is not None:
            try:
                config.LIVE_SYNC_DUP_WINDOW_MINUTES = max(1, min(1440, int(v)))
                count += 1
            except (ValueError, TypeError):
                pass
        # API key from SQLite (Option B: allows setting key without .env)
        if not config.CLOUD_API_KEY:
            v = db.get_meta("setting:cloud_api_key")
            if v:
                config.CLOUD_API_KEY = v
                LOGGER.info("[Admin] API key loaded from local database")
                count += 1
        # Debug settings
        v = db.get_meta("setting:log_level")
        if v is not None and v.upper() in ("DEBUG", "INFO", "WARNING", "ERROR"):
            config.LOGGING_LEVEL = v.upper()
            numeric = getattr(logging, v.upper(), logging.INFO)
            root = logging.getLogger()
            root.setLevel(min(numeric, logging.DEBUG))
            for handler in root.handlers:
                if handler is _debug_log_buffer:
                    continue
                handler.setLevel(numeric)
            count += 1
        v = db.get_meta("setting:console_logging")
        if v is not None:
            want_console = v.lower() in ("true", "1")
            config.LOGGING_CONSOLE = want_console
            root = logging.getLogger()
            has_console = any(
                isinstance(h, logging.StreamHandler) and not isinstance(h, logging.handlers.RotatingFileHandler)
                for h in root.handlers
            )
            if want_console and not has_console:
                import sys as _sys
                console = logging.StreamHandler(_sys.stderr)
                console.setLevel(getattr(logging, config.LOGGING_LEVEL, logging.INFO))
                console.setFormatter(logging.Formatter('%(asctime)s [%(levelname)-8s] %(name)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S'))
                root.addHandler(console)
            elif not want_console and has_console:
                for h in list(root.handlers):
                    if isinstance(h, logging.StreamHandler) and not isinstance(h, logging.handlers.RotatingFileHandler):
                        root.removeHandler(h)
            count += 1
        v = db.get_meta("setting:debug_panel")
        if v is not None and v.lower() in ("true", "1"):
            root = logging.getLogger()
            if _debug_log_buffer not in root.handlers:
                fmt = logging.Formatter('%(asctime)s [%(levelname)-5s] %(name)s - %(message)s', datefmt='%H:%M:%S')
                _debug_log_buffer.setFormatter(fmt)
                _debug_log_buffer.setLevel(logging.DEBUG)
                root.addHandler(_debug_log_buffer)
            config._DEBUG_PANEL_ACTIVE = True
            count += 1
        if count:
            LOGGER.info("[Admin] Loaded %d saved setting(s) from database", count)

    @pyqtSlot(bool, result="QVariant")
    def admin_set_camera_overlay(self, enabled: bool) -> dict:
        """Toggle camera overlay between preview (True) and icon (False). Persisted."""
        if not self._proximity_manager:
            return {"ok": False, "message": "Camera not configured"}
        self._proximity_manager.set_overlay_mode(enabled)
        config.CAMERA_SHOW_OVERLAY = enabled
        self._save_setting("camera_overlay", str(enabled))
        mode = "preview" if enabled else "icon"
        LOGGER.info("[Admin] Camera overlay mode: %s", mode)
        return {"ok": True, "enabled": enabled}

    @pyqtSlot(int, result="QVariant")
    def admin_set_greeting_cooldown(self, seconds: int) -> dict:
        """Set greeting cooldown in seconds. Persisted across restarts."""
        if not self._proximity_manager:
            return {"ok": False, "message": "Camera not configured"}
        seconds = max(5, min(300, seconds))
        self._proximity_manager._cooldown = float(seconds)
        config.CAMERA_GREETING_COOLDOWN_SECONDS = float(seconds)
        self._save_setting("greeting_cooldown", str(seconds))
        LOGGER.info("[Admin] Greeting cooldown set to %ds", seconds)
        return {"ok": True, "value": seconds}

    @pyqtSlot(int, result="QVariant")
    def admin_set_scan_feedback_duration(self, ms: int) -> dict:
        """Set scan feedback display duration in ms. Persisted across restarts."""
        ms = max(500, min(30000, ms))
        config.SCAN_FEEDBACK_DURATION_MS = ms
        self._save_setting("scan_feedback_ms", str(ms))
        LOGGER.info("[Admin] Scan feedback duration set to %dms", ms)
        return {"ok": True, "value": ms}

    @pyqtSlot(float, result="QVariant")
    def admin_set_connection_check(self, seconds: float) -> dict:
        """Set connection check interval in seconds. Persisted across restarts."""
        seconds = max(0, min(600, seconds))
        config.CONNECTION_CHECK_INTERVAL_MS = int(seconds * 1000)
        self._save_setting("connection_check_s", str(seconds))
        LOGGER.info("[Admin] Connection check interval set to %.0fs", seconds)
        return {"ok": True, "value": seconds}

    @pyqtSlot(bool, result="QVariant")
    def admin_set_monitoring_mode(self, enabled: bool) -> dict:
        """Toggle monitoring (read-only) mode. Persisted across restarts."""
        config.CLOUD_READ_ONLY = enabled
        self._save_setting("cloud_read_only", str(enabled))
        # Auto-disable Live Sync when monitoring mode is on
        if enabled and config.LIVE_SYNC_ENABLED:
            config.LIVE_SYNC_ENABLED = False
            self._save_setting("live_sync_enabled", "False")
            LOGGER.info("[Admin] Live Sync auto-disabled (monitoring mode on)")
        LOGGER.info("[Admin] Monitoring mode %s", "enabled" if enabled else "disabled")
        return {"ok": True, "value": enabled}

    @pyqtSlot(bool, result="QVariant")
    def admin_set_live_sync(self, enabled: bool) -> dict:
        """Toggle Live Sync mode. Persisted across restarts."""
        if enabled and config.CLOUD_READ_ONLY:
            return {"ok": False, "message": "Cannot enable Live Sync in monitoring mode"}
        config.LIVE_SYNC_ENABLED = enabled
        self._save_setting("live_sync_enabled", str(enabled))
        LOGGER.info("[Admin] Live Sync %s", "enabled" if enabled else "disabled")
        return {"ok": True, "value": enabled}

    @pyqtSlot(int, result="QVariant")
    def admin_set_live_sync_window(self, minutes: int) -> dict:
        """Set Live Sync cross-station duplicate window in minutes. Persisted."""
        minutes = max(1, min(1440, minutes))
        config.LIVE_SYNC_DUP_WINDOW_MINUTES = minutes
        self._save_setting("live_sync_window_minutes", str(minutes))
        LOGGER.info("[Admin] Live Sync window set to %dm", minutes)
        return {"ok": True, "value": minutes}

    @pyqtSlot(str, result="QVariant")
    def admin_set_log_level(self, level: str) -> dict:
        """Change runtime log level. Persisted across restarts."""
        level = level.upper()
        if level not in ("DEBUG", "INFO", "WARNING", "ERROR"):
            return {"ok": False, "message": "Invalid level"}
        config.LOGGING_LEVEL = level
        numeric = getattr(logging, level, logging.INFO)
        root = logging.getLogger()
        root.setLevel(min(numeric, logging.DEBUG))  # root must pass all levels for debug buffer
        for handler in root.handlers:
            if handler is _debug_log_buffer:
                continue  # debug buffer always captures at DEBUG level
            handler.setLevel(numeric)
        self._save_setting("log_level", level)
        LOGGER.info("[Admin] Log level set to %s", level)
        return {"ok": True, "value": level}

    @pyqtSlot(bool, result="QVariant")
    def admin_set_console_logging(self, enabled: bool) -> dict:
        """Toggle console (stderr) logging at runtime. Persisted."""
        config.LOGGING_CONSOLE = enabled
        root = logging.getLogger()
        # Remove or add console handler
        for handler in list(root.handlers):
            if isinstance(handler, logging.StreamHandler) and not isinstance(handler, logging.handlers.RotatingFileHandler):
                if not enabled:
                    root.removeHandler(handler)
        if enabled:
            has_console = any(
                isinstance(h, logging.StreamHandler) and not isinstance(h, logging.handlers.RotatingFileHandler)
                for h in root.handlers
            )
            if not has_console:
                import sys as _sys
                console = logging.StreamHandler(_sys.stderr)
                console.setLevel(getattr(logging, config.LOGGING_LEVEL, logging.INFO))
                log_format = '%(asctime)s [%(levelname)-8s] %(name)s - %(message)s'
                console.setFormatter(logging.Formatter(log_format, datefmt='%Y-%m-%d %H:%M:%S'))
                root.addHandler(console)
        self._save_setting("console_logging", str(enabled))
        LOGGER.info("[Admin] Console logging %s", "enabled" if enabled else "disabled")
        return {"ok": True, "enabled": enabled}

    @pyqtSlot(bool, result="QVariant")
    def admin_set_debug_panel(self, enabled: bool) -> dict:
        """Toggle debug panel visibility. When on, attaches log buffer to root logger."""
        root = logging.getLogger()
        if enabled:
            if _debug_log_buffer not in root.handlers:
                fmt = logging.Formatter('%(asctime)s [%(levelname)-5s] %(name)s - %(message)s', datefmt='%H:%M:%S')
                _debug_log_buffer.setFormatter(fmt)
                _debug_log_buffer.setLevel(logging.DEBUG)
                root.addHandler(_debug_log_buffer)
        else:
            if _debug_log_buffer in root.handlers:
                root.removeHandler(_debug_log_buffer)
        config._DEBUG_PANEL_ACTIVE = enabled
        self._save_setting("debug_panel", str(enabled))
        LOGGER.info("[Admin] Debug panel %s", "enabled" if enabled else "disabled")
        return {"ok": True, "enabled": enabled}

    @pyqtSlot(int, result="QVariant")
    def admin_get_debug_logs(self, since_cursor: int) -> dict:
        """Poll new log lines since cursor. Returns {lines: [...], cursor: int}."""
        return _debug_log_buffer.get_lines_since(since_cursor)

    @pyqtSlot(str, result="QVariant")
    def admin_set_api_key(self, key: str) -> dict:
        """Set or update the cloud API key at runtime. Persisted across restarts.

        This allows customers to enter their license key from the admin panel
        without editing .env files. The key is stored in local SQLite and
        takes effect immediately (no restart needed).
        """
        key = key.strip()
        if not key:
            return {"ok": False, "message": "API key cannot be empty"}

        # Update runtime config
        old_key = config.CLOUD_API_KEY
        config.CLOUD_API_KEY = key

        # Persist to SQLite
        self._save_setting("cloud_api_key", key)

        # Reinitialise sync service if it wasn't running (first-time key entry)
        if not old_key and self._sync_service is None:
            try:
                self._sync_service = SyncService(
                    db=self._service._db,
                    api_url=config.CLOUD_API_URL,
                    api_key=key,
                    batch_size=config.CLOUD_SYNC_BATCH_SIZE,
                    connection_timeout=config.CONNECTION_CHECK_TIMEOUT_SECONDS,
                )
                self._service.set_sync_service(self._sync_service)
                LOGGER.info("[Admin] Sync service initialised with new API key")
            except Exception as exc:
                LOGGER.warning("[Admin] Failed to init sync service: %s", exc)
        elif self._sync_service:
            # Update existing sync service's API key
            self._sync_service._api_key = key
            LOGGER.info("[Admin] Sync service API key updated")

        LOGGER.info("[Admin] API key %s", "updated" if old_key else "set for first time")
        return {
            "ok": True,
            "message": "API key saved. Cloud features are now active." if not old_key
                else "API key updated.",
            "had_previous": bool(old_key),
        }

    @pyqtSlot(result="QVariant")
    def admin_get_api_key_status(self) -> dict:
        """Return whether an API key is configured (without exposing the key itself)."""
        key = config.CLOUD_API_KEY
        if not key:
            return {"configured": False, "masked": "", "message": "No API key set — running in local-only mode"}
        # Show first 8 and last 4 chars, mask the rest
        if len(key) > 16:
            masked = key[:8] + "..." + key[-4:]
        else:
            masked = key[:4] + "..." + key[-2:] if len(key) > 6 else "***"
        return {"configured": True, "masked": masked, "message": "Cloud features active"}

    @pyqtSlot(float, result="QVariant")
    def admin_set_min_size_pct(self, pct: float) -> dict:
        """Set camera min face size percentage. Persisted across restarts."""
        if not self._proximity_manager:
            return {"ok": False, "message": "Camera not configured"}
        pct = max(0.05, min(0.80, pct))
        self._proximity_manager._min_size_pct = pct
        # Also update detector if running
        if self._proximity_manager._detector:
            self._proximity_manager._detector.min_size_pct = pct
        config.CAMERA_MIN_SIZE_PCT = pct
        self._save_setting("min_size_pct", str(round(pct, 2)))
        LOGGER.info("[Admin] Min face size set to %.0f%%", pct * 100)
        return {"ok": True, "value": pct}

    @pyqtSlot(float, result="QVariant")
    def admin_set_absence_threshold(self, seconds: float) -> dict:
        """Set camera absence threshold in seconds. Persisted across restarts."""
        if not self._proximity_manager:
            return {"ok": False, "message": "Camera not configured"}
        seconds = max(1.0, min(30.0, seconds))
        self._proximity_manager._absence_threshold = seconds
        # Also update detector if running
        if self._proximity_manager._detector:
            self._proximity_manager._detector.absence_threshold = seconds
        config.CAMERA_ABSENCE_THRESHOLD_SECONDS = seconds
        self._save_setting("absence_threshold", str(round(seconds, 1)))
        LOGGER.info("[Admin] Absence threshold set to %.1fs", seconds)
        return {"ok": True, "value": seconds}

    @pyqtSlot(int, result="QVariant")
    def admin_set_confirm_frames(self, frames: int) -> dict:
        """Set confirm frames required before greeting. Persisted across restarts."""
        if not self._proximity_manager:
            return {"ok": False, "message": "Camera not configured"}
        frames = max(1, min(15, frames))
        self._proximity_manager._confirm_frames = frames
        if self._proximity_manager._detector:
            self._proximity_manager._detector.confirm_frames = frames
        config.CAMERA_CONFIRM_FRAMES = frames
        self._save_setting("confirm_frames", str(frames))
        LOGGER.info("[Admin] Confirm frames set to %d", frames)
        return {"ok": True, "value": frames}

    @pyqtSlot(int, result="QVariant")
    def admin_set_haar_min_neighbors(self, neighbors: int) -> dict:
        """Set Haar cascade strictness (minNeighbors). Persisted across restarts."""
        if not self._proximity_manager:
            return {"ok": False, "message": "Camera not configured"}
        neighbors = max(2, min(10, neighbors))
        self._proximity_manager._haar_min_neighbors = neighbors
        if self._proximity_manager._detector:
            self._proximity_manager._detector.haar_min_neighbors = neighbors
        config.CAMERA_HAAR_MIN_NEIGHBORS = neighbors
        self._save_setting("haar_min_neighbors", str(neighbors))
        LOGGER.info("[Admin] Haar min neighbors set to %d", neighbors)
        return {"ok": True, "value": neighbors}

    @pyqtSlot(result="QVariant")
    def admin_reset_camera_settings(self) -> dict:
        """Reset all camera settings to .env defaults. Clears DB overrides."""
        db = self._service._db
        camera_keys = [
            "camera_device_id", "camera_overlay", "greeting_cooldown",
            "min_size_pct", "absence_threshold", "confirm_frames",
            "haar_min_neighbors",
        ]
        for key in camera_keys:
            db._connection.execute("DELETE FROM roster_meta WHERE key = ?", (f"setting:{key}",))
        db._connection.commit()

        # Restore from defaults snapshot
        d = self._config_defaults
        config.CAMERA_GREETING_COOLDOWN_SECONDS = d["greeting_cooldown"]
        config.CAMERA_MIN_SIZE_PCT = d["min_size_pct"]
        config.CAMERA_ABSENCE_THRESHOLD_SECONDS = d["absence_threshold"]
        config.CAMERA_CONFIRM_FRAMES = d["confirm_frames"]
        config.CAMERA_HAAR_MIN_NEIGHBORS = d["haar_min_neighbors"]
        config.CAMERA_SHOW_OVERLAY = False  # production default
        config.CAMERA_DEVICE_ID = d.get("camera_device_id", 0)

        # Push to live manager/detector
        if self._proximity_manager:
            self._proximity_manager._camera_id = config.CAMERA_DEVICE_ID
            self._proximity_manager._cooldown = d["greeting_cooldown"]
            self._proximity_manager._min_size_pct = d["min_size_pct"]
            self._proximity_manager._absence_threshold = d["absence_threshold"]
            self._proximity_manager._confirm_frames = d["confirm_frames"]
            self._proximity_manager._haar_min_neighbors = d["haar_min_neighbors"]
            self._proximity_manager.set_overlay_mode(False)
            det = self._proximity_manager._detector
            if det:
                det.cooldown = d["greeting_cooldown"]
                det.min_size_pct = d["min_size_pct"]
                det.absence_threshold = d["absence_threshold"]
                det.confirm_frames = d["confirm_frames"]
                det.haar_min_neighbors = d["haar_min_neighbors"]

        LOGGER.info("[Admin] Camera settings reset to defaults")
        return {"ok": True}

    @pyqtSlot()
    def _handle_clear_epoch_and_heartbeat_slot(self) -> None:
        """Check clear_epoch and send heartbeat. Runs on MAIN thread (SQLite safe)."""
        if not self._sync_service:
            return
        # Read-only mode: skip all outgoing operations and epoch sync
        import config
        if config.CLOUD_READ_ONLY:
            return

        cloud_epoch = self._sync_service.last_clear_epoch
        local_epoch = self._service._db.get_meta("last_clear_epoch")

        # First time: initialize local epoch to cloud value (no clear needed)
        if local_epoch is None and cloud_epoch:
            self._service._db.set_meta("last_clear_epoch", cloud_epoch)
            LOGGER.info("[Sync] First connection — initialized clear_epoch to %s", cloud_epoch)
            local_epoch = cloud_epoch
        # Existing station: detect remote clear
        elif cloud_epoch and local_epoch and cloud_epoch != local_epoch:
            LOGGER.info("[Sync] Remote clear detected (cloud=%s, local=%s) — exporting + clearing", cloud_epoch, local_epoch)
            # Pause auto-sync to prevent re-uploading stale data
            if self._auto_sync_manager:
                self._auto_sync_manager.stop()
                LOGGER.info("[Sync] Auto-sync paused during remote clear")
            try:
                self._service.export_scans()
                LOGGER.info("[Sync] Backup exported before remote clear")
            except Exception as e:
                LOGGER.warning("[Sync] Backup export failed: %s", e)
            self._service._db.clear_all_scans()
            self._service._db.set_meta("last_clear_epoch", cloud_epoch)
            LOGGER.info("[Sync] Local data cleared after remote clear")
            # Refresh UI: reset counters and show alert modal
            self._notify_remote_clear()
            # Resume auto-sync
            if self._auto_sync_manager:
                self._auto_sync_manager.start()
                LOGGER.info("[Sync] Auto-sync resumed after remote clear")

        # Send heartbeat (in background to avoid blocking main thread)
        station = self._service._db.get_station_name() or "Unknown"
        scan_count = self._service._db.count_scans_total()
        current_epoch = self._service._db.get_meta("last_clear_epoch")
        sync_svc = self._sync_service

        def _send():
            sync_svc.send_heartbeat(station, current_epoch, scan_count)

        threading.Thread(target=_send, daemon=True, name="heartbeat").start()

    def _notify_remote_clear(self) -> None:
        """Show alert modal and refresh UI after remote clear detected."""
        view = self._window.centralWidget() if self._window else None
        if not view:
            return
        script = """
        (function() {
            // Reset all counters to 0
            var ids = ['total-count', 'matched-count', 'unmatched-count',
                       'sync-pending', 'sync-synced', 'sync-failed',
                       'total-scanned'];
            ids.forEach(function(id) {
                var el = document.getElementById(id);
                if (el) el.textContent = '0';
            });
            // Clear recent scan history list
            var historyEl = document.getElementById('scan-history-list');
            if (historyEl) historyEl.innerHTML = '';
            // Reset live feedback
            var feedbackEl = document.getElementById('live-feedback');
            if (feedbackEl) {
                feedbackEl.textContent = 'Ready to scan...';
                feedbackEl.style.color = 'var(--deloitte-green)';
            }
            // Show alert modal
            var overlay = document.createElement('div');
            overlay.id = 'remote-clear-overlay';
            overlay.style.cssText = 'position:fixed;top:0;left:0;width:100%;height:100%;' +
                'background:rgba(0,0,0,0.6);display:flex;align-items:center;justify-content:center;z-index:9999;';
            var box = document.createElement('div');
            box.style.cssText = 'background:#fff;border-radius:12px;padding:32px 40px;text-align:center;' +
                'max-width:420px;box-shadow:0 8px 32px rgba(0,0,0,0.3);';
            box.innerHTML = '<div style="font-size:2.5rem;margin-bottom:12px;">&#9888;</div>' +
                '<h3 style="margin:0 0 12px;color:#333;font-size:1.3rem;">Data Cleared by Admin</h3>' +
                '<p style="margin:0 0 20px;color:#666;font-size:0.95rem;">' +
                'All station data has been cleared from another station.<br>' +
                'Local backup has been exported to the exports folder.</p>' +
                '<div style="display:flex;gap:12px;justify-content:center;">' +
                '<button onclick="document.getElementById(\\'remote-clear-overlay\\').remove()" ' +
                'style="background:#86bc25;color:#fff;border:none;padding:10px 32px;border-radius:6px;' +
                'font-size:1rem;font-weight:600;cursor:pointer;">OK</button>' +
                '<button onclick="document.getElementById(\\'remote-clear-overlay\\').remove();' +
                'if(window.qt&&window.qt.webChannelTransport){new QWebChannel(qt.webChannelTransport,' +
                'function(ch){ch.objects.api.close_window()})}" ' +
                'style="background:#e8443a;color:#fff;border:none;padding:10px 32px;border-radius:6px;' +
                'font-size:1rem;font-weight:600;cursor:pointer;">Close App</button>' +
                '</div>';
            overlay.appendChild(box);
            document.body.appendChild(overlay);
            console.log('[RemoteClear] UI reset and alert shown');
        })();
        """
        view.page().runJavaScript(script)
        LOGGER.info("[Sync] Remote clear alert shown to user")

    @pyqtSlot(str, result="QVariant")
    def admin_rename_station(self, new_name: str) -> dict:
        """Rename this station. Requires admin PIN already verified."""
        new_name = new_name.strip()
        if not new_name:
            return {"ok": False, "message": "Station name cannot be empty"}
        old_name = self._service._db.get_station_name() or "Unknown"
        self._service._db.set_station_name(new_name)
        updated = self._service._db.rename_station_scans(old_name, new_name)
        LOGGER.info("[Admin] Station renamed: '%s' → '%s' (%d local scans updated)", old_name, new_name, updated)
        # Sync rename to cloud in background
        import threading
        def _cloud_rename():
            try:
                import requests
                resp = requests.put(
                    f"{config.CLOUD_API_URL}/v1/stations/rename",
                    json={"old_name": old_name, "new_name": new_name},
                    headers={"x-api-key": config.CLOUD_API_KEY},
                    timeout=10,
                )
                data = resp.json()
                if data.get("ok"):
                    LOGGER.info("[Admin] Cloud station rename: %d scans updated", data.get("scans_updated", 0))
                else:
                    LOGGER.warning("[Admin] Cloud station rename failed: %s", data.get("error", "unknown"))
            except Exception as e:
                LOGGER.warning("[Admin] Cloud station rename error: %s", e)
        threading.Thread(target=_cloud_rename, daemon=True).start()
        return {"ok": True, "message": f"Station renamed to '{new_name}'", "old_name": old_name, "new_name": new_name}

    @pyqtSlot(result="QVariant")
    def get_voice_status(self) -> dict:
        """Return voice confirmation feature status."""
        if not self._voice_player:
            return {"enabled": False}
        return {"enabled": self._voice_player.enabled}

    @pyqtSlot(result="QVariant")
    def toggle_voice(self) -> dict:
        """Toggle voice confirmation on/off at runtime."""
        if not self._voice_player:
            return {"ok": False, "enabled": False, "message": "Voice not configured"}
        self._voice_player.enabled = not self._voice_player.enabled
        LOGGER.info("[Voice] Toggled %s by user", "ON" if self._voice_player.enabled else "OFF")
        return {"ok": True, "enabled": self._voice_player.enabled}

    @pyqtSlot(str, result="QVariant")
    def search_employee(self, query: str) -> dict:
        """Search employees by email prefix or name for manual lookup."""
        results = self._service.search_employee(query)
        return {"ok": True, "results": results}

    @pyqtSlot(str, str, result="QVariant")
    def submit_manual_scan(self, original_query: str, legacy_id: str = "") -> dict:
        """Record a scan via manual employee lookup (forgot-badge flow).

        original_query: what the user actually typed (stored as scan value)
        legacy_id: matched employee's ID (used for employee lookup, may be empty)
        """
        # Use legacy_id as badge value when employee was selected from lookup
        # (original_query is just the search text, not the actual badge)
        badge_value = legacy_id if legacy_id else original_query
        result = self._service.register_scan(
            badge_value, scan_source="lookup" if legacy_id else "manual",
            lookup_legacy_id=legacy_id or None,
        )

        # Play voice confirmation on successful match
        if self._voice_player and result.get("matched") and not result.get("is_duplicate"):
            if self._proximity_manager:
                self._proximity_manager.notify_voice_playing()
            self._voice_player.play_random()

        if self._auto_sync_manager:
            self._auto_sync_manager.on_scan()

        if self._proximity_manager:
            self._proximity_manager.notify_scan_activity()

        return result

    @pyqtSlot(str)
    def open_export_folder(self, file_path: str) -> None:
        """Open file manager with the exported file selected."""
        import subprocess
        import platform
        try:
            if platform.system() == "Darwin":
                subprocess.Popen(["open", "-R", file_path])
            else:
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

    # Show roster error to user if bootstrap detected issues (e.g. duplicate Legacy IDs)
    if getattr(service, '_roster_error', None):
        QMessageBox.warning(
            None,
            "Roster Error",
            f"Employee roster has issues:\n\n{service._roster_error}\n\n"
            "The application will continue but roster data may be incomplete.",
        )

    # Initialize sync service for cloud integration (only if API key is available)
    sync_service = None
    dashboard_service = None
    if config.CLOUD_API_KEY:
        sync_service = SyncService(
            db=service._db,
            api_url=config.CLOUD_API_URL,
            api_key=config.CLOUD_API_KEY,
            batch_size=config.CLOUD_SYNC_BATCH_SIZE,
            connection_timeout=config.CONNECTION_CHECK_TIMEOUT_SECONDS,
        )
        # Wire SyncService into AttendanceService for Live Sync (#54)
        service.set_sync_service(sync_service)
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
    else:
        LOGGER.info("No API key — cloud sync and dashboard disabled (local-only mode)")

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
        # Load persisted admin settings (SQLite overrides .env defaults)
        api_object.load_saved_settings()

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
                    min_size_pct=config.CAMERA_MIN_SIZE_PCT,
                    haar_min_neighbors=config.CAMERA_HAAR_MIN_NEIGHBORS,
                    detection_scale=config.CAMERA_DETECTION_SCALE,
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
                # Respect saved camera state — if user turned it off, don't auto-start
                _api = getattr(window, '_api', None)
                _saved_off = False
                if isinstance(_api, Api):
                    v = _api._service._db.get_meta("setting:camera_running")
                    _saved_off = (v is not None and v.lower() in ("false", "0"))
                if _saved_off:
                    LOGGER.info("[Proximity] Camera kept OFF (saved preference)")
                else:
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

    # Prevent Windows screen lock / display sleep while kiosk is running
    _keep_awake_set = False
    if sys.platform == "win32":
        try:
            import ctypes
            ES_CONTINUOUS = 0x80000000
            ES_SYSTEM_REQUIRED = 0x00000001
            ES_DISPLAY_REQUIRED = 0x00000002
            ctypes.windll.kernel32.SetThreadExecutionState(
                ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED
            )
            _keep_awake_set = True
            LOGGER.info("Screen lock prevention enabled (SetThreadExecutionState)")
        except Exception as exc:
            LOGGER.warning("Failed to prevent screen lock: %s", exc)

    try:
        sys.exit(app.exec())
    finally:
        if _keep_awake_set:
            try:
                ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS)
                LOGGER.info("Screen lock prevention released")
            except Exception:
                pass
        if proximity_manager:
            proximity_manager.stop()
        service.close()


if __name__ == '__main__':
    main()
