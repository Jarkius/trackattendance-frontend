"""Cloud sync service for uploading attendance scans."""

from __future__ import annotations

import logging
import requests
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timezone

from database import DatabaseManager, ScanRecord

LOGGER = logging.getLogger(__name__)


class SyncService:
    """Manages synchronization of local scans to cloud API."""

    def __init__(
        self,
        db: DatabaseManager,
        api_url: str,
        api_key: str,
        batch_size: int = 100,
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
        self.station_name = db.get_station_name()

    def test_connection(self) -> Tuple[bool, str]:
        """
        Test connection to cloud API.

        Returns:
            (success: bool, message: str)
        """
        try:
            response = requests.get(
                f"{self.api_url}/healthz",
                timeout=5,
            )
            if response.status_code == 200:
                return True, "Connected to cloud API"
            else:
                return False, f"API returned status {response.status_code}"
        except requests.exceptions.ConnectionError:
            return False, "Cannot connect to API (network error)"
        except requests.exceptions.Timeout:
            return False, "Connection timeout"
        except Exception as e:
            return False, f"Connection error: {str(e)}"

    def sync_pending_scans(self) -> Dict[str, int]:
        """
        Upload pending scans to cloud API.

        Returns:
            Dictionary with counts: {"synced": int, "failed": int, "pending": int}
        """
        # Fetch pending scans
        pending_scans = self.db.fetch_pending_scans(limit=self.batch_size)

        if not pending_scans:
            LOGGER.info("No pending scans to sync")
            return {"synced": 0, "failed": 0, "pending": 0}

        LOGGER.info(f"Attempting to sync {len(pending_scans)} scans")

        # Build batch payload
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
                "meta": {
                    "matched": scan.legacy_id is not None,
                    "local_id": scan.id,
                },
            })

        # Upload to cloud API
        try:
            response = requests.post(
                f"{self.api_url}/v1/scans/batch",
                json={"events": events},
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.api_key}",
                },
                timeout=30,
            )

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
                # API error - mark as failed
                error_msg = f"API error: {response.status_code}"
                scan_ids = [scan.id for scan in pending_scans]
                self.db.mark_scans_as_failed(scan_ids, error_msg)

                LOGGER.error(f"Sync failed: {error_msg}")

                return {
                    "synced": 0,
                    "failed": len(pending_scans),
                    "pending": len(pending_scans),
                }

        except requests.exceptions.RequestException as e:
            # Network error - mark as failed
            error_msg = f"Network error: {str(e)}"
            scan_ids = [scan.id for scan in pending_scans]
            self.db.mark_scans_as_failed(scan_ids, error_msg)

            LOGGER.error(f"Sync failed: {error_msg}")

            return {
                "synced": 0,
                "failed": len(pending_scans),
                "pending": len(pending_scans),
            }

    def _generate_idempotency_key(self, scan: ScanRecord) -> str:
        """
        Generate unique idempotency key for a scan.

        Format: {station_name}-{badge_id}-{local_id}
        Example: MainGate-101117-1234
        """
        # Sanitize station name (remove spaces and special chars)
        safe_station = self.station_name.replace(" ", "").replace("-", "")
        return f"{safe_station}-{scan.badge_id}-{scan.id}"


__all__ = ["SyncService"]
