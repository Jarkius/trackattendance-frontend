"""Core attendance application services."""

from __future__ import annotations

import hashlib
import logging
import re
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from openpyxl import Workbook, load_workbook
from openpyxl.utils import get_column_letter

from excel_safety import neutralize_formulas
from PyQt6.QtWidgets import QInputDialog, QMessageBox, QWidget

from database import (
    DatabaseManager, EmployeeRecord, ScanRecord, ISO_TIMESTAMP_FORMAT,
    clean_badge_id, normalize_badge_id,
)

LOGGER = logging.getLogger(__name__)
# Bump when the set of roster columns stored in `employees` changes, so a roster
# imported by an older build is re-imported once even if employee.xlsx is
# byte-identical (v2: Career Level; v3: re-import after v2 stored it empty).
ROSTER_IMPORT_VERSION = "3"
REQUIRED_COLUMNS = ["Legacy ID", "Full Name", "SL L1 Desc", "Position Desc"]
OPTIONAL_EMAIL_COLUMN = "Email"
OPTIONAL_CAREER_LEVEL_COLUMN = "Career Level"
EXAMPLE_WORKBOOK_NAME = "exampleof_employee.xlsx"

# Invisible characters that Excel/copy-paste commonly leave in header cells.
_INVISIBLE_HEADER_CHARS = dict.fromkeys(
    map(ord, "\u200b\u200c\u200d\u2060\ufeff"), None
)


def _clean_header(value: object) -> str:
    """Display form of a header cell: no zero-width chars, NBSP as space, trimmed."""
    if value is None:
        return ""
    text = str(value).translate(_INVISIBLE_HEADER_CHARS).replace("\u00a0", " ")
    return " ".join(text.split())


def _normalise_header(value: object) -> str:
    """Comparison key for a header cell (cleaned and case-insensitive)."""
    return _clean_header(value).casefold()


def map_roster_headers(header_row) -> Dict[str, int]:
    """Map canonical column names (required + optional Email/Career Level) to column indices.

    Shared by validate_roster_headers and the roster import so both agree on
    what counts as a matching header. First matching column wins.
    """
    by_key: Dict[str, int] = {}
    for idx, cell in enumerate(header_row):
        key = _normalise_header(cell)
        if key and key not in by_key:
            by_key[key] = idx
    mapping: Dict[str, int] = {}
    for canonical in [*REQUIRED_COLUMNS, OPTIONAL_EMAIL_COLUMN, OPTIONAL_CAREER_LEVEL_COLUMN]:
        idx = by_key.get(_normalise_header(canonical))
        if idx is not None:
            mapping[canonical] = idx
    return mapping


def _one_line(message: str) -> str:
    return " ".join(message.split())


