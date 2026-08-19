"""Cloud sync service for uploading attendance scans."""

from __future__ import annotations

import itertools
import json
import logging
import queue
import requests
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Tuple
from datetime import datetime, timezone

from database import DatabaseManager, ScanRecord

LOGGER = logging.getLogger(__name__)


def _is_retryable_error(exception: Exception) -> bool:
    """
    Determine if an error is transient and should trigger a retry.

    Retryable errors:
    - Connection timeouts
    - Connection errors (temporary network issues)
    - Server errors (5xx)

    Non-retryable errors:
    - Authentication errors (4xx except 429)
    - Bad request (4xx)
    """
    if isinstance(exception, requests.exceptions.Timeout):
        return True
    if isinstance(exception, requests.exceptions.ConnectionError):
        return True
    return False


class BackgroundSyncCoordinator:
    """Bounded FIFO coordinator that runs network-only jobs on one reused worker thread.

    A job is any no-argument callable. Jobs must never touch SQLite — this class has
    no database access itself, and the reused worker thread is the only thread that
    ever executes a job, so callers must not pass in work that opens or uses a
    DatabaseManager/sqlite3 connection. Result/error callbacks are invoked on that
    same worker thread; callers that need to touch SQLite or Qt state from a callback
    must marshal it back to their own owning thread themselves (e.g. via Qt's queued
    signal/invokeMethod) — that marshalling is intentionally out of scope here.

    Generation/barrier semantics: pause_barrier() stops new submissions, discards any
    jobs still sitting in the queue, and bumps an internal generation counter. A job's
    callback only fires if its generation still matches the coordinator's current
    generation at the moment the job finishes — this also invalidates a job that was
    already in flight (dequeued, mid-run) when the barrier was raised, so a stale
    result can never be delivered after a barrier. resume() re-opens submission.
    """

    def __init__(self, max_queue_size: int = 8):
        self._queue: "queue.Queue[tuple]" = queue.Queue(maxsize=max_queue_size)
        self._lock = threading.Lock()
        self._generation = 0
        self._paused = False
        self._shutdown = False
        self._stop_event = threading.Event()
        self._job_counter = itertools.count(1)
        self._worker = threading.Thread(
            target=self._run, name="sync-coordinator", daemon=True
        )
        self._worker.start()

    def submit(
        self,
        job: Callable[[], Any],
        on_result: Optional[Callable[[int, Any], None]] = None,
        on_error: Optional[Callable[[int, Exception], None]] = None,
    ) -> Optional[int]:
        """Enqueue a network-only job. Never blocks the calling thread.

        Returns the job_id on success, or None if the job was rejected because the
        coordinator is shut down, paused (mid-barrier), or the bounded queue is full.
        A None return means the caller's underlying work item (e.g. a pending scan
        row) was not claimed and remains eligible for a normal retry/batch path.
        """
        with self._lock:
            if self._shutdown or self._paused:
                return None
            generation = self._generation
        job_id = next(self._job_counter)
        try:
            self._queue.put_nowait((job_id, generation, job, on_result, on_error))
        except queue.Full:
            return None
        return job_id

    def pause_barrier(self) -> int:
        """Stop accepting new jobs, drop everything still queued, and advance the
        generation so any already-dequeued (in-flight) job's callback is skipped
        when it finishes. Returns the new generation number.

        Does not block waiting for an in-flight job to finish — callers that need
        that guarantee must poll/wait using their own mechanism so this method never
        blocks a Qt UI thread.
        """
        with self._lock:
            self._paused = True
            self._generation += 1
            new_generation = self._generation
        while True:
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break
        return new_generation

    def resume(self) -> None:
        """Re-open the coordinator for new submissions after a barrier."""
        with self._lock:
            self._paused = False

    def shutdown(self, timeout: Optional[float] = None) -> None:
        """Stop accepting new work and join the worker thread deterministically.

        Any job still queued when shutdown() is called is left unrun (its row, if
        any, remains pending for the normal batch path). A job already popped and
        executing when shutdown() is called is allowed to finish; join(timeout=...)
        bounds how long this call waits for that.
        """
        with self._lock:
            if self._shutdown:
                return
            self._shutdown = True
            self._stop_event.set()
        self._worker.join(timeout=timeout)

    def is_shutdown(self) -> bool:
        return self._shutdown

    def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                job_id, generation, job, on_result, on_error = self._queue.get(timeout=0.1)
            except queue.Empty:
                continue
            try:
                result = job()
            except Exception as exc:  # noqa: BLE001 - report to caller, don't crash worker
                if on_error and self._is_current_generation(generation):
                    try:
                        on_error(job_id, exc)
                    except Exception:
                        LOGGER.exception("sync coordinator on_error callback raised")
                continue
            if on_result and self._is_current_generation(generation):
                try:
                    on_result(job_id, result)
                except Exception:
                    LOGGER.exception("sync coordinator on_result callback raised")

    def _is_current_generation(self, generation: int) -> bool:
        with self._lock:
            return generation == self._generation


