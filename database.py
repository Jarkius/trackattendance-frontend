"""Database management utilities for the attendance application."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional

ISO_TIMESTAMP_FORMAT = "%Y-%m-%dT%H:%M:%S"


@dataclass(frozen=True)
class EmployeeRecord:
    legacy_id: str
    full_name: str
    sl_l1_desc: str
    position_desc: str


@dataclass(frozen=True)
class ScanRecord:
    badge_id: str
    scanned_at: str
    station_name: str
    employee_full_name: Optional[str]
    legacy_id: Optional[str]
    sl_l1_desc: Optional[str]
    position_desc: Optional[str]


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
                    position_desc TEXT
                );
                """
            )

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

    def bulk_insert_employees(self, employees: Iterable[EmployeeRecord]) -> int:
        rows = [
            (
                employee.legacy_id.strip(),
                employee.full_name.strip(),
                employee.sl_l1_desc.strip(),
                employee.position_desc.strip(),
            )
            for employee in employees
        ]
        with self._connection:
            self._connection.executemany(
                "INSERT OR IGNORE INTO employees(legacy_id, full_name, sl_l1_desc, position_desc)"
                " VALUES(?, ?, ?, ?)",
                rows,
            )
        return len(rows)

    def load_employee_cache(self) -> Dict[str, EmployeeRecord]:
        cursor = self._connection.execute(
            "SELECT legacy_id, full_name, sl_l1_desc, position_desc FROM employees"
        )
        return {
            row["legacy_id"]: EmployeeRecord(
                legacy_id=row["legacy_id"],
                full_name=row["full_name"],
                sl_l1_desc=row["sl_l1_desc"],
                position_desc=row["position_desc"],
            )
            for row in cursor.fetchall()
        }

    def record_scan(
        self,
        badge_id: str,
        station_name: str,
        employee: Optional[EmployeeRecord],
        scanned_at: Optional[str] = None,
    ) -> None:
        timestamp = scanned_at or datetime.now().strftime(ISO_TIMESTAMP_FORMAT)
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
                    position_desc
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    badge_id,
                    timestamp,
                    station_name,
                    employee.full_name if employee else None,
                    employee.legacy_id if employee else None,
                    employee.sl_l1_desc if employee else None,
                    employee.position_desc if employee else None,
                ),
            )

    def get_recent_scans(self, limit: int = 25) -> List[ScanRecord]:
        cursor = self._connection.execute(
            """
            SELECT badge_id, scanned_at, station_name,
                   employee_full_name, legacy_id, sl_l1_desc, position_desc
            FROM scans
            ORDER BY scanned_at DESC
            LIMIT ?
            """,
            (limit,),
        )
        return [
            ScanRecord(
                badge_id=row["badge_id"],
                scanned_at=row["scanned_at"],
                station_name=row["station_name"],
                employee_full_name=row["employee_full_name"],
                legacy_id=row["legacy_id"],
                sl_l1_desc=row["sl_l1_desc"],
                position_desc=row["position_desc"],
            )
            for row in cursor.fetchall()
        ]

    def count_employees(self) -> int:
        cursor = self._connection.execute("SELECT COUNT(1) FROM employees")
        return int(cursor.fetchone()[0])

    def count_scans_total(self) -> int:
        cursor = self._connection.execute("SELECT COUNT(1) FROM scans")
        return int(cursor.fetchone()[0])

    def count_scans_today(self) -> int:
        cursor = self._connection.execute(
            "SELECT COUNT(1) FROM scans WHERE DATE(scanned_at) = DATE('now','localtime')"
        )
        return int(cursor.fetchone()[0])

    def fetch_all_scans(self) -> List[ScanRecord]:
        cursor = self._connection.execute(
            """
            SELECT badge_id, scanned_at, station_name,
                   employee_full_name, legacy_id, sl_l1_desc, position_desc
            FROM scans
            ORDER BY scanned_at ASC
            """
        )
        return [
            ScanRecord(
                badge_id=row["badge_id"],
                scanned_at=row["scanned_at"],
                station_name=row["station_name"],
                employee_full_name=row["employee_full_name"],
                legacy_id=row["legacy_id"],
                sl_l1_desc=row["sl_l1_desc"],
                position_desc=row["position_desc"],
            )
            for row in cursor.fetchall()
        ]

    def close(self) -> None:
        self._connection.close()


__all__ = [
    "DatabaseManager",
    "EmployeeRecord",
    "ScanRecord",
    "ISO_TIMESTAMP_FORMAT",
]