def _legacy_id_from_cell(cell) -> tuple[str, bool]:
    """Read a Legacy ID cell. Returns (id_text, lost_leading_zeros_risk).

    Numeric cells lose leading zeros in Excel. When the cell's number format is
    all zeros (e.g. ``00000``) the value is zero-padded to that width. Any other
    numeric cell keeps ``str(int)`` and is flagged so the operator gets a warning.
    Integral floats are treated as ints.
    """
    value = getattr(cell, "value", None)
    if value is None:
        return "", False
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return clean_badge_id(value), False
    if isinstance(value, float):
        if not value.is_integer():
            return clean_badge_id(value), False
        value = int(value)
    text = str(value)
    fmt = getattr(cell, "number_format", None) or ""
    if value >= 0 and re.fullmatch(r"0+", fmt):
        return text.zfill(len(fmt)), False
    return text, True


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
        self._example_employee_workbook_path = self._employee_workbook_path.with_name(EXAMPLE_WORKBOOK_NAME)
        self._export_directory = export_directory
        self._export_directory.mkdir(parents=True, exist_ok=True)
        self._employee_headers: List[str] = list(REQUIRED_COLUMNS)
        self._employee_cache: Dict[str, EmployeeRecord] = {}
        self._roster_warning: Optional[str] = None
        self._station_name: Optional[str] = self._db.get_station_name()

        try:
            self._bootstrap_employee_directory()
        except ValueError as e:
            LOGGER.error("Roster bootstrap error: %s", e)
            self._roster_error = str(e)
        else:
            self._roster_error = None
        self._employee_cache = self._db.load_employee_cache()
        self._roster_warning = self._db.get_roster_meta("roster_warning") or None
        zero_warning = self._leading_zero_mismatch_warning()
        if zero_warning:
            LOGGER.warning("Roster: %s", zero_warning)
            self._roster_warning = (
                f"{self._roster_warning}\n\n{zero_warning}" if self._roster_warning else zero_warning
            )
        self._sync_service = None  # Set via set_sync_service() for immediate-write sync
        self._sync_coordinator = None  # Set via set_sync_service() for immediate-write sync

    def _zero_stripped_roster_index(self) -> Dict[str, str]:
        """Roster IDs keyed by their form without leading zeros ("00123" and "123" -> "123")."""
        index: Dict[str, str] = {}
        for key in self._employee_cache:
            stripped = key.lstrip("0")
            if stripped and key.isascii() and key.isdigit():
                index.setdefault(stripped, key)
        return index

    def _leading_zero_mismatch_warning(self) -> str:
        """Warn when scanned badges miss the roster only because of leading zeros.

        Direct evidence that the roster's Legacy IDs lost (or gained) zero padding,
        which the import-time width check cannot see when every ID has the same
        stored width. Returns "" when nothing is wrong or there is no roster/scans.
        """
        if not self._employee_cache:
            return ""
        index = self._zero_stripped_roster_index()
        if not index:
            return ""
        examples: List[str] = []
        seen = set()
        for badge in self._db.fetch_distinct_badge_ids():
            key = normalize_badge_id(badge)
            if key in self._employee_cache or key in seen:
                continue
            if key.isascii() and key.isdigit() and index.get(key.lstrip("0")) not in (None, key):
                seen.add(key)
                if len(examples) < 3:
                    examples.append(f"{key} vs roster {index[key.lstrip('0')]}")
        if not seen:
            return ""
        return (
            f"{len(seen)} scanned badge ID(s) do not match the roster but match an ID that "
            f"differs only by leading zeros (e.g. {'; '.join(examples)}). "
            f"Format the Legacy ID column as Text (or as 00000) and re-save the roster."
        )

    def set_sync_service(self, sync_service, coordinator=None) -> None:
        """Attach SyncService for immediate per-scan cloud upload.

        coordinator: shared BackgroundSyncCoordinator (from main.py) used to
        enqueue the immediate-write upload instead of spawning a raw thread
        per scan. If not supplied, immediate-write is disabled (register_scan()
        checks for this) rather than falling back to a per-scan threading.Thread.
        """
        self._sync_service = sync_service
        self._sync_coordinator = coordinator

    def employees_loaded(self) -> bool:
        return self._db.employees_loaded()

    def validate_roster_headers(self, workbook_path: Path) -> tuple[bool, str]:
        """
        Validate that an employee workbook has required columns.

        Returns:
            (is_valid, error_message)
        """
        if not workbook_path.exists():
            return False, f"Roster file not found: {workbook_path.name}"

        try:
            workbook = load_workbook(workbook_path, read_only=True)
            try:
                sheet = workbook.active
                header_row = next(sheet.iter_rows(min_row=1, max_row=1, values_only=True))
            finally:
                workbook.close()

            # Check for header row
            if not header_row or all(cell is None for cell in header_row):
                return False, "Roster file has no headers (first row is empty)"

            # Extract non-empty headers (cleaned display form)
            actual_headers = {
                _clean_header(name) for name in header_row
                if _clean_header(name)
            }

            # Check for required columns (same normalisation as the import)
            mapping = map_roster_headers(header_row)
            missing = [col for col in REQUIRED_COLUMNS if col not in mapping]

            if missing:
                msg = f"Roster missing required columns:\n\n"
                msg += f"Missing: {', '.join(missing)}\n\n"
                msg += f"Required: {', '.join(REQUIRED_COLUMNS)}\n\n"
                msg += f"Found: {', '.join(sorted(actual_headers)) if actual_headers else '(none)'}"
                return False, msg

            return True, "Roster headers valid"

        except Exception as e:
            return False, f"Error reading roster file: {str(e)}"

    def _bootstrap_employee_directory(self) -> None:
        if not self._employee_workbook_path.exists():
            LOGGER.warning("Employee workbook not found at %s", self._employee_workbook_path)
            self.ensure_example_employee_workbook()
            return

        # Fast path: skip SHA256 if file modification time hasn't changed
        current_mtime = str(self._employee_workbook_path.stat().st_mtime)
        stored_mtime = self._db.get_roster_meta("file_mtime")
        stored_hash = self._db.get_roster_hash()
        import_current = self._db.get_roster_meta("import_version") == ROSTER_IMPORT_VERSION

        if import_current and stored_mtime == current_mtime and stored_hash and self._db.employees_loaded():
            LOGGER.info("Roster unchanged (mtime match), skipping reimport")
            return

        # Mtime changed (or first run) — compute hash to confirm
        current_hash = self._hash_file(self._employee_workbook_path)

        if import_current and stored_hash == current_hash and self._db.employees_loaded():
            # File was touched but content unchanged — update mtime cache
            self._db.set_roster_meta("file_mtime", current_mtime)
            LOGGER.info("Roster unchanged (hash match, mtime updated), skipping reimport")
            return

        if stored_hash and stored_hash != current_hash:
            LOGGER.info("Roster file changed (hash mismatch), reimporting employees")

        # Validate roster headers before import
        from config import ROSTER_VALIDATION_ENABLED, ROSTER_STRICT_VALIDATION
        is_valid, validation_msg = self.validate_roster_headers(self._employee_workbook_path)

        if not is_valid:
            if ROSTER_VALIDATION_ENABLED:
                LOGGER.error("Roster validation failed: %s", validation_msg)
                if ROSTER_STRICT_VALIDATION:
                    LOGGER.error("Strict validation enabled - skipping import")
                    raise ValueError(
                        f"Roster not imported. {_one_line(validation_msg)} "
                        f"Fix {self._employee_workbook_path.name} and restart the application."
                    )
            else:
                LOGGER.warning("Roster validation skipped (disabled): %s", validation_msg)

        # A corrupt/malformed .xlsx (bad zip, truncated file, wrong format
        # despite the extension) raises here — e.g. BadZipFile, KeyError,
        # openpyxl's InvalidFileException — none of which are ValueError, so
        # without this they'd bypass __init__'s `except ValueError` and crash
        # the whole app at startup instead of degrading gracefully like the
        # duplicate-Legacy-ID case below already does.
        try:
            workbook = load_workbook(self._employee_workbook_path, read_only=True)
        except Exception as e:
            LOGGER.error("Roster: failed to open workbook %s: %s", self._employee_workbook_path, e)
            raise ValueError(
                f"Could not open roster file {self._employee_workbook_path.name}: {e}. "
                f"Fix or replace employee.xlsx and restart the application."
            ) from e
        try:
            sheet = workbook.active
            header_row = next(sheet.iter_rows(min_row=1, max_row=1, values_only=True), None)
            if not header_row:
                raise ValueError(
                    f"Roster not imported: {self._employee_workbook_path.name} has no header row. "
                    f"Fix the file and restart the application."
                )
            ordered_headers = [_clean_header(name) for name in header_row if _clean_header(name)]
            if ordered_headers:
                self._employee_headers = ordered_headers
            header_to_index = map_roster_headers(header_row)
            missing = [name for name in REQUIRED_COLUMNS if name not in header_to_index]
            if missing:
                LOGGER.error("Employee workbook missing columns: %s", ", ".join(missing))
                raise ValueError(
                    f"Roster not imported: missing required column(s): {', '.join(missing)}. "
                    f"Fix {self._employee_workbook_path.name} and restart the application."
                )

            # Detect optional columns present in this workbook
            email_index = header_to_index.get(OPTIONAL_EMAIL_COLUMN)
            career_level_index = header_to_index.get(OPTIONAL_CAREER_LEVEL_COLUMN)

            seen_ids: dict[str, int] = {}  # legacy_id → first row number
            duplicates: list[dict] = []  # detailed duplicate info
            employees: List[EmployeeRecord] = []
            row_num = 1  # header is row 1
            legacy_col = header_to_index["Legacy ID"]
            # Widths of numeric-format IDs, and the widest all-digit ID of any kind.
            # A numeric ID can only have lost leading zeros if it is shorter than that.
            numeric_widths: List[int] = []
            widest_digit_id = 0
            for row_cells in sheet.iter_rows(min_row=2):
                row_num += 1
                row = tuple(getattr(c, "value", None) for c in row_cells)
                if legacy_col >= len(row_cells):
                    continue
                legacy_id, numeric_risk = _legacy_id_from_cell(row_cells[legacy_col])
                if not legacy_id:
                    continue
                if numeric_risk:
                    numeric_widths.append(len(legacy_id))
                if legacy_id.isascii() and legacy_id.isdigit():
                    widest_digit_id = max(widest_digit_id, len(legacy_id))
                id_key = normalize_badge_id(legacy_id)
                full_name = _safe_string(row[header_to_index["Full Name"]] if header_to_index["Full Name"] < len(row) else None)
                sl_l1_desc = _safe_string(row[header_to_index["SL L1 Desc"]] if header_to_index["SL L1 Desc"] < len(row) else None)
                if id_key in seen_ids:
                    duplicates.append({
                        "legacy_id": legacy_id,
                        "full_name": full_name,
                        "business_unit": sl_l1_desc,
                        "row": row_num,
                        "first_row": seen_ids[id_key],
                    })
                    LOGGER.warning(
                        "Roster: duplicate Legacy ID %s on row %d (first seen row %d) — %s [%s], skipped",
                        legacy_id, row_num, seen_ids[id_key], full_name, sl_l1_desc,
                    )
                    continue
                position_desc = _safe_string(row[header_to_index["Position Desc"]] if header_to_index["Position Desc"] < len(row) else None)
                email = _safe_string(row[email_index] if email_index is not None and email_index < len(row) else None)
                career_level = _normalize_career_level(
                    row[career_level_index] if career_level_index is not None and career_level_index < len(row) else None
                )
                employees.append(
                    EmployeeRecord(
                        legacy_id=legacy_id,
                        full_name=full_name,
                        sl_l1_desc=sl_l1_desc,
                        position_desc=position_desc,
                        email=email,
                        career_level=career_level,
                    )
                )
                seen_ids[id_key] = row_num
            # Abort import if duplicates found — admin must fix the roster first
            if duplicates:
                LOGGER.error(
                    "Roster: IMPORT BLOCKED — %d duplicate Legacy ID(s) found. "
                    "Fix employee.xlsx and restart the application.",
                    len(duplicates),
                )
                report_path = self._export_duplicate_report(duplicates)
                raise ValueError(
                    f"Roster contains {len(duplicates)} duplicate Legacy ID(s). "
                    f"See report: {report_path}. "
                    f"Fix employee.xlsx and restart the application."
                )

            if not employees:
                raise ValueError(
                    f"Roster not imported: {self._employee_workbook_path.name} has no valid "
                    f"employee rows (every Legacy ID is empty). "
                    f"Fix the file and restart the application."
                )

            # Clear old employees and reimport. The hash/mtime are stored only
            # after a successful import, so a fixed file is re-imported.
            try:
                inserted = self._db.replace_employees(employees)
            except sqlite3.DatabaseError as e:
                # The previous roster is still in place (the replace is one transaction).
                raise ValueError(
                    f"Roster not imported: database error while saving employees ({e}). "
                    f"The previous roster is still in use. Restart the application to retry."
                ) from e
            self._db.set_roster_hash(current_hash)
            self._db.set_roster_meta("file_mtime", current_mtime)
            self._db.set_roster_meta("import_version", ROSTER_IMPORT_VERSION)
            numeric_unpadded = sum(1 for w in numeric_widths if w < widest_digit_id)
            if numeric_unpadded:
                warning = (
                    f"{numeric_unpadded} numeric Legacy ID cell(s) in "
                    f"{self._employee_workbook_path.name} use a number format that does not keep "
                    f"leading zeros, so IDs such as 00123 may have been stored as 123. "
                    f"Format the Legacy ID column as Text (or as 00000) and re-save the roster."
                )
                LOGGER.warning("Roster: %s", warning)
            else:
                warning = ""
            self._db.set_roster_meta("roster_warning", warning)
            LOGGER.info("Imported %s employees from workbook (hash: %s)", inserted, current_hash[:12])
            # Roster BU counts will be pushed to cloud after first
            # successful health check (see main.py Api._run_check)
        finally:
            workbook.close()

    def _export_duplicate_report(self, duplicates: list[dict]) -> Optional[Path]:
        """Export duplicate Legacy IDs to an Excel file in the exports directory.

        Returns:
            Path to the exported report, or None if export failed.
        """
        try:
            export_dir = self._export_directory
            export_dir.mkdir(parents=True, exist_ok=True)
            from datetime import datetime
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            path = export_dir / f"Roster_Duplicates_{ts}.xlsx"
            wb = Workbook()
            try:
                ws = wb.active
                ws.title = "Duplicate Legacy IDs"
                ws.append(["Legacy ID", "Name (Skipped)", "Business Unit", "Row in Excel", "First Seen Row"])
                for d in duplicates:
                    ws.append([d["legacy_id"], d["full_name"], d["business_unit"], d["row"], d["first_row"]])
                # Auto-width columns
                for col in ws.columns:
                    max_len = max((len(str(cell.value or "")) for cell in col), default=10)
                    ws.column_dimensions[col[0].column_letter].width = min(max_len + 2, 40)
                neutralize_formulas(wb)
                wb.save(path)
            finally:
                wb.close()
            LOGGER.warning("Roster: duplicate report exported to %s", path)
            return path
        except Exception as exc:
            LOGGER.error("Roster: failed to export duplicate report: %s", exc)
            return None

    @staticmethod
    def _hash_file(path: Path) -> str:
        """Compute SHA256 hash of a file."""
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()

    def ensure_example_employee_workbook(self) -> Path:
        """Ensure a sample employee roster workbook exists for onboarding."""
        path = self._example_employee_workbook_path
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            return path

        workbook = Workbook()
        try:
            sheet = workbook.active
            sheet.title = "Employees"
            # Optional Career Level: 0 = Intern ... 9 = Partner (both excluded from the Lucky Draw).
            sheet.append(REQUIRED_COLUMNS + ["Email", "Career Level"])

            sample_rows = [
                ("100001", "Ada Lovelace", "Consulting", "Analyst", "alovelace@example.com", 2),
                ("100002", "Grace Hopper", "Technology", "Engineer", "ghopper@example.com", 5),
            ]
            for row in sample_rows:
                sheet.append(row)

            neutralize_formulas(workbook)
            workbook.save(path)
        finally:
            workbook.close()
        return path


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
            if len(sanitized) > 50:
                QMessageBox.warning(parent, "Invalid Name", "Station name must be 50 characters or fewer.")
                continue
            if not re.match(r'^[A-Za-z0-9 _-]+$', sanitized):
                QMessageBox.warning(parent, "Invalid Name", "Station name can only contain letters, numbers, spaces, hyphens, and underscores.")
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
        import config
        import os

        history = self._db.get_recent_scans()
        return {
            "stationName": self.station_name,
            "totalEmployees": self._db.count_employees(),
            "totalScansToday": self._db.count_scans_today(),
            "totalScansOverall": self._db.count_scans_total(),
            "scanHistory": [_scan_to_dict(scan) for scan in history],
            "connectionCheckIntervalMs": max(0, int(config.CONNECTION_CHECK_INTERVAL_MS)),
            "connectionCheckInitialDelayMs": max(0, int(config.CONNECTION_CHECK_INITIAL_DELAY_MS)),
            "duplicateBadgeAlertDurationMs": max(0, int(config.DUPLICATE_BADGE_ALERT_DURATION_MS)),
            "scanFeedbackDurationMs": max(0, int(config.SCAN_FEEDBACK_DURATION_MS)),
            "confettiEnabled": bool(config.CONFETTI_ENABLED),
            "debugMode": os.getenv("DEBUG", "False").lower() == "true"
                or getattr(config, '_DEBUG_PANEL_ACTIVE', False),
        }

    def search_employee(self, query: str) -> List[Dict[str, object]]:
        """Search employees by email prefix, partial name, or fuzzy match.

        Search strategy (in order):
        1. Exact email prefix match, or query matches the start of the
           first name (e.g. "j" -> "Jihun Jung")
        2. Query matches the start of a later name word, e.g. a surname
           (e.g. "j" -> "Parichart Jiravachara") — ranked below #1 so a
           first-name match surfaces before a surname match for the same
           query, matching how people expect name search to behave
        3. Substring match anywhere in the full name (lower priority than
           #1/#2 so a short query like "c" doesn't get filled up with
           mid-name hits like "Marcus" before prefix matches are considered).
           Within this tier, ranked by match position — a match earlier in
           the name is a better hit than one buried deep in it.
        4. All individual query words must appear in the name (any order).
           Within this tier, ranked by adjacency — words appearing next to
           each other in the name (in either order) rank above the same
           words scattered apart, since an adjacent match is a closer fit
           to a two-word query like "first last".
        5. Fuzzy fallback — tolerate typos using word-level similarity

        Within tiers 3 and 4, cache iteration order previously decided which
        matches filled the 10-result cap — meaning a worse but earlier-seen
        match could starve out a better one. Explicit secondary sort keys
        below fix that the same way tier 1's first-name-vs-surname split did.
        """
        # Normalize whitespace: collapse multiple spaces into one
        query = " ".join(query.split()).lower()
        if not query:
            return []

        query_words = query.split()
        first_name_prefix_results = []
        other_prefix_results = []
        contains_results = []  # (match_position, employee_dict)
        word_match_results = []  # (adjacency_rank, employee_dict)
        fuzzy_results = []  # (similarity_score, employee_dict)

        for emp in self._employee_cache.values():
            emp_dict = {
                "legacy_id": emp.legacy_id,
                "full_name": emp.full_name,
                "email": emp.email,
                "business_unit": emp.sl_l1_desc,
            }
            email_prefix = emp.email.split("@")[0].lower() if emp.email else ""
            name_lower = " ".join(emp.full_name.split()).lower()
            name_words = name_lower.split()

            # Tier 1: exact email match, or query matches the start of the
            # first name.
            if (email_prefix and email_prefix == query) or (
                name_words and name_words[0].startswith(query)
            ):
                first_name_prefix_results.append(emp_dict)
                continue

            # Tier 2: query matches the start of a later name word (surname,
            # middle name, etc.) — ranked below a first-name match.
            if any(w.startswith(query) for w in name_words[1:]):
                other_prefix_results.append(emp_dict)
                continue

            # Tier 3: substring match anywhere in the name, ranked by how
            # early the match starts.
            match_pos = name_lower.find(query)
            if match_pos != -1:
                contains_results.append((match_pos, emp_dict))
                continue

            # Tier 4: all query words appear somewhere in the name (any
            # order), ranked by adjacency — e.g. "smith john" matches "John
            # Smith" (rank 0, adjacent) ahead of "John Middle Smith" (rank 1).
            if len(query_words) > 1 and all(w in name_lower for w in query_words):
                positions = sorted(name_words.index(w) for w in query_words if w in name_words)
                adjacency_rank = positions[-1] - positions[0] if positions else 0
                word_match_results.append((adjacency_rank, emp_dict))
                continue

            # Tier 5: fuzzy match — each query word must closely match a name word
            # Handles typos like "Smth" → "Smith", "Jhon" → "John"
            if len(query_words) >= 1 and len(query) >= 3:
                score = _fuzzy_word_score(query_words, name_words)
                if score >= 0.75:
                    fuzzy_results.append((score, emp_dict))

        contains_results.sort(key=lambda x: x[0])
        combined_prefix = first_name_prefix_results + other_prefix_results
        if combined_prefix or contains_results:
            return (combined_prefix + [r[1] for r in contains_results])[:10]

        word_match_results.sort(key=lambda x: x[0])
        if word_match_results:
            return [r[1] for r in word_match_results][:10]

        # Sort fuzzy results by score descending, return top matches
        if fuzzy_results:
            fuzzy_results.sort(key=lambda x: x[0], reverse=True)
            return [r[1] for r in fuzzy_results[:10]]

        return []

    def register_scan(self, badge_id: str, scan_source: str = "badge",
                       lookup_legacy_id: str = None) -> Dict[str, object]:
        import re
        import config

        sanitized = badge_id.strip()
        if not sanitized:
            return {
                "ok": False,
                "message": "Badge ID is required.",
            }

        # Only derive scan_source when caller used default (submit_scan passes "badge")
        # Lookup/manual paths pass explicit scan_source — don't override
        if scan_source == "badge":
            scan_source = "badge" if re.match(r'^\d+[A-Za-z]?$', sanitized) else "manual"

        # For lookup: user typed a name but selected an employee — resolve by legacy_id
        # For badge/manual: resolve by the scan value itself
        lookup_key = normalize_badge_id(lookup_legacy_id if lookup_legacy_id else sanitized)
        employee = self._employee_cache.get(lookup_key)
        if employee is None and lookup_key.isascii() and lookup_key.isdigit():
            near = self._zero_stripped_roster_index().get(lookup_key.lstrip("0"))
            if near and near != lookup_key:
                LOGGER.warning(
                    "Scan %s is not in the roster but %s is: IDs differ only by leading zeros "
                    "(check the roster's Legacy ID column format)", lookup_key, near,
                )

        # Check for duplicate badge scan (Issue #20)
        # Check both raw input AND resolved Legacy ID to catch same employee
        # scanned via different methods (badge, lookup, manual)
        is_duplicate = False
        if config.DUPLICATE_BADGE_DETECTION_ENABLED:
            is_dup, original_id = self._db.check_if_duplicate_badge(
                sanitized,
                self.station_name,
                config.DUPLICATE_BADGE_TIME_WINDOW_SECONDS
            )
            is_duplicate = is_dup
            # Also check by legacy_id column — catches same employee via different input
            if not is_duplicate and employee:
                is_dup, original_id = self._db.check_if_duplicate_employee(
                    employee.legacy_id,
                    self.station_name,
                    config.DUPLICATE_BADGE_TIME_WINDOW_SECONDS
                )
                is_duplicate = is_dup

            # If duplicate and action is 'block', reject the scan
            if is_duplicate and config.DUPLICATE_BADGE_ACTION == 'block':
                return {
                    "ok": False,
                    "status": "duplicate_rejected",
                    "message": f"Duplicate: Badge {sanitized} scanned within {config.DUPLICATE_BADGE_TIME_WINDOW_SECONDS} seconds",
                    "is_duplicate": True,
                    "duplicateWindowSeconds": config.DUPLICATE_BADGE_TIME_WINDOW_SECONDS,
                    "badgeId": sanitized,
                    "fullName": employee.full_name if employee else "Unknown",
                }
        # Cross-station duplicates are intentionally NOT checked or blocked
        # in real time here (removed after the 2026-09-03 event): the check
        # required a synchronous cloud round-trip inside this offline-first
        # hot path, and when the network was slow, a barcode double-fire
        # during that wait landed on the not-yet-cleared input field and
        # concatenated into garbage badge values (e.g. "108670108670").
        # Blocking also provided little real benefit — cross-station
        # duplicates were rare (10 out of ~1,500 scans at the event) and are
        # already caught cleanly after the fact via the cross-station dedup
        # sheet in DashboardService.export_to_excel(). Offline-first means
        # the local write should never wait on network reachability; local
        # same-station duplicate detection above (SQLite-only, no network)
        # is unaffected and still runs synchronously.
        timestamp = datetime.now(timezone.utc).strftime(ISO_TIMESTAMP_FORMAT)
        self._db.record_scan(sanitized, self.station_name, employee, timestamp, scan_source=scan_source)

        # Immediate write: upload this scan to cloud right away instead of
        # waiting for the idle-triggered batch sync, via the shared
        # BackgroundSyncCoordinator worker thread. record_scan() above has
        # already committed the scan to SQLite (offline-first: the local
        # write always happens first, regardless of whether this enqueue
        # succeeds). sync_single_scan() performs network I/O only — it
        # never touches self._db — so it's safe to run on the coordinator's
        # worker thread. It never marks the scan as synced itself (that
        # would touch SQLite off the main thread); the row stays 'pending'
        # and the normal idle-triggered batch sync marks it synced later,
        # using the same idempotency key so a redundant re-send is a safe
        # no-op. If the bounded queue is full or the coordinator is
        # unavailable/paused, the scan simply falls back to that same batch
        # path — no scan is ever lost, only its immediate-upload latency.
        if (config.IMMEDIATE_SYNC_ENABLED and not config.CLOUD_READ_ONLY
                and self._sync_service and self._sync_coordinator):
            scan_to_sync = self._db.fetch_last_pending_scan()
            if scan_to_sync:
                sync_service = self._sync_service
                station = self.station_name  # resolved on the main thread, not the worker
                badge_id = scan_to_sync.badge_id

                def _log_result(job_id: int, result: dict) -> None:
                    if result.get("ok"):
                        LOGGER.info("[ImmediateSync] Uploaded badge=%s", badge_id)
                    else:
                        LOGGER.warning(
                            "[ImmediateSync] Failed badge=%s: %s — will be picked up by next batch sync",
                            badge_id, result.get("error") or result.get("message"),
                        )

                def _log_error(job_id: int, exc: Exception) -> None:
                    LOGGER.warning(
                        "[ImmediateSync] Exception for badge=%s: %s — will be picked up by next batch sync",
                        badge_id, exc,
                    )

                job_id = self._sync_coordinator.submit(
                    lambda: sync_service.sync_single_scan(scan_to_sync, station),
                    on_result=_log_result,
                    on_error=_log_error,
                )
                if job_id is None:
                    LOGGER.info(
                        "[ImmediateSync] Coordinator busy for badge=%s — will be picked up by next batch sync",
                        badge_id,
                    )

        history = self._db.get_recent_scans()
        # Only flag as duplicate for UI alert if action is 'warn' (not 'silent')
        # 'silent' mode accepts duplicates without any UI alert
        show_duplicate_alert = is_duplicate and config.DUPLICATE_BADGE_ACTION == 'warn'

        payload = {
            "ok": True,
            "badgeId": sanitized,
            "fullName": employee.full_name if employee else "Unknown",
            "matched": employee is not None,
            "timestamp": timestamp,
            "totalScansToday": self._db.count_scans_today(),
            "totalScansOverall": self._db.count_scans_total(),
            "scanHistory": [_scan_to_dict(scan) for scan in history],
            "is_duplicate": show_duplicate_alert,  # Only true for 'warn' mode
            "duplicateWindowSeconds": config.DUPLICATE_BADGE_TIME_WINDOW_SECONDS,
        }
        return payload

    def export_scans(self, run_blocking=None) -> Dict[str, object]:
        """Write all scans to an Excel file.

        The SQLite read always happens on the calling thread (sqlite3
        connections are thread-affine). When ``run_blocking`` is given, only
        the workbook build/save -- which touches no database -- is passed to
        it (e.g. ``call_without_freezing_ui``) so the GUI thread stays
        responsive for large histories.
        """
        scans = self._db.fetch_all_scans()
        if not scans:
            return {
                "ok": False,
                "noData": True,
                "message": "No scan data to export.",
                "records": 0,
            }
        export_path = self._build_export_path()
        if run_blocking is None:
            self._write_export_workbook(scans, export_path)
        else:
            run_blocking(lambda: self._write_export_workbook(scans, export_path))
        return {
            "ok": True,
            "fileName": export_path.name,
            "absolutePath": str(export_path),
            "records": len(scans),
        }

    @staticmethod
    def _write_export_workbook(scans, export_path: Path) -> None:
        """Build and save the workbook. Pure CPU/file I/O, no database access."""
        workbook = Workbook()
        try:
            sheet = workbook.active
            sheet.title = "Scans"

            export_headers = [
                "Scan Value", "Legacy ID", "Full Name",
                "SL L1 Desc", "Position Desc", "Email",
                "Station", "Scanned At", "Matched", "Scan Source",
            ]
            sheet.append(export_headers)

            for record in scans:
                matched = record.legacy_id is not None
                row = [
                    record.badge_id or "",
                    record.legacy_id or "",
                    record.employee_full_name or "",
                    record.sl_l1_desc or "",
                    record.position_desc or "",
                    record.email or "",
                    record.station_name or "",
                    _format_timestamp(record.scanned_at),
                    "Yes" if matched else "No",
                    record.scan_source or "manual",
                ]
                sheet.append(row)

            for col_idx, header in enumerate(export_headers, start=1):
                max_length = len(header)
                for column_cells in sheet.iter_cols(min_col=col_idx, max_col=col_idx, min_row=2, max_row=sheet.max_row, values_only=True):
                    for value in column_cells:
                        if value is None:
                            continue
                        max_length = max(max_length, len(str(value)))
                sheet.column_dimensions[get_column_letter(col_idx)].width = min(max_length + 2, 60)
            neutralize_formulas(workbook)
            workbook.save(export_path)
        finally:
            workbook.close()

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


