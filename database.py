"""Database management utilities for the attendance application."""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

logger = logging.getLogger(__name__)

ISO_TIMESTAMP_FORMAT = "%Y-%m-%dT%H:%M:%SZ"  # UTC format with Z suffix


@dataclass(frozen=True)
class EmployeeRecord:
    legacy_id: str
    full_name: str
    sl_l1_desc: str
    position_desc: str
    email: str = ""


@dataclass(frozen=True)
class ScanRecord:
    id: int
    badge_id: str
    scanned_at: str
    station_name: str
    employee_full_name: Optional[str]
    legacy_id: Optional[str]
    sl_l1_desc: Optional[str]
    position_desc: Optional[str]
    email: Optional[str] = None
    scan_source: str = "manual"
    sync_status: str = "pending"
    synced_at: Optional[str] = None
    sync_error: Optional[str] = None


class DatabaseManager:
    """Lightweight wrapper around the SQLite database."""

    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path
        self._connection = sqlite3.connect(self._database_path)
        self._connection.row_factory = sqlite3.Row
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        with self._connection:
            self._connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS stations (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    name TEXT NOT NULL,
                    configured_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS employees (
                    legacy_id TEXT PRIMARY KEY,
                    full_name TEXT NOT NULL,
                    sl_l1_desc TEXT NOT NULL,
                    position_desc TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS scans (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    badge_id TEXT NOT NULL,
                    scanned_at TEXT NOT NULL,
                    station_name TEXT NOT NULL,
                    employee_full_name TEXT,
                    legacy_id TEXT,
                    sl_l1_desc TEXT,
                    position_desc TEXT,
                    sync_status TEXT NOT NULL DEFAULT 'pending',
                    synced_at TEXT,
                    sync_error TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_scans_sync_status ON scans(sync_status);
                CREATE INDEX IF NOT EXISTS idx_scans_badge_station_time ON scans(badge_id, station_name, scanned_at DESC);
                CREATE INDEX IF NOT EXISTS idx_scans_sync_status_time ON scans(sync_status, scanned_at);
                CREATE INDEX IF NOT EXISTS idx_scans_station_name ON scans(station_name);
                CREATE INDEX IF NOT EXISTS idx_employees_sl_l1_desc ON employees(sl_l1_desc);

                CREATE TABLE IF NOT EXISTS roster_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                """
            )
        # Migrations for email column
        try:
            self._connection.execute("ALTER TABLE employees ADD COLUMN email TEXT DEFAULT ''")
        except sqlite3.OperationalError:
            pass  # column already exists
        try:
            self._connection.execute("ALTER TABLE scans ADD COLUMN email TEXT")
        except sqlite3.OperationalError:
            pass  # column already exists
        try:
            self._connection.execute("ALTER TABLE scans ADD COLUMN scan_source TEXT DEFAULT 'manual'")
        except sqlite3.OperationalError:
            pass  # column already exists

    def get_station_name(self) -> Optional[str]:
        cursor = self._connection.execute("SELECT name FROM stations WHERE id = 1")
        row = cursor.fetchone()
        return row["name"] if row else None

    def set_station_name(self, name: str) -> None:
        with self._connection:
            self._connection.execute(
                "INSERT INTO stations(id, name, configured_at) VALUES(1, ?, CURRENT_TIMESTAMP) "
                "ON CONFLICT(id) DO UPDATE SET name = excluded.name",
                (name.strip(),),
            )

    def employees_loaded(self) -> bool:
        cursor = self._connection.execute("SELECT COUNT(1) FROM employees")
        return cursor.fetchone()[0] > 0

    def get_roster_meta(self, key: str) -> Optional[str]:
        cursor = self._connection.execute("SELECT value FROM roster_meta WHERE key = ?", (key,))
        row = cursor.fetchone()
        return row[0] if row else None

    def set_roster_meta(self, key: str, value: str) -> None:
        with self._connection:
            self._connection.execute(
                "INSERT INTO roster_meta(key, value) VALUES(?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, value),
            )

    def get_roster_hash(self) -> Optional[str]:
        return self.get_roster_meta("file_hash")

    def set_roster_hash(self, file_hash: str) -> None:
        self.set_roster_meta("file_hash", file_hash)

    def clear_employees(self) -> None:
        """Remove all employees to prepare for reimport."""
        with self._connection:
            self._connection.execute("DELETE FROM employees")

    def bulk_insert_employees(self, employees: Iterable[EmployeeRecord]) -> int:
        rows = [
            (
                employee.legacy_id.strip(),
                employee.full_name.strip(),
                employee.sl_l1_desc.strip(),
                employee.position_desc.strip(),
                employee.email.strip() if employee.email else "",
            )
            for employee in employees
        ]
        with self._connection:
            self._connection.executemany(
                "INSERT OR IGNORE INTO employees(legacy_id, full_name, sl_l1_desc, position_desc, email)"
                " VALUES(?, ?, ?, ?, ?)",
                rows,
            )
        return len(rows)

    def load_employee_cache(self) -> Dict[str, EmployeeRecord]:
        cursor = self._connection.execute(
            "SELECT legacy_id, full_name, sl_l1_desc, position_desc, email FROM employees"
        )
        return {
            row["legacy_id"]: EmployeeRecord(
                legacy_id=row["legacy_id"],
                full_name=row["full_name"],
                sl_l1_desc=row["sl_l1_desc"],
                position_desc=row["position_desc"],
                email=row["email"] or "",
            )
            for row in cursor.fetchall()
        }

    def record_scan(
        self,
        badge_id: str,
        station_name: str,
        employee: Optional[EmployeeRecord],
        scanned_at: Optional[str] = None,
        scan_source: str = "manual",
    ) -> None:
        timestamp = scanned_at or datetime.now(timezone.utc).strftime(ISO_TIMESTAMP_FORMAT)
        logger.info(f"RecordingScan: badge={badge_id}, station={station_name}, time={timestamp}, source={scan_source}")
        with self._connection:
            self._connection.execute(
                """
                INSERT INTO scans(
                    badge_id,
                    scanned_at,
                    station_name,
                    employee_full_name,
                    legacy_id,
                    sl_l1_desc,
                    position_desc,
                    email,
                    scan_source
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    badge_id,
                    timestamp,
                    station_name,
                    employee.full_name if employee else None,
                    employee.legacy_id if employee else None,
                    employee.sl_l1_desc if employee else None,
                    employee.position_desc if employee else None,
                    employee.email if employee else None,
                    scan_source,
                ),
            )

    def get_recent_scans(self, limit: int = 25) -> List[ScanRecord]:
        cursor = self._connection.execute(
            """
            SELECT id, badge_id, scanned_at, station_name,
                   employee_full_name, legacy_id, sl_l1_desc, position_desc,
                   email, scan_source, sync_status, synced_at, sync_error
            FROM scans
            ORDER BY scanned_at DESC
            LIMIT ?
            """,
            (limit,),
        )
        return [
            ScanRecord(
                id=row["id"],
                badge_id=row["badge_id"],
                scanned_at=row["scanned_at"],
                station_name=row["station_name"],
                employee_full_name=row["employee_full_name"],
                legacy_id=row["legacy_id"],
                sl_l1_desc=row["sl_l1_desc"],
                position_desc=row["position_desc"],
                email=row["email"],
                scan_source=row["scan_source"],
                sync_status=row["sync_status"],
                synced_at=row["synced_at"],
                sync_error=row["sync_error"],
            )
            for row in cursor.fetchall()
        ]

    def count_employees(self) -> int:
        cursor = self._connection.execute("SELECT COUNT(1) FROM employees")
        return int(cursor.fetchone()[0])

    def get_employees_by_bu(self) -> list[dict]:
        """Get employee count grouped by Business Unit (SL L1 Desc).

        Returns:
            List of dicts with 'bu_name' and 'count' keys, sorted by BU name.
        """
        cursor = self._connection.execute("""
            SELECT sl_l1_desc AS bu_name, COUNT(*) AS count
            FROM employees
            GROUP BY sl_l1_desc
            ORDER BY sl_l1_desc
        """)
        return [{"bu_name": row["bu_name"], "count": row["count"]} for row in cursor.fetchall()]

    def count_scans_total(self) -> int:
        cursor = self._connection.execute("SELECT COUNT(1) FROM scans")
        return int(cursor.fetchone()[0])

    def count_scans_today(self) -> int:
        cursor = self._connection.execute(
            "SELECT COUNT(1) FROM scans WHERE DATE(scanned_at, 'localtime') = DATE('now', 'localtime')"
        )
        return int(cursor.fetchone()[0])

    def fetch_all_scans(self) -> List[ScanRecord]:
        cursor = self._connection.execute(
            """
            SELECT id, badge_id, scanned_at, station_name,
                   employee_full_name, legacy_id, sl_l1_desc, position_desc,
                   email, scan_source, sync_status, synced_at, sync_error
            FROM scans
            ORDER BY scanned_at ASC
            """
        )
        return [
            ScanRecord(
                id=row["id"],
                badge_id=row["badge_id"],
                scanned_at=row["scanned_at"],
                station_name=row["station_name"],
                employee_full_name=row["employee_full_name"],
                legacy_id=row["legacy_id"],
                sl_l1_desc=row["sl_l1_desc"],
                position_desc=row["position_desc"],
                email=row["email"],
                scan_source=row["scan_source"],
                sync_status=row["sync_status"],
                synced_at=row["synced_at"],
                sync_error=row["sync_error"],
            )
            for row in cursor.fetchall()
        ]

    def check_if_duplicate_badge(
        self,
        badge_id: str,
        station_name: str,
        time_window_seconds: int = 60,
    ) -> tuple[bool, Optional[int]]:
        """
        Check if a badge was recently scanned at the same station.

        This prevents accidental duplicate scans within a time window.

        Args:
            badge_id: The badge ID to check
            station_name: The station where scan occurred
            time_window_seconds: Time window to check (default 60s)

        Returns:
            (is_duplicate: bool, original_scan_id: Optional[int])
            - is_duplicate=True if badge was scanned within window
            - original_scan_id=ID of the original scan if duplicate
        """
        # Calculate cutoff time (now - time_window)
        cutoff_time = datetime.now(timezone.utc) - timedelta(seconds=time_window_seconds)
        cutoff_timestamp = cutoff_time.strftime("%Y-%m-%dT%H:%M:%SZ")

        logger.info(
            f"DuplicateCheck: badge={badge_id}, station={station_name}, "
            f"window={time_window_seconds}s, cutoff={cutoff_timestamp}"
        )

        # Query: Find most recent scan with same badge at same station within window
        cursor = self._connection.execute(
            """
            SELECT id FROM scans
            WHERE badge_id = ?
            AND station_name = ?
            AND scanned_at >= ?
            ORDER BY scanned_at DESC
            LIMIT 1
            """,
            (badge_id, station_name, cutoff_timestamp),
        )

        result = cursor.fetchone()
        if result:
            logger.info(f"DuplicateCheck: FOUND duplicate scan (id={result[0]})")
        else:
            logger.info(f"DuplicateCheck: No duplicate found for {badge_id} at {station_name}")
        if result:
            return True, result["id"]
        return False, None

    def check_if_duplicate_employee(
        self,
        legacy_id: str,
        station_name: str,
        time_window_seconds: int = 60,
    ) -> tuple[bool, Optional[int]]:
        """Check if an employee (by legacy_id) was recently scanned at the same station."""
        cutoff_time = datetime.now(timezone.utc) - timedelta(seconds=time_window_seconds)
        cutoff_timestamp = cutoff_time.strftime("%Y-%m-%dT%H:%M:%SZ")

        cursor = self._connection.execute(
            """
            SELECT id FROM scans
            WHERE legacy_id = ?
            AND station_name = ?
            AND scanned_at >= ?
            ORDER BY scanned_at DESC
            LIMIT 1
            """,
            (legacy_id, station_name, cutoff_timestamp),
        )

        result = cursor.fetchone()
        if result:
            logger.info(f"DuplicateCheck: FOUND duplicate employee (legacy_id={legacy_id}, scan_id={result[0]})")
            return True, result["id"]
        return False, None

    def fetch_pending_scans(self, limit: int = 100) -> List[ScanRecord]:
        """Fetch scans that need to be synced to cloud."""
        cursor = self._connection.execute(
            """
            SELECT id, badge_id, scanned_at, station_name,
                   employee_full_name, legacy_id, sl_l1_desc, position_desc,
                   email, scan_source, sync_status, synced_at, sync_error
            FROM scans
            WHERE sync_status = 'pending'
            ORDER BY scanned_at ASC
            LIMIT ?
            """,
            (limit,),
        )
        return [
            ScanRecord(
                id=row["id"],
                badge_id=row["badge_id"],
                scanned_at=row["scanned_at"],
                station_name=row["station_name"],
                employee_full_name=row["employee_full_name"],
                legacy_id=row["legacy_id"],
                sl_l1_desc=row["sl_l1_desc"],
                position_desc=row["position_desc"],
                email=row["email"],
                scan_source=row["scan_source"],
                sync_status=row["sync_status"],
                synced_at=row["synced_at"],
                sync_error=row["sync_error"],
            )
            for row in cursor.fetchall()
        ]

    def mark_scans_as_synced(self, scan_ids: List[int]) -> int:
        """Mark scans as successfully synced to cloud."""
        if not scan_ids:
            return 0
        timestamp = datetime.now(timezone.utc).strftime(ISO_TIMESTAMP_FORMAT)
        placeholders = ",".join("?" * len(scan_ids))
        with self._connection:
            cursor = self._connection.execute(
                f"""
                UPDATE scans
                SET sync_status = 'synced',
                    synced_at = ?,
                    sync_error = NULL
                WHERE id IN ({placeholders})
                """,
                [timestamp] + scan_ids,
            )
        return cursor.rowcount

    def mark_scans_as_failed(self, scan_ids: List[int], error_message: str) -> int:
        """Mark scans as failed to sync with error message."""
        if not scan_ids:
            return 0
        placeholders = ",".join("?" * len(scan_ids))
        with self._connection:
            cursor = self._connection.execute(
                f"""
                UPDATE scans
                SET sync_status = 'failed',
                    sync_error = ?
                WHERE id IN ({placeholders})
                """,
                [error_message[:500]] + scan_ids,  # Limit error message length
            )
        return cursor.rowcount

    def get_sync_statistics(self) -> Dict[str, Any]:
        """Get sync statistics for UI display."""
        cursor = self._connection.execute(
            """
            SELECT
                COUNT(*) FILTER (WHERE sync_status = 'pending') as pending,
                COUNT(*) FILTER (WHERE sync_status = 'synced') as synced,
                COUNT(*) FILTER (WHERE sync_status = 'failed') as failed,
                MAX(synced_at) as last_sync_time
            FROM scans
            """
        )
        row = cursor.fetchone()
        return {
            "pending": int(row["pending"] or 0),
            "synced": int(row["synced"] or 0),
            "failed": int(row["failed"] or 0),
            "last_sync_time": row["last_sync_time"],
        }

    def get_scans_by_bu(self) -> list[dict]:
        """Get unique scanned badge count grouped by BU using local data."""
        cursor = self._connection.execute("""
            SELECT
                e.sl_l1_desc AS bu_name,
                COUNT(DISTINCT e.legacy_id) AS registered,
                COUNT(DISTINCT s.badge_id) AS scanned
            FROM employees e
            LEFT JOIN scans s ON e.legacy_id = s.badge_id
            GROUP BY e.sl_l1_desc
            ORDER BY e.sl_l1_desc
        """)
        return [
            {"bu_name": row["bu_name"], "registered": row["registered"], "scanned": row["scanned"]}
            for row in cursor.fetchall()
        ]

    def count_unmatched_scanned_badges(self) -> int:
        """Count distinct badge_ids in scans that don't match any employee."""
        cursor = self._connection.execute("""
            SELECT COUNT(DISTINCT s.badge_id) AS cnt
            FROM scans s
            LEFT JOIN employees e ON s.badge_id = e.legacy_id
            WHERE e.legacy_id IS NULL
        """)
        return int(cursor.fetchone()["cnt"] or 0)

    def clear_all_scans(self) -> int:
        """Clear all scan records from local database. Preserves station name. Returns scan count deleted."""
        cursor = self._connection.execute("SELECT COUNT(*) FROM scans")
        count = int(cursor.fetchone()[0])
        with self._connection:
            self._connection.execute("DELETE FROM scans")
            self._connection.execute("DELETE FROM sqlite_sequence WHERE name='scans'")
        logger.info(f"Cleared {count} local scan records (station name preserved)")
        return count

    def get_meta(self, key: str) -> Optional[str]:
        """Get a value from the local roster_meta key-value store."""
        cursor = self._connection.execute(
            "SELECT value FROM roster_meta WHERE key = ?", (key,)
        )
        row = cursor.fetchone()
        return row["value"] if row else None

    def set_meta(self, key: str, value: str) -> None:
        """Set a value in the local roster_meta key-value store."""
        with self._connection:
            self._connection.execute(
                "INSERT INTO roster_meta (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, value),
            )

    def count_scans_total(self) -> int:
        """Count total scan records in local database."""
        cursor = self._connection.execute("SELECT COUNT(*) AS cnt FROM scans")
        return int(cursor.fetchone()["cnt"] or 0)

    def close(self) -> None:
        self._connection.close()


__all__ = [
    "DatabaseManager",
    "EmployeeRecord",
    "ScanRecord",
    "ISO_TIMESTAMP_FORMAT",
]




