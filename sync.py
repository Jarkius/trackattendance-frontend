"""Cloud sync service for uploading attendance scans."""

from __future__ import annotations

import logging
import requests
import time
from typing import Dict, List, Optional, Tuple
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

        Returns:
            Dictionary with counts: {"synced": int, "failed": int, "pending": int}
            If sync_all=True, also includes {"batches": int}
        """
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
        events = []
        for scan in pending_scans:
            # Ensure timestamp has Z suffix for UTC format
            scanned_at = scan.scanned_at
            if not scanned_at.endswith('Z'):
                # Handle timezone offset format (e.g., "2025-11-05T08:39:24+00:00")
                if '+00:00' in scanned_at:
                    scanned_at = scanned_at.replace('+00:00', 'Z')
                else:
                    scanned_at = scanned_at + 'Z'

            events.append({
                "idempotency_key": self._generate_idempotency_key(scan),
                "badge_id": scan.badge_id,
                "station_name": scan.station_name,
                "scanned_at": scanned_at,
                "business_unit": scan.sl_l1_desc or None,
                "meta": {
                    "matched": scan.legacy_id is not None,
                    "local_id": scan.id,
                },
            })

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
                    result = response.json()
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
        """
        # Get station name dynamically from database (cached for performance)
        if not hasattr(self, '_cached_station_name'):
            self._cached_station_name = self.db.get_station_name() or "UnknownStation"
        station = self._cached_station_name
        # Sanitize station name (remove spaces and special chars)
        safe_station = station.replace(" ", "").replace("-", "")
        return f"{safe_station}-{scan.badge_id}-{scan.id}"


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
                data = response.json()
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
                data = response.json()
                LOGGER.info(f"Cloud scans cleared: {data.get('deleted', 0)} records")
                return {"ok": True, "deleted": data.get("deleted", 0), "message": data.get("message", "Scans cleared")}
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


def sync_roster_summary(db: DatabaseManager, api_url: str, api_key: str) -> dict:
    """Push BU roster counts to cloud for dashboard progress display."""
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
        result = response.json()
        LOGGER.info(f"RosterSync: pushed {len(bu_data)} BU counts to cloud")
        return {"ok": True, "saved": result.get("saved", 0)}
    except Exception as e:
        LOGGER.warning(f"RosterSync: failed to push roster summary: {e}")
        return {"ok": False, "error": str(e)}


def sync_roster_summary_from_data(
    bu_data: list, api_url: str, api_key: str,
    max_retries: int = 5, initial_delay: float = 10.0,
) -> dict:
    """Push pre-fetched BU counts to cloud. Thread-safe (no DB access).

    Retries with exponential backoff if network is unavailable at startup.
    Delays: 10s, 30s, 90s, 270s, 810s (~13 min total before giving up).
    """
    import time

    payload = {
        "business_units": [
            {"name": row["bu_name"], "registered": row["count"]}
            for row in bu_data
        ]
    }

    delay = initial_delay
    for attempt in range(1, max_retries + 1):
        try:
            response = requests.post(
                f"{api_url.rstrip('/')}/v1/roster/summary",
                json=payload,
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=10,
            )
            response.raise_for_status()
            result = response.json()
            LOGGER.info(f"RosterSync: pushed {len(bu_data)} BU counts to cloud")
            return {"ok": True, "saved": result.get("saved", 0)}
        except Exception as e:
            if attempt < max_retries:
                LOGGER.info(f"RosterSync: attempt {attempt}/{max_retries} failed, retry in {delay:.0f}s: {e}")
                time.sleep(delay)
                delay *= 3  # exponential backoff
            else:
                LOGGER.warning(f"RosterSync: all {max_retries} attempts failed: {e}")
                return {"ok": False, "error": str(e)}


__all__ = ["SyncService", "sync_roster_summary", "sync_roster_summary_from_data"]
