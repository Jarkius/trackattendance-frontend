"""Core attendance application services."""

from __future__ import annotations

import logging
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from openpyxl import Workbook, load_workbook
from openpyxl.utils import get_column_letter
from PyQt6.QtWidgets import QInputDialog, QMessageBox, QWidget

from database import DatabaseManager, EmployeeRecord, ScanRecord

LOGGER = logging.getLogger(__name__)
REQUIRED_COLUMNS = ["Legacy ID", "Full Name", "SL L1 Desc", "Position Desc"]


DISPLAY_TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"
class AttendanceService:
    """High-level operations for coordinating scans, employees, and exports."""

    def __init__(
        self,
        *,
        database_path: Path,
        employee_workbook_path: Path,
        export_directory: Path,
    ) -> None:
        self._db = DatabaseManager(database_path)
        self._employee_workbook_path = employee_workbook_path
        self._export_directory = export_directory
        self._export_directory.mkdir(parents=True, exist_ok=True)
        self._employee_headers: List[str] = list(REQUIRED_COLUMNS)
        self._employee_cache: Dict[str, EmployeeRecord] = {}
        self._station_name: Optional[str] = self._db.get_station_name()

        self._bootstrap_employee_directory()
        self._employee_cache = self._db.load_employee_cache()

    def _bootstrap_employee_directory(self) -> None:
        if self._db.employees_loaded():
            return
        if not self._employee_workbook_path.exists():
            LOGGER.warning("Employee workbook not found at %s", self._employee_workbook_path)
            return
        workbook = load_workbook(self._employee_workbook_path, read_only=True)
        try:
            sheet = workbook.active
            header_row = next(sheet.iter_rows(min_row=1, max_row=1, values_only=True))
            ordered_headers = [
                str(name).strip()
                for name in header_row
                if name and str(name).strip()
            ]
            if ordered_headers:
                self._employee_headers = ordered_headers
            header_to_index = {name: idx for idx, name in enumerate(header_row) if name}
            missing = [name for name in REQUIRED_COLUMNS if name not in header_to_index]
            if missing:
                LOGGER.error("Employee workbook missing columns: %s", ", ".join(missing))
                return

            seen_ids: set[str] = set()
            employees: List[EmployeeRecord] = []
            for row in sheet.iter_rows(min_row=2, values_only=True):
                legacy_id_raw = row[header_to_index["Legacy ID"]]
                if legacy_id_raw is None:
                    continue
                legacy_id = str(legacy_id_raw).strip()
                if not legacy_id or legacy_id in seen_ids:
                    continue
                full_name = _safe_string(row[header_to_index["Full Name"]])
                sl_l1_desc = _safe_string(row[header_to_index["SL L1 Desc"]])
                position_desc = _safe_string(row[header_to_index["Position Desc"]])
                employees.append(
                    EmployeeRecord(
                        legacy_id=legacy_id,
                        full_name=full_name,
                        sl_l1_desc=sl_l1_desc,
                        position_desc=position_desc,
                    )
                )
                seen_ids.add(legacy_id)
            if employees:
                inserted = self._db.bulk_insert_employees(employees)
                LOGGER.info("Imported %s employees from workbook", inserted)
        finally:
            workbook.close()

    def ensure_station_configured(self, parent: Optional[QWidget] = None) -> str:
        station = self._station_name or self._db.get_station_name()
        if station:
            self._station_name = station
            return station
        while True:
            name, ok = QInputDialog.getText(
                parent,
                "Station Setup",
                "Enter the station name:",
            )
            if not ok:
                QMessageBox.information(
                    parent,
                    "Station Required",
                    "A station name is required to continue. The application will now close.",
                )
                if parent is not None:
                    parent.close()
                self._db.close()
                sys.exit(0)
            sanitized = name.strip()
            if not sanitized:
                QMessageBox.warning(parent, "Invalid Name", "Please provide a non-empty station name.")
                continue
            self._db.set_station_name(sanitized)
            self._station_name = sanitized
            return sanitized

    @property
    def station_name(self) -> str:
        if self._station_name is None:
            station = self._db.get_station_name()
            if station is None:
                raise RuntimeError("Station name not configured")
            self._station_name = station
        return self._station_name

    def get_initial_payload(self) -> Dict[str, object]:
        history = self._db.get_recent_scans()
        return {
            "stationName": self.station_name,
            "totalEmployees": self._db.count_employees(),
            "totalScansToday": self._db.count_scans_today(),
            "totalScansOverall": self._db.count_scans_total(),
            "scanHistory": [_scan_to_dict(scan) for scan in history],
        }

    def register_scan(self, badge_id: str) -> Dict[str, object]:
        sanitized = badge_id.strip()
        if not sanitized:
            return {
                "ok": False,
                "message": "Badge ID is required.",
            }
        employee = self._employee_cache.get(sanitized)
        timestamp = datetime.now().replace(microsecond=0).isoformat()
        self._db.record_scan(sanitized, self.station_name, employee, timestamp)
        history = self._db.get_recent_scans()
        payload = {
            "ok": True,
            "badgeId": sanitized,
            "fullName": employee.full_name if employee else "Unknown",
            "matched": employee is not None,
            "timestamp": timestamp,
            "totalScansToday": self._db.count_scans_today(),
            "totalScansOverall": self._db.count_scans_total(),
            "scanHistory": [_scan_to_dict(scan) for scan in history],
        }
        return payload

    def export_scans(self) -> Dict[str, object]:
        scans = self._db.fetch_all_scans()
        export_path = self._build_export_path()
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Scans"

        employee_columns = [
            header
            for header in self._employee_headers
            if header in REQUIRED_COLUMNS
        ]
        if not employee_columns:
            employee_columns = list(REQUIRED_COLUMNS)

        export_headers = ["Submitted Value", "Matched"] + employee_columns + ["Station ID", "Timestamp"]
        sheet.append(export_headers)

        for record in scans:
            values_by_header = {
                "Legacy ID": record.legacy_id or "",
                "Full Name": record.employee_full_name or "Unknown",
                "SL L1 Desc": record.sl_l1_desc or "",
                "Position Desc": record.position_desc or "",
            }
            matched = record.legacy_id is not None
            row = [
                record.badge_id or "",
                "Yes" if matched else "No",
            ]
            row.extend(values_by_header.get(header, "") for header in employee_columns)
            row.extend([record.station_name or "", _format_timestamp(record.scanned_at)])
            sheet.append(row)

        for col_idx, header in enumerate(export_headers, start=1):
            max_length = len(header)
            for column_cells in sheet.iter_cols(min_col=col_idx, max_col=col_idx, min_row=2, max_row=sheet.max_row, values_only=True):
                for value in column_cells:
                    if value is None:
                        continue
                    max_length = max(max_length, len(str(value)))
            sheet.column_dimensions[get_column_letter(col_idx)].width = min(max_length + 2, 60)
        workbook.save(export_path)
        workbook.close()
        return {
            "ok": True,
            "fileName": export_path.name,
            "absolutePath": str(export_path),
            "records": len(scans),
        }

    def _build_export_path(self) -> Path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_station = _sanitize_filename_component(self.station_name)
        filename = f"Checkins_{safe_station}_{timestamp}.xlsx"
        return self._export_directory / filename

    def close(self) -> None:
        self._db.close()


def _sanitize_filename_component(component: str) -> str:
    fallback = "station"
    sanitized = re.sub(r"[^A-Za-z0-9_-]+", "-", component).strip("-")
    return sanitized or fallback


def _safe_string(value: Optional[object]) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _format_timestamp(value: Optional[str]) -> str:
    if not value:
        return ""
    try:
        return datetime.fromisoformat(value).strftime(DISPLAY_TIMESTAMP_FORMAT)
    except ValueError:
        return value


def _scan_to_dict(record: ScanRecord) -> Dict[str, object]:
    return {
        "badgeId": record.badge_id,
        "timestamp": record.scanned_at,
        "fullName": record.employee_full_name or "Unknown",
        "station": record.station_name,
        "legacyId": record.legacy_id,
        "slL1Desc": record.sl_l1_desc,
        "positionDesc": record.position_desc,
        "matched": record.legacy_id is not None,
    }


__all__ = ["AttendanceService"]