def _fuzzy_word_score(query_words: list, name_words: list) -> float:
    """Score how well query words match name words, tolerating typos.

    Each query word finds its best-matching name word using SequenceMatcher.
    Returns average of best matches (0.0-1.0). A score >= 0.75 is a good fuzzy match.

    Examples:
        ["john", "smth"] vs ["john", "smith"]  → ~0.92
        ["jhon", "smith"] vs ["john", "smith"] → ~0.88
        ["xyz", "abc"] vs ["john", "smith"]    → ~0.0
    """
    from difflib import SequenceMatcher
    if not query_words or not name_words:
        return 0.0
    total = 0.0
    for qw in query_words:
        best = max(SequenceMatcher(None, qw, nw).ratio() for nw in name_words)
        total += best
    return total / len(query_words)


def _normalize_career_level(value: Optional[object]) -> str:
    """Career Level as a clean string: 5, 5.0 and "5" all become "5"."""
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return str(value).strip()


def _safe_string(value: Optional[object]) -> str:
    if value is None:
        return ""
    # Strip leading/trailing whitespace and collapse internal multiple spaces
    return " ".join(str(value).split())


def _format_timestamp(value: Optional[str]) -> str:
    """Convert UTC timestamp to local time for display."""
    if not value:
        return ""
    try:
        # Handle 'Z' suffix (UTC indicator) - replace with +00:00 for fromisoformat
        iso_value = value.replace('Z', '+00:00')
        utc_dt = datetime.fromisoformat(iso_value)
        # Convert to local timezone
        local_dt = utc_dt.astimezone()
        return local_dt.strftime(DISPLAY_TIMESTAMP_FORMAT)
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