class SyncService:
    """Manages synchronization of local scans to cloud API."""

    def __init__(
        self,
        db: DatabaseManager,
        api_url: str,
        api_key: str,
        batch_size: int = 100,
        connection_timeout: float = 3.0,
    ) -> None:
        """
        Initialize sync service.

        Args:
            db: DatabaseManager instance
            api_url: Cloud API base URL (e.g., http://localhost:5000)
            api_key: API authentication key
            batch_size: Number of scans to upload per batch
        """
        self.db = db
        self.api_url = api_url.rstrip("/")
        self.api_key = api_key
        self.batch_size = batch_size
        self.connection_timeout = connection_timeout

    def test_connection(self) -> Tuple[bool, str]:
        """
        Test connection to cloud API.

        Returns:
            (success: bool, message: str)

        Side-effect: stores clear_epoch from response in self.last_clear_epoch.
        """
        try:
            LOGGER.info(
                "Health check: GET %s/ (timeout=%.2fs)",
                self.api_url,
                self.connection_timeout,
            )
            response = requests.get(
                f"{self.api_url}/",
                timeout=self.connection_timeout,
            )
            response.encoding = 'utf-8'  # Force UTF-8 encoding
            if response.status_code == 200:
                LOGGER.info("Health check success")
                try:
                    data = response.json()
                    self.last_clear_epoch = data.get("clear_epoch")
                except Exception:
                    self.last_clear_epoch = None
                return True, "Connected to cloud API"
            else:
                LOGGER.warning("Health check failed: API returned %s", response.status_code)
                return False, f"API returned status {response.status_code}"
        except requests.exceptions.ConnectionError as e:
            LOGGER.warning("Health check failed: Cannot connect to API (network error): %s", e)
            return False, "Cannot connect to API (network error)"
        except requests.exceptions.Timeout:
            LOGGER.warning("Health check failed: Connection timeout after %.2fs", self.connection_timeout)
            return False, "Connection timeout"
        except Exception as e:
            LOGGER.error("Health check error: %s", e)
            return False, f"Connection error: {str(e)}"

    last_clear_epoch: str | None = None  # populated by test_connection()

    def clear_station_scans(self, station_name: str) -> Dict[str, object]:
        """Delete scans for a specific station from cloud."""
        try:
            response = requests.delete(
                f"{self.api_url}/v1/admin/clear-station",
                params={"station": station_name},
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "X-Confirm-Delete": "DELETE STATION SCANS",
                },
                timeout=self.connection_timeout,
            )
            if response.status_code == 200:
                try:
                    return response.json()
                except (json.JSONDecodeError, ValueError) as e:
                    LOGGER.error(f"Invalid JSON response (status {response.status_code}): {response.text[:200]}")
                    return {"ok": False, "message": f"Invalid server response: {e}"}
            return {"ok": False, "message": f"API returned {response.status_code}"}
        except Exception as e:
            return {"ok": False, "message": str(e)}

    def send_heartbeat(self, station_name: str, last_clear_epoch: str | None, local_scan_count: int, retries: int = 1) -> bool:
        """Report station status to cloud. Retries on failure. Returns True on success."""
        from config import CLOUD_READ_ONLY
        if CLOUD_READ_ONLY:
            LOGGER.debug("Heartbeat skipped (read-only mode)")
            return True
        for attempt in range(1 + retries):
            try:
                response = requests.post(
                    f"{self.api_url}/v1/stations/heartbeat",
                    json={
                        "station_name": station_name,
                        "last_clear_epoch": last_clear_epoch,
                        "local_scan_count": local_scan_count,
                    },
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    timeout=self.connection_timeout,
                )
                if response.status_code == 200:
                    return True
            except Exception as e:
                LOGGER.debug("Heartbeat attempt %d failed: %s", attempt + 1, e)
            if attempt < retries:
                time.sleep(2)
        LOGGER.warning("Heartbeat failed after %d attempt(s)", 1 + retries)
        return False

    def get_station_status(self) -> Dict[str, object]:
        """Get all station statuses from cloud (public endpoint)."""
        try:
            response = requests.get(
                f"{self.api_url}/v1/stations/status",
                timeout=self.connection_timeout,
            )
            if response.status_code == 200:
                try:
                    return response.json()
                except (json.JSONDecodeError, ValueError) as e:
                    LOGGER.error(f"Invalid JSON response (status {response.status_code}): {response.text[:200]}")
                    return {"error": f"Invalid server response: {e}"}
            return {"error": f"API returned {response.status_code}"}
        except Exception as e:
            return {"error": str(e)}

    def test_authentication(self) -> Tuple[bool, str]:
        """
        Test authentication with the cloud API.
        Makes a minimal authenticated request to verify the API key is valid.

        Returns:
            (success: bool, message: str)
        """
        try:
            # Make a minimal POST request with auth header to verify token works
            # Using empty events array - API accepts this without errors
            response = requests.post(
                f"{self.api_url}/v1/scans/batch",
                json={"events": []},
                headers={
                    "Content-Type": "application/json; charset=utf-8",
                    "Authorization": f"Bearer {self.api_key}",
                },
                timeout=5,
            )
            response.encoding = 'utf-8'

            if response.status_code == 200:
                return True, "API authentication successful"
            elif response.status_code == 401:
                return False, "API authentication failed (invalid or expired API key)"
            elif response.status_code == 403:
                return False, "API access forbidden (insufficient permissions)"
            else:
                return False, f"API error: {response.status_code}"

        except requests.exceptions.Timeout:
            return False, "Authentication check timeout"
        except requests.exceptions.ConnectionError:
            return False, "Cannot reach API (network error)"
        except Exception as e:
            return False, f"Authentication error: {str(e)}"

    def sync_pending_scans(self, sync_all: bool = False, max_batches: int = None) -> Dict[str, int]:
        """
        Upload pending scans to cloud API.

        Args:
            sync_all: If True, syncs all pending scans in batches until none remain.
                      If False (default), syncs only one batch.
            max_batches: Maximum number of batches to sync when sync_all=True.
                         Prevents infinite loops. Default None (no limit).

        Read-only mode: returns zeros without uploading.

        Returns:
            Dictionary with counts: {"synced": int, "failed": int, "pending": int}
            If sync_all=True, also includes {"batches": int}
        """
        from config import CLOUD_READ_ONLY
        if CLOUD_READ_ONLY:
            LOGGER.debug("Scan sync skipped (read-only mode)")
            return {"synced": 0, "failed": 0, "pending": 0}
        if not sync_all:
            # Original behavior: sync one batch only
            return self._sync_one_batch()

        # Sync all pending scans in batches
        total_synced = 0
        total_failed = 0
        batch_count = 0

        while True:
            batch_result = self._sync_one_batch()
            batch_synced = batch_result.get('synced', 0)
            batch_failed = batch_result.get('failed', 0)
            pending = batch_result.get('pending', 0)

            total_synced += batch_synced
            total_failed += batch_failed
            batch_count += 1

            # Stop conditions
            if pending == 0:
                LOGGER.info(f"All scans synced after {batch_count} batch(es)")
                break
            if batch_synced == 0 and batch_failed == 0:
                LOGGER.warning(f"No progress in batch {batch_count}, stopping")
                break
            if max_batches and batch_count >= max_batches:
                LOGGER.info(f"Reached max_batches limit ({max_batches})")
                break

        return {
            "synced": total_synced,
            "failed": total_failed,
            "pending": pending,
            "batches": batch_count,
        }

    @staticmethod
    def _build_idempotency_key(station_name: str, badge_id: str, local_id: int) -> str:
        """Pure key-format helper, shared by _generate_idempotency_key (main-thread
        path, resolves station_name from self.db) and sync_scan_batch_network_only
        (network-only path, given an already-resolved station_name so it never
        touches self.db). Format: {station}-{badge_id}-{local_id}.
        """
        safe_station = (station_name or "UnknownStation").replace(" ", "").replace("-", "")
        return f"{safe_station}-{badge_id}-{local_id}"

    def _get_cached_station_name(self) -> str:
        """Resolve and cache the station name from self.db.

        Touches SQLite — only call this from the thread that owns self.db
        (the main thread). Never call from a network-only background job.
        """
        if not hasattr(self, '_cached_station_name'):
            self._cached_station_name = self.db.get_station_name() or "UnknownStation"
        return self._cached_station_name

    def _build_batch_events(self, scans: List[ScanRecord], station_name: str) -> List[dict]:
        """Build the /v1/scans/batch event payload for a list of scans.

        Pure — no I/O. station_name is passed in explicitly (rather than read from
        self.db) so this can be called from a network-only background job. Shared by
        _sync_one_batch (main-thread path) and sync_scan_batch_network_only.
        """
        events = []
        for scan in scans:
            # Ensure timestamp has Z suffix for UTC format
            scanned_at = scan.scanned_at
            if not scanned_at.endswith('Z'):
                # Handle timezone offset format (e.g., "2025-11-05T08:39:24+00:00")
                if '+00:00' in scanned_at:
                    scanned_at = scanned_at.replace('+00:00', 'Z')
                else:
                    scanned_at = scanned_at + 'Z'

            events.append({
                "idempotency_key": self._build_idempotency_key(station_name, scan.badge_id, scan.id),
                "badge_id": scan.badge_id,
                "station_name": scan.station_name,
                "scanned_at": scanned_at,
                "business_unit": scan.sl_l1_desc or None,
                "scan_source": scan.scan_source or "manual",
                "meta": {
                    "matched": scan.legacy_id is not None,
                    "legacy_id": scan.legacy_id,
                    "local_id": scan.id,
                },
            })
        return events

    def _sync_one_batch(self) -> Dict[str, int]:
        """
        Internal method: Upload ONE BATCH of pending scans to cloud API with retry logic.

        Uses exponential backoff for transient failures (timeouts, connection errors).

        Returns:
            Dictionary with counts: {"synced": int, "failed": int, "pending": int}
        """
        # Fetch pending scans
        pending_scans = self.db.fetch_pending_scans(limit=self.batch_size)

        if not pending_scans:
            LOGGER.info("No pending scans to sync")
            return {"synced": 0, "failed": 0, "pending": 0}

        LOGGER.info(f"Attempting to sync {len(pending_scans)} scans")

        # Build batch payload (reusable for retries)
        events = self._build_batch_events(pending_scans, self._get_cached_station_name())

        # Upload to cloud API with retry logic
        from config import SYNC_RETRY_ENABLED, SYNC_RETRY_MAX_ATTEMPTS, SYNC_RETRY_BACKOFF_SECONDS

        max_attempts = SYNC_RETRY_MAX_ATTEMPTS if SYNC_RETRY_ENABLED else 1
        backoff_seconds = SYNC_RETRY_BACKOFF_SECONDS if SYNC_RETRY_ENABLED else 0
        last_error = None

        for attempt in range(max_attempts):
            try:
                LOGGER.info(f"Syncing {len(events)} scans to cloud API (attempt {attempt + 1}/{max_attempts})...")
                response = requests.post(
                    f"{self.api_url}/v1/scans/batch",
                    json={"events": events},
                    headers={
                        "Content-Type": "application/json; charset=utf-8",
                        "Authorization": f"Bearer {self.api_key}",
                    },
                    timeout=10,
                )
                response.encoding = 'utf-8'  # Force UTF-8 encoding
                LOGGER.info(f"Cloud API response received in {response.elapsed.total_seconds():.2f}s")

                if response.status_code == 200:
                    try:
                        result = response.json()
                    except (json.JSONDecodeError, ValueError) as e:
                        LOGGER.error(f"Invalid JSON response (status {response.status_code}): {response.text[:200]}")
                        error_msg = f"Invalid server response: {e}"
                        scan_ids = [scan.id for scan in pending_scans]
                        self.db.mark_scans_as_failed(scan_ids, error_msg)
                        stats = self.db.get_sync_statistics()
                        return {
                            "synced": 0,
                            "failed": len(pending_scans),
                            "pending": stats["pending"],
                        }
                    synced_count = result.get("saved", 0) + result.get("duplicates", 0)
                    scan_ids = [scan.id for scan in pending_scans]

                    # Mark as synced
                    self.db.mark_scans_as_synced(scan_ids)

                    LOGGER.info(
                        f"Successfully synced {synced_count} scans "
                        f"(saved: {result.get('saved')}, duplicates: {result.get('duplicates')})"
                    )

                    # Get remaining pending count
                    stats = self.db.get_sync_statistics()

                    return {
                        "synced": synced_count,
                        "failed": 0,
                        "pending": stats["pending"],
                    }
                else:
                    # Classify error as retryable or permanent
                    if response.status_code == 401:
                        # 401 Unauthorized - permanent auth error, don't retry
                        error_msg = "API error: 401 (Unauthorized - check API key)"
                        LOGGER.error(error_msg)
                        stats = self.db.get_sync_statistics()
                        return {
                            "synced": 0,
                            "failed": 0,
                            "pending": stats["pending"],
                            "error": error_msg,
                        }
                    elif 400 <= response.status_code < 500 and response.status_code != 429:
                        # Other 4xx errors (bad request, etc.) - non-retryable, mark as failed
                        error_msg = f"API error: {response.status_code} (non-retryable)"
                        scan_ids = [scan.id for scan in pending_scans]
                        self.db.mark_scans_as_failed(scan_ids, error_msg)
                        LOGGER.error(f"Sync failed: {error_msg}")
                        stats = self.db.get_sync_statistics()
                        return {
                            "synced": 0,
                            "failed": len(pending_scans),
                            "pending": stats["pending"],
                        }
                    else:
                        # Retryable error (5xx or 429) - will retry
                        error_msg = f"API error: {response.status_code}"
                        last_error = error_msg
                        if attempt < max_attempts - 1:
                            wait_time = backoff_seconds * (2 ** attempt)  # Exponential backoff
                            LOGGER.warning(f"{error_msg}, retrying in {wait_time}s...")
                            time.sleep(wait_time)
                        continue

            except requests.exceptions.Timeout as e:
                # Timeout - retryable
                error_msg = f"Connection timeout: {str(e)}"
                last_error = error_msg
                if attempt < max_attempts - 1:
                    wait_time = backoff_seconds * (2 ** attempt)
                    LOGGER.warning(f"{error_msg}, retrying in {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    LOGGER.error(f"Sync failed after {max_attempts} attempts: {error_msg}")

            except requests.exceptions.ConnectionError as e:
                # Connection error - retryable
                error_msg = f"Connection error: {str(e)}"
                last_error = error_msg
                if attempt < max_attempts - 1:
                    wait_time = backoff_seconds * (2 ** attempt)
                    LOGGER.warning(f"{error_msg}, retrying in {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    LOGGER.error(f"Sync failed after {max_attempts} attempts: {error_msg}")

            except requests.exceptions.RequestException as e:
                # Other network errors - mark as failed
                error_msg = f"Network error: {str(e)}"
                scan_ids = [scan.id for scan in pending_scans]
                self.db.mark_scans_as_failed(scan_ids, error_msg)
                LOGGER.error(f"Sync failed: {error_msg}")

                stats = self.db.get_sync_statistics()
                return {
                    "synced": 0,
                    "failed": len(pending_scans),
                    "pending": stats["pending"],
                }

        # All retries exhausted with no success - keep as pending for future retry
        if last_error:
            error_msg = f"Network error (after {max_attempts} attempts): {last_error}"
            LOGGER.warning("%s — scans kept as pending for future retry", error_msg)

        stats = self.db.get_sync_statistics()
        return {
            "synced": 0,
            "failed": 0,
            "pending": stats["pending"],
        }

    def _generate_idempotency_key(self, scan: ScanRecord) -> str:
        """
        Generate unique idempotency key for a scan.

        Format: {station_name}-{badge_id}-{local_id}
        Example: MainGate-101117-1234

        Touches SQLite (via _get_cached_station_name -> self.db.get_station_name())
        on first call — only call this from the thread that owns self.db.
        """
        return self._build_idempotency_key(
            self._get_cached_station_name(), scan.badge_id, scan.id
        )

    def sync_scan_batch_network_only(
        self,
        scans: List[ScanRecord],
        station_name: str,
    ) -> Dict[str, Any]:
        """Upload a caller-supplied snapshot of scans to the cloud API. No SQLite access.

        This is the network-only counterpart to _sync_one_batch(): it performs the
        exact same request-building, idempotency-key format, and retry/backoff
        classification, but never reads or writes self.db — the caller (the Qt/main
        thread) is responsible for snapshotting pending ScanRecord rows beforehand
        and applying mark_scans_as_synced()/mark_scans_as_failed() afterward, based
        on the id lists returned here. Safe to call from a background worker thread
        (e.g. via BackgroundSyncCoordinator), since sqlite3 connections are not
        thread-safe across threads.

        Args:
            scans: Snapshot of ScanRecord rows to upload (already fetched by the
                   caller from the main thread — this method does not fetch anything).
            station_name: Pre-resolved station name (the caller must resolve this via
                          self.db.get_station_name() on the main thread beforehand;
                          this method must not call it here).

        Returns:
            {
                "ok": bool,                 # False only for a genuine transport-level
                                             # failure (e.g. malformed response); see below
                "synced_ids": List[int],    # scan.id values the cloud accepted
                "failed_ids": List[int],    # scan.id values that permanently failed
                                             # (4xx other than 401/429) — caller should
                                             # mark_scans_as_failed() for these
                "pending_ids": List[int],   # scan.id values still unresolved (retries
                                             # exhausted, or a 401) — caller should leave
                                             # these as pending, matching _sync_one_batch's
                                             # existing "keep as pending" behavior
                "synced_count": int,
                "error": Optional[str],
            }

        Read-only mode: returns everything as pending_ids without uploading, matching
        sync_pending_scans()'s CLOUD_READ_ONLY short-circuit.
        """
        from config import CLOUD_READ_ONLY

        all_ids = [scan.id for scan in scans]

        if CLOUD_READ_ONLY:
            LOGGER.debug("Scan batch sync skipped (read-only mode)")
            return {
                "ok": True, "synced_ids": [], "failed_ids": [], "pending_ids": all_ids,
                "synced_count": 0, "error": None,
            }

        if not scans:
            return {
                "ok": True, "synced_ids": [], "failed_ids": [], "pending_ids": [],
                "synced_count": 0, "error": None,
            }

        LOGGER.info(f"[NetworkOnly] Attempting to sync {len(scans)} scans")
        events = self._build_batch_events(scans, station_name)

        from config import SYNC_RETRY_ENABLED, SYNC_RETRY_MAX_ATTEMPTS, SYNC_RETRY_BACKOFF_SECONDS

        max_attempts = SYNC_RETRY_MAX_ATTEMPTS if SYNC_RETRY_ENABLED else 1
        backoff_seconds = SYNC_RETRY_BACKOFF_SECONDS if SYNC_RETRY_ENABLED else 0
        last_error = None

        for attempt in range(max_attempts):
            try:
                LOGGER.info(
                    f"[NetworkOnly] Syncing {len(events)} scans to cloud API "
                    f"(attempt {attempt + 1}/{max_attempts})..."
                )
                response = requests.post(
                    f"{self.api_url}/v1/scans/batch",
                    json={"events": events},
                    headers={
                        "Content-Type": "application/json; charset=utf-8",
                        "Authorization": f"Bearer {self.api_key}",
                    },
                    timeout=10,
                )
                response.encoding = 'utf-8'
                LOGGER.info(f"[NetworkOnly] Cloud API response received in {response.elapsed.total_seconds():.2f}s")

                if response.status_code == 200:
                    try:
                        result = response.json()
                    except (json.JSONDecodeError, ValueError) as e:
                        LOGGER.error(f"[NetworkOnly] Invalid JSON response (status {response.status_code}): {response.text[:200]}")
                        error_msg = f"Invalid server response: {e}"
                        return {
                            "ok": False, "synced_ids": [], "failed_ids": all_ids,
                            "pending_ids": [], "synced_count": 0, "error": error_msg,
                        }
                    synced_count = result.get("saved", 0) + result.get("duplicates", 0)
                    LOGGER.info(
                        f"[NetworkOnly] Successfully synced {synced_count} scans "
                        f"(saved: {result.get('saved')}, duplicates: {result.get('duplicates')})"
                    )
                    return {
                        "ok": True, "synced_ids": all_ids, "failed_ids": [],
                        "pending_ids": [], "synced_count": synced_count, "error": None,
                    }
                else:
                    if response.status_code == 401:
                        error_msg = "API error: 401 (Unauthorized - check API key)"
                        LOGGER.error(f"[NetworkOnly] {error_msg}")
                        return {
                            "ok": True, "synced_ids": [], "failed_ids": [],
                            "pending_ids": all_ids, "synced_count": 0, "error": error_msg,
                        }
                    elif 400 <= response.status_code < 500 and response.status_code != 429:
                        error_msg = f"API error: {response.status_code} (non-retryable)"
                        LOGGER.error(f"[NetworkOnly] Sync failed: {error_msg}")
                        return {
                            "ok": True, "synced_ids": [], "failed_ids": all_ids,
                            "pending_ids": [], "synced_count": 0, "error": error_msg,
                        }
                    else:
                        error_msg = f"API error: {response.status_code}"
                        last_error = error_msg
                        if attempt < max_attempts - 1:
                            wait_time = backoff_seconds * (2 ** attempt)
                            LOGGER.warning(f"[NetworkOnly] {error_msg}, retrying in {wait_time}s...")
                            time.sleep(wait_time)
                        continue

            except requests.exceptions.Timeout as e:
                error_msg = f"Connection timeout: {str(e)}"
                last_error = error_msg
                if attempt < max_attempts - 1:
                    wait_time = backoff_seconds * (2 ** attempt)
                    LOGGER.warning(f"[NetworkOnly] {error_msg}, retrying in {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    LOGGER.error(f"[NetworkOnly] Sync failed after {max_attempts} attempts: {error_msg}")

            except requests.exceptions.ConnectionError as e:
                error_msg = f"Connection error: {str(e)}"
                last_error = error_msg
                if attempt < max_attempts - 1:
                    wait_time = backoff_seconds * (2 ** attempt)
                    LOGGER.warning(f"[NetworkOnly] {error_msg}, retrying in {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    LOGGER.error(f"[NetworkOnly] Sync failed after {max_attempts} attempts: {error_msg}")

            except requests.exceptions.RequestException as e:
                error_msg = f"Network error: {str(e)}"
                LOGGER.error(f"[NetworkOnly] Sync failed: {error_msg}")
                return {
                    "ok": True, "synced_ids": [], "failed_ids": all_ids,
                    "pending_ids": [], "synced_count": 0, "error": error_msg,
                }

        # All retries exhausted with no success - keep as pending for future retry
        if last_error:
            error_msg = f"Network error (after {max_attempts} attempts): {last_error}"
            LOGGER.warning("[NetworkOnly] %s — scans kept as pending for future retry", error_msg)
        return {
            "ok": True, "synced_ids": [], "failed_ids": [], "pending_ids": all_ids,
            "synced_count": 0, "error": last_error,
        }

    def check_duplicate_cloud(
        self,
        badge_id: str,
        station_name: str,
        window_minutes: int = 5,
        timeout: float = 2.0,
    ) -> dict:
        """Check cloud for cross-station duplicate scan. Fail-open on any error."""
        from config import CLOUD_READ_ONLY
        if CLOUD_READ_ONLY:
            return {"duplicate": False, "skipped": True}
        try:
            response = requests.get(
                f"{self.api_url}/v1/scans/check-duplicate",
                params={
                    "badge_id": badge_id,
                    "window_minutes": str(window_minutes),
                    "exclude_station": station_name,
                },
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=timeout,
            )
            if response.status_code == 200:
                return response.json()
            LOGGER.warning("Cloud dup check returned %d", response.status_code)
            return {"duplicate": False, "error": f"HTTP {response.status_code}"}
        except Exception as e:
            LOGGER.warning("Cloud dup check failed (fail-open): %s", e)
            return {"duplicate": False, "error": str(e)}

    def sync_single_scan(self, scan: ScanRecord) -> dict:
        """Immediately sync a single scan to cloud. Fire-and-forget safe."""
        from config import CLOUD_READ_ONLY
        if CLOUD_READ_ONLY:
            return {"ok": False, "skipped": True}
        try:
            key = self._generate_idempotency_key(scan)
            payload = {
                "events": [{
                    "idempotency_key": key,
                    "badge_id": scan.badge_id,
                    "station_name": scan.station_name,
                    "scanned_at": scan.scanned_at,
                    "business_unit": scan.sl_l1_desc or None,
                    "scan_source": scan.scan_source,
                }]
            }
            response = requests.post(
                f"{self.api_url}/v1/scans/batch",
                json=payload,
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=3.0,
            )
            if response.status_code == 200:
                # Don't call mark_scans_as_synced here — this runs in a
                # background thread and the SQLite connection belongs to the
                # main thread.  Batch sync will mark it later; the idempotency
                # key prevents double-counting on the cloud side.
                LOGGER.info("[LiveSync] Immediate sync OK: badge=%s", scan.badge_id)
                return {"ok": True}
            LOGGER.warning("[LiveSync] Immediate sync HTTP %d", response.status_code)
            return {"ok": False, "error": f"HTTP {response.status_code}"}
        except Exception as e:
            LOGGER.warning("[LiveSync] Immediate sync failed: %s", e)
            return {"ok": False, "error": str(e)}

    def get_cloud_scan_count(self) -> Tuple[bool, int, str]:
        """Get count of scans in cloud database.

        Returns:
            (success, count, message)
        """
        try:
            response = requests.get(
                f"{self.api_url}/v1/admin/scan-count",
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=10,
            )
            if response.status_code == 200:
                try:
                    data = response.json()
                except (json.JSONDecodeError, ValueError) as e:
                    LOGGER.error(f"Invalid JSON response (status {response.status_code}): {response.text[:200]}")
                    return False, 0, f"Invalid server response: {e}"
                return True, data.get("count", 0), "OK"
            else:
                return False, 0, f"API error: {response.status_code}"
        except requests.exceptions.ConnectionError:
            return False, 0, "Cannot connect to API"
        except requests.exceptions.Timeout:
            return False, 0, "Connection timeout"
        except Exception as e:
            return False, 0, f"Error: {str(e)}"

    def clear_cloud_scans(self) -> Dict[str, object]:
        """Clear all scans from cloud database.

        Returns:
            Dictionary with: ok, deleted, message
        """
        try:
            response = requests.delete(
                f"{self.api_url}/v1/admin/clear-scans",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "X-Confirm-Delete": "DELETE ALL SCANS",
                },
                timeout=30,
            )
            if response.status_code == 200:
                try:
                    data = response.json()
                except (json.JSONDecodeError, ValueError) as e:
                    LOGGER.error(f"Invalid JSON response (status {response.status_code}): {response.text[:200]}")
                    return {"ok": False, "deleted": 0, "message": f"Invalid server response: {e}"}
                LOGGER.info(f"Cloud scans cleared: {data.get('deleted', 0)} records")
                return {"ok": True, "deleted": data.get("deleted", 0), "clear_epoch": data.get("clear_epoch", ""), "message": data.get("message", "Scans cleared")}
            elif response.status_code == 401:
                return {"ok": False, "deleted": 0, "message": "Authentication failed"}
            else:
                return {"ok": False, "deleted": 0, "message": f"API error: {response.status_code}"}
        except requests.exceptions.ConnectionError:
            return {"ok": False, "deleted": 0, "message": "Cannot connect to API"}
        except requests.exceptions.Timeout:
            return {"ok": False, "deleted": 0, "message": "Connection timeout"}
        except Exception as e:
            return {"ok": False, "deleted": 0, "message": f"Error: {str(e)}"}


    def get_dashboard_refresh(self) -> Tuple[bool, int, str]:
        """Get current dashboard refresh interval from cloud.

        Returns:
            (success, interval_seconds, message)
        """
        try:
            response = requests.get(
                f"{self.api_url}/v1/dashboard/public/config",
                timeout=10,
            )
            if response.status_code == 200:
                try:
                    data = response.json()
                except (json.JSONDecodeError, ValueError) as e:
                    LOGGER.error(f"Invalid JSON response (status {response.status_code}): {response.text[:200]}")
                    return False, 60, f"Invalid server response: {e}"
                return True, data.get("refresh_interval", 60), "OK"
            return False, 60, f"API error: {response.status_code}"
        except Exception as e:
            return False, 60, f"Error: {str(e)}"

    def set_dashboard_refresh(self, interval: int) -> Tuple[bool, str]:
        """Set dashboard refresh interval on cloud.

        Args:
            interval: 0 (manual only) or 10-600 seconds

        Returns:
            (success, message)
        """
        try:
            response = requests.put(
                f"{self.api_url}/v1/dashboard/config",
                json={"refresh_interval": interval},
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=10,
            )
            if response.status_code == 200:
                return True, f"Refresh set to {interval}s" if interval > 0 else "Auto-refresh disabled"
            elif response.status_code == 400:
                try:
                    data = response.json()
                except (json.JSONDecodeError, ValueError):
                    return False, f"API error: {response.status_code}"
                return False, data.get("error", "Invalid value")
            return False, f"API error: {response.status_code}"
        except Exception as e:
            return False, f"Error: {str(e)}"


def sync_roster_summary(db: DatabaseManager, api_url: str, api_key: str) -> dict:
    """Push BU roster counts to cloud for dashboard progress display."""
    from config import CLOUD_READ_ONLY
    if CLOUD_READ_ONLY:
        LOGGER.debug("Roster sync skipped (read-only mode)")
        return {"ok": True, "skipped": True}
    bu_data = db.get_employees_by_bu()
    if not bu_data:
        return {"ok": False, "reason": "no_employees"}

    payload = {
        "business_units": [
            {"name": row["bu_name"], "registered": row["count"]}
            for row in bu_data
        ]
    }

    try:
        response = requests.post(
            f"{api_url.rstrip('/')}/v1/roster/summary",
            json=payload,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=10,
        )
        response.raise_for_status()
        try:
            result = response.json()
        except (json.JSONDecodeError, ValueError) as e:
            LOGGER.error(f"Invalid JSON response (status {response.status_code}): {response.text[:200]}")
            return {"ok": False, "error": f"Invalid server response: {e}"}
        LOGGER.info(f"RosterSync: pushed {len(bu_data)} BU counts to cloud")
        return {"ok": True, "saved": result.get("saved", 0)}
    except Exception as e:
        LOGGER.warning(f"RosterSync: failed to push roster summary: {e}")
        return {"ok": False, "error": str(e)}


def sync_roster_summary_from_data(bu_data: list, api_url: str, api_key: str) -> dict:
    """Push pre-fetched BU counts to cloud. Thread-safe (no DB access).

    Called from health check thread after first successful API connection.
    Checks cloud hash first — skips POST if roster already up to date.
    Skipped entirely in CLOUD_READ_ONLY mode.
    """
    from config import CLOUD_READ_ONLY
    if CLOUD_READ_ONLY:
        LOGGER.debug("Roster sync from data skipped (read-only mode)")
        return {"ok": True, "skipped": True}
    import hashlib

    # Compute local hash (same algorithm as API)
    hash_input = "|".join(sorted(f"{row['bu_name']}:{row['count']}" for row in bu_data))
    local_hash = hashlib.sha256(hash_input.encode()).hexdigest()[:16]

    headers = {"Authorization": f"Bearer {api_key}"}
    base_url = api_url.rstrip("/")

    # Check cloud hash first
    try:
        check = requests.get(f"{base_url}/v1/roster/hash", headers=headers, timeout=5)
        if check.status_code == 200:
            cloud_hash = check.json().get("hash")
            if cloud_hash == local_hash:
                LOGGER.info(f"RosterSync: hash match ({local_hash}), skipping POST")
                return {"ok": True, "skipped": True}
    except Exception:
        pass  # proceed to POST if hash check fails

    # Hash mismatch or check failed — push the data
    payload = {
        "business_units": [
            {"name": row["bu_name"], "registered": row["count"]}
            for row in bu_data
        ]
    }
    try:
        response = requests.post(
            f"{base_url}/v1/roster/summary",
            json=payload,
            headers=headers,
            timeout=10,
        )
        response.raise_for_status()
        try:
            result = response.json()
        except (json.JSONDecodeError, ValueError) as e:
            LOGGER.error(f"Invalid JSON response (status {response.status_code}): {response.text[:200]}")
            return {"ok": False, "error": f"Invalid server response: {e}"}
        skipped = result.get("skipped", False)
        LOGGER.info(f"RosterSync: pushed {len(bu_data)} BU counts (hash={local_hash}, skipped={skipped})")
        return {"ok": True, "saved": result.get("saved", 0), "skipped": skipped}
    except Exception as e:
        LOGGER.warning(f"RosterSync: failed to push roster summary: {e}")
        return {"ok": False, "error": str(e)}


__all__ = ["SyncService", "sync_roster_summary", "sync_roster_summary_from_data"]
