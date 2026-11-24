"""Dashboard service for multi-station scan reports (Issue #27).

This module provides centralized reporting by:
- Querying Cloud API for multi-station scan data
- Reading local SQLite for employee count (registered headcount)

The dashboard shows:
- Total registered employees (from local SQLite)
- Total unique badges scanned (from Cloud API - all stations)
- Attendance rate (scanned / registered)
- Per-station breakdown
- Excel export functionality
"""

from __future__ import annotations

import logging
from database import normalize_badge_id, normalize_walkin_name
from excel_safety import neutralize_formulas
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING

import requests

if TYPE_CHECKING:
    from database import DatabaseManager

logger = logging.getLogger(__name__)

# Server caps GET /v1/dashboard/export at this many rows (no pagination).
EXPORT_SERVER_LIMIT = 100000


def classify_export_scan(employee_found: bool, scan_source: Optional[str], cloud_matched: bool = False) -> str:
    """Attendance bucket for one export row: registered, walkin or unknown.

    A scan the cloud matched counts as registered even if this station's roster
    lacks the person, so the export agrees with the dashboard. A missing or empty
    scan_source means "manual", matching the server default and the local query.
    """
    if employee_found or cloud_matched:
        return "registered"
    return "walkin" if (scan_source or "manual") == "manual" else "unknown"


def bucket_export_scans(enriched_scans: List[dict]) -> Dict[str, Any]:
    """Count the three attendance buckets from enriched export rows.

    Registered employees are keyed by normalised legacy_id (a badge scan and a
    lookup of the same person are one person); walk-ins by normalised typed
    name (earliest scan kept); unknown badges by normalised badge value.
    """
    registered: set = set()
    walkins: Dict[str, dict] = {}
    unknown: set = set()
    for row in enriched_scans:
        kind = row["_kind"]
        if kind == "registered":
            registered.add(normalize_badge_id(row["Legacy ID"]))
        elif kind == "walkin":
            key = normalize_walkin_name(row["Scan Value"])
            current = walkins.get(key)
            if current is None or row["_ScannedAtDt"] < current["_ScannedAtDt"]:
                walkins[key] = row
        else:
            unknown.add(normalize_badge_id(row["Scan Value"]))
    return {"registered": registered, "walkins": walkins, "unknown": unknown}


def compute_bu_breakdown(enriched_scans: List[dict], employee_cache: Dict[str, Any]) -> List[dict]:
    """Per-BU attended counts for the export. Employees count once by
    normalised legacy_id; walk-ins are excluded (own sheet); unknown badges
    form the trailing "(Unmatched)" row."""
    from collections import defaultdict
    bu_scanned = defaultdict(set)
    unknown = set()
    for row in enriched_scans:
        kind = row.get("_kind")
        if kind == "registered":
            bu = row["SL L1 Desc"]
            bu_key = bu if bu and bu != "--" else "(No BU)"
            bu_scanned[bu_key].add(normalize_badge_id(row["Legacy ID"]))
        elif kind == "unknown":
            unknown.add(normalize_badge_id(row["Scan Value"]))

    bu_registered = defaultdict(int)
    for emp in employee_cache.values():
        bu_registered[emp.sl_l1_desc or "(No BU)"] += 1

    bu_export = []
    for bu_name in sorted(set(bu_scanned) | set(bu_registered)):
        registered = bu_registered.get(bu_name, 0)
        scanned = len(bu_scanned.get(bu_name, set()))
        rate = round((scanned / registered) * 100, 1) if registered > 0 else 0.0
        bu_export.append({"bu_name": bu_name, "registered": registered,
                          "scanned": scanned, "attendance_rate": rate})
    if unknown:
        bu_export.append({"bu_name": "(Unmatched)", "registered": 0,
                          "scanned": len(unknown), "attendance_rate": 0.0})
    return bu_export


# Career Levels not eligible for the lucky draw: 9 = Partner, 0 = Intern.
LUCKY_DRAW_EXCLUDED_LEVELS = frozenset({"9", "0"})


class DashboardService:
    """Service for fetching multi-station dashboard data via Cloud API."""

    def __init__(
        self,
        db_manager: "DatabaseManager",
        api_url: str,
        api_key: str,
        export_directory: Optional[Path] = None,
        run_network_call: Optional[Callable[[Callable[[], Any]], Any]] = None,
    ) -> None:
        """Initialize the dashboard service.

        Args:
            db_manager: Local SQLite database manager (for employee count)
            api_url: Cloud API base URL
            api_key: Cloud API authentication key
            export_directory: Directory where Excel exports will be saved
            run_network_call: Wraps each blocking HTTP call (e.g.
                qt_bridge.call_without_freezing_ui, injected by main.py) so it
                can run off the Qt main thread without freezing the UI.
                Defaults to a plain synchronous call — this module has no
                PyQt6 dependency and must stay that way (see
                tests/test_dashboard.py, which imports/tests it without
                PyQt6 installed). Only the network calls are wrapped, never
                the SQLite reads around them — SQLite connections are
                thread-affine, so those must stay on the calling thread.
        """
        self._db_manager = db_manager
        self._api_url = api_url.rstrip("/")
        self._api_key = api_key
        self._export_directory = export_directory or Path.cwd() / "exports"
        self._timeout = 15  # seconds
        self._employee_cache = None
        self._employee_cache_loaded = False
        self._run_network_call = run_network_call or (lambda fn: fn())

    def _get_employee_cache(self):
        """Get employee cache, loading once per session."""
        if not self._employee_cache_loaded:
            self._employee_cache = self._db_manager.load_employee_cache()
            self._employee_cache_loaded = True
            logger.debug(f"Dashboard: Loaded {len(self._employee_cache)} employees (cached)")
        return self._employee_cache

    def _get_headers(self) -> Dict[str, str]:
        """Get HTTP headers for API requests."""
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    def get_local_snapshot(self) -> Dict[str, Any]:
        """Local-only, instant subset of dashboard data — no network call.

        Used to populate the dashboard the moment it opens (registered
        employee count is a single indexed SQLite query, effectively
        instant) while get_dashboard_data() fetches the cloud-sourced
        fields (scanned count, stations, BU breakdown) in the background.
        Avoids making the user wait on a cloud round-trip just to see a
        number that was already sitting in the local database.
        """
        result = {
            "registered": 0,
            "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "error": None,
        }
        try:
            result["registered"] = self._db_manager.count_employees()
        except Exception as e:
            logger.error(f"Dashboard: Failed to get employee count (local snapshot): {e}")
            result["error"] = f"Failed to get employee count: {e}"
        return result

    def get_dashboard_data(self) -> Dict[str, Any]:
        """Fetch all dashboard data.

        Returns:
            Dictionary containing:
            - registered: int (employee count from local SQLite)
            - scanned: int (registered employees attended, the rate numerator)
            - walkins: int | None (typed names of people not in the roster)
            - unknown_badges: int | None (unmatched badge scans, need review)
            - total_present: int (scanned + walkins)
            - total_scans: int (total scans from cloud)
            - attendance_rate: float (percentage)
            - stations: list of station data
            - business_units: list of BU data with registered, scanned, and percentage
            - last_updated: str (ISO timestamp)
            - error: str (if any error occurred)
        """
        result = {
            "registered": 0,
            "scanned": 0,
            "walkins": None,
            "unknown_badges": None,
            "total_present": 0,
            "total_scans": 0,
            "attendance_rate": 0.0,
            "stations": [],
            "business_units": [],
            "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "error": None,
        }

        # Get registered employee count from local SQLite
        try:
            result["registered"] = self._db_manager.count_employees()
            logger.debug(f"Dashboard: Local employee count = {result['registered']}")
        except Exception as e:
            logger.error(f"Dashboard: Failed to get employee count: {e}")
            result["error"] = f"Failed to get employee count: {e}"

        # Get cloud scan data from API
        cloud_bus = []  # BU data from cloud (all stations combined)
        stats_ok = False
        try:
            response = self._run_network_call(lambda: requests.get(
                f"{self._api_url}/v1/dashboard/stats",
                headers=self._get_headers(),
                timeout=self._timeout,
            ))

            if response.status_code == 200:
                data = response.json()
                result["total_scans"] = data.get("total_scans", 0)
                cloud_bus = data.get("business_units", [])
                if "matched_unique" in data:
                    result["scanned"] = int(data.get("matched_unique") or 0)
                    result["walkins"] = int(data.get("walkin_unique") or 0)
                    result["unknown_badges"] = int(data.get("unknown_badge_unique") or 0)
                else:
                    # Old server: no bucket fields. unique_badges includes
                    # unmatched badges, so sum the matched BUs instead.
                    result["scanned"] = sum(
                        int(bu.get("unique", 0) or 0) for bu in cloud_bus
                        if str(bu.get("name", "")).strip("() ").lower() != "unmatched"
                    )
                stats_ok = True
                result["stations"] = sorted([
                    {
                        "name": s.get("name", "--"),
                        "scans": s.get("scans", 0),
                        "unique": s.get("unique", 0),
                        "last_scan": self._format_time(s.get("last_scan")),
                    }
                    for s in data.get("stations", [])
                ], key=lambda s: s["name"])
                logger.info(
                    f"Dashboard: total_scans={result['total_scans']}, "
                    f"unique_badges={result['scanned']}, stations={len(result['stations'])}"
                )
            elif response.status_code == 401:
                result["error"] = "Authentication failed - check API key"
                logger.error("Dashboard: API authentication failed")
            elif response.status_code == 503:
                result["error"] = "Cloud database unavailable"
                logger.error("Dashboard: Cloud database unavailable")
            else:
                result["error"] = f"API error: {response.status_code}"
                logger.error(f"Dashboard: API returned {response.status_code}")

        except requests.exceptions.ConnectionError:
            result["error"] = "Cannot connect to cloud API"
            logger.error("Dashboard: Connection error")
        except requests.exceptions.Timeout:
            result["error"] = "Cloud API timeout"
            logger.error("Dashboard: Request timeout")
        except Exception as e:
            result["error"] = f"API error: {e}"
            logger.error(f"Dashboard: Unexpected error: {e}")

        result["source"] = "cloud" if stats_ok else "none"
        if not stats_ok:
            # Cloud unavailable: same three buckets from this station's SQLite.
            # Marked "local" so the UI says these cover this station only.
            try:
                local = self._db_manager.get_attendance_buckets()
                result["scanned"] = local["registered_attended"]
                result["walkins"] = local["walkins"]
                result["unknown_badges"] = local["unknown_badges"]
                result["source"] = "local"
            except Exception as e:
                logger.error(f"Dashboard: Failed to compute local attendance buckets: {e}")

        result["total_present"] = result["scanned"] + (result["walkins"] or 0)

        # Attendance rate = registered attended / registered, never above 100%
        if result["registered"] > 0:
            rate = round((result["scanned"] / result["registered"]) * 100, 1)
            if rate > 100:
                logger.warning(
                    "Dashboard: attended (%d) exceeds registered (%d); capping rate at 100%% "
                    "(cloud roster summary may be stale)",
                    result["scanned"], result["registered"],
                )
                rate = 100.0
            result["attendance_rate"] = rate

        # Get BU breakdown from cloud API (aggregates all stations)
        # Falls back to local SQLite if cloud data unavailable
        if cloud_bus:
            bu_list = []
            for bu in cloud_bus:
                registered = bu.get("registered", 0)
                scanned = bu.get("unique", 0)
                name = bu.get("name", "--")
                rate = round((scanned / registered) * 100, 1) if registered > 0 else 0.0
                bu_list.append({
                    "bu_name": name,
                    "registered": registered,
                    "scanned": scanned,
                    "attendance_rate": rate,
                })
            result["business_units"] = bu_list
            logger.info(f"Dashboard: BU breakdown from cloud API for {len(bu_list)} BUs")
        else:
            # Fallback: local SQLite (only this station's scans)
            try:
                bu_data = self._db_manager.get_scans_by_bu()
                bu_list = []
                for bu in bu_data:
                    registered = bu["registered"]
                    scanned = bu["scanned"]
                    rate = round((scanned / registered) * 100, 1) if registered > 0 else 0.0
                    bu_list.append({
                        "bu_name": bu["bu_name"],
                        "registered": registered,
                        "scanned": scanned,
                        "attendance_rate": rate,
                    })

                unmatched_count = self._db_manager.count_unmatched_scanned_badges()
                if unmatched_count > 0:
                    bu_list.append({
                        "bu_name": "(Unmatched)",
                        "registered": 0,
                        "scanned": unmatched_count,
                        "attendance_rate": 0.0,
                    })

                result["business_units"] = bu_list
                logger.info(f"Dashboard: BU breakdown from local DB for {len(bu_list)} BUs (cloud unavailable)")
            except Exception as e:
                logger.error(f"Dashboard: Failed to calculate BU breakdown: {e}")
                result["business_units"] = []

        return result

    def _format_time(self, iso_timestamp: Optional[str]) -> str:
        """Format ISO timestamp to time-only string."""
        if not iso_timestamp:
            return "--"
        try:
            dt = datetime.fromisoformat(iso_timestamp.replace("Z", "+00:00"))
            local_dt = dt.astimezone()  # Convert UTC to local machine timezone
            return local_dt.strftime("%H:%M:%S")
        except Exception:
            return "--"

    def _format_datetime(self, iso_timestamp: Optional[str]) -> str:
        """Format ISO timestamp to local date+time string for Excel export."""
        if not iso_timestamp:
            return "--"
        try:
            dt = datetime.fromisoformat(iso_timestamp.replace("Z", "+00:00"))
            local_dt = dt.astimezone()  # Convert UTC to local machine timezone
            return local_dt.strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            return iso_timestamp  # Return raw value as fallback

    @staticmethod
    def _write_simple_sheet(wb, title, headers, rows, total_label, header_fill, header_font) -> None:
        """Header + data rows + a bold total line, auto-width, frozen header."""
        from openpyxl.styles import Font, Alignment

        ws = wb.create_sheet(title)
        for col_idx, name in enumerate(headers, start=1):
            cell = ws.cell(row=1, column=col_idx, value=name)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal="center")
        for row_idx, values in enumerate(rows, start=2):
            for col_idx, value in enumerate(values, start=1):
                ws.cell(row=row_idx, column=col_idx, value=value)
        total_row = len(rows) + 2
        ws.cell(row=total_row, column=1, value=total_label).font = Font(bold=True)
        ws.cell(row=total_row, column=2, value=len(rows)).font = Font(bold=True)
        for col in ws.columns:
            max_length = max(len(str(cell.value or "")) for cell in col)
            ws.column_dimensions[col[0].column_letter].width = max_length + 2
        ws.freeze_panes = "A2"

    def _parse_datetime_for_sort(self, formatted_datetime: str) -> datetime:
        """Parse a `_format_datetime()`-produced string back into a sortable
        datetime, for ranking a person's multiple scans by earliest-first.
        Unparseable/placeholder values ("--", raw-ISO fallback) sort first
        (datetime.min) rather than raising or silently misordering."""
        try:
            return datetime.strptime(formatted_datetime, "%Y-%m-%d %H:%M:%S")
        except (ValueError, TypeError):
            return datetime.min

    def export_to_excel(self, dashboard_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Export dashboard data to Excel file.

        Args:
            dashboard_data: Pre-fetched dashboard data to avoid redundant API calls.
                            If None, will fetch fresh data.

        Returns:
            Dictionary with:
            - ok: bool (success status)
            - message: str (success/error message)
            - file_path: str (absolute path to created file)
            - fileName: str (just the filename)
        """
        # Build export path with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"Dashboard_Report_{timestamp}.xlsx"
        file_path = self._export_directory / filename

        # Ensure export directory exists
        self._export_directory.mkdir(parents=True, exist_ok=True)

        result = {
            "ok": False,
            "message": "",
            "file_path": str(file_path),
            "fileName": filename,
        }

        # Fetch export data from API
        try:
            response = self._run_network_call(lambda: requests.get(
                f"{self._api_url}/v1/dashboard/export",
                headers=self._get_headers(),
                timeout=60,  # Longer timeout for export
            ))

            if response.status_code != 200:
                result["message"] = f"API error: {response.status_code}"
                return result

            data = response.json()
            scans = data.get("scans", [])

            total_records = data.get("total_records", len(scans))
            if max(total_records, len(scans)) >= EXPORT_SERVER_LIMIT:
                logger.warning(
                    "Export returned %d records, at the server limit of %d; "
                    "the export may be truncated",
                    max(total_records, len(scans)), EXPORT_SERVER_LIMIT,
                )

            if not scans:
                result["message"] = "No scan data to export"
                result["noData"] = True
                return result

        except requests.exceptions.ConnectionError:
            result["message"] = "Cannot connect to cloud API"
            return result
        except requests.exceptions.Timeout:
            result["message"] = "Cloud API timeout"
            return result
        except Exception as e:
            result["message"] = f"API error: {e}"
            return result

        # Generate Excel file
        try:
            import pandas as pd
            from openpyxl import Workbook
            from openpyxl.styles import Font, PatternFill, Alignment

            # Load employee cache for enriching scan data with employee details
            employee_cache = self._get_employee_cache()
            logger.debug(f"Dashboard export: Loaded {len(employee_cache)} employees for enrichment")

            # Enrich scans with employee details from local database
            enriched_scans = []
            for scan in scans:
                # Handle both dict and list formats from API
                if isinstance(scan, dict):
                    badge_id = scan.get("badge_id", "")
                    station = scan.get("station_name", "")
                    scanned_at = scan.get("scanned_at", "")
                    matched = scan.get("matched", False)
                else:
                    badge_id, station, scanned_at, matched = scan[0], scan[1], scan[2], scan[3]

                # Use legacy_id from cloud meta if available, otherwise try badge_id
                legacy_id = scan.get("legacy_id") if isinstance(scan, dict) else None
                lookup_key = legacy_id or badge_id
                employee = employee_cache.get(normalize_badge_id(lookup_key))
                if employee:
                    full_name = employee.full_name
                    business_unit = employee.sl_l1_desc or "--"
                    position = employee.position_desc or "--"
                    career_level = employee.career_level or "--"
                else:
                    full_name = "Unknown"
                    business_unit = "--"
                    position = "--"
                    career_level = "--"

                scan_source = (scan.get("scan_source") if isinstance(scan, dict) else None) or "manual"
                enriched_scans.append({
                    "_kind": classify_export_scan(employee is not None, scan_source, bool(matched)),
                    "Scan Value": badge_id,
                    "Legacy ID": employee.legacy_id if employee else (legacy_id or ""),
                    "Full Name": full_name,
                    "SL L1 Desc": business_unit,
                    "Position Desc": position,
                    "Career Level": career_level,
                    "Email": employee.email if employee else "",
                    "Station": station,
                    "Scanned At": self._format_datetime(scanned_at),
                    "Matched": "Yes" if matched else "No",
                    "Scan Source": scan_source,
                })

            for row in enriched_scans:
                row["_ScannedAtDt"] = self._parse_datetime_for_sort(row["Scanned At"])

            columns = ["Scan Value", "Legacy ID", "Full Name", "SL L1 Desc", "Position Desc", "Career Level", "Email", "Station", "Scanned At", "Matched", "Scan Source"]
            df = pd.DataFrame(enriched_scans)[columns] if enriched_scans else pd.DataFrame(columns=columns)
            buckets = bucket_export_scans(enriched_scans)

            # Create Excel workbook
            wb = Workbook()
            ws = wb.active
            ws.title = "All Scans"

            # Add header with styling
            header_fill = PatternFill(start_color="86bc25", end_color="86bc25", fill_type="solid")
            header_font = Font(bold=True, color="FFFFFF")

            for col_idx, col_name in enumerate(columns, start=1):
                cell = ws.cell(row=1, column=col_idx, value=col_name)
                cell.fill = header_fill
                cell.font = header_font
                cell.alignment = Alignment(horizontal="center")

            # Add data rows
            for row_idx, row in enumerate(df.values, start=2):
                for col_idx, value in enumerate(row, start=1):
                    ws.cell(row=row_idx, column=col_idx, value=value)

            # Auto-adjust column widths
            for col in ws.columns:
                max_length = 0
                column = col[0].column_letter
                for cell in col:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except Exception:
                        pass
                ws.column_dimensions[column].width = max_length + 2

            # Add summary sheet
            ws_summary = wb.create_sheet("Summary")
            if dashboard_data is None:
                dashboard_data = self.get_dashboard_data()

            ws_summary["A1"] = "Metric"
            ws_summary["B1"] = "Value"
            ws_summary["A1"].font = header_font
            ws_summary["A1"].fill = header_fill
            ws_summary["B1"].font = header_font
            ws_summary["B1"].fill = header_fill

            # Buckets come from the export rows themselves so Summary, By
            # Business Unit, Deduplicated and Walk-ins always agree.
            attended = len(buckets["registered"])
            walkin_count = len(buckets["walkins"])
            registered_total = dashboard_data["registered"]
            export_rate = (
                min(round(attended / registered_total * 100, 1), 100.0)
                if registered_total > 0 else 0.0
            )
            summary_data = [
                ("Registered Employees", registered_total),
                ("Registered Attended", attended),
                ("Walk-ins", walkin_count),
                ("Unknown Badge Scans (needs review)", len(buckets["unknown"])),
                ("Total Present", attended + walkin_count),
                ("Total Scans", dashboard_data["total_scans"]),
                ("Attendance Rate", f"{export_rate}%"),
                ("Report Generated", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            ]

            for row_idx, (label, value) in enumerate(summary_data, start=2):
                ws_summary.cell(row=row_idx, column=1, value=label)
                ws_summary.cell(row=row_idx, column=2, value=value)

            ws_summary.column_dimensions["A"].width = 36
            ws_summary.column_dimensions["B"].width = 20

            # Add station breakdown sheet
            if dashboard_data["stations"]:
                ws_stations = wb.create_sheet("By Station")
                station_headers = ["Station", "Total Scans", "Unique Badges", "Last Scan"]

                for col_idx, col_name in enumerate(station_headers, start=1):
                    cell = ws_stations.cell(row=1, column=col_idx, value=col_name)
                    cell.fill = header_fill
                    cell.font = header_font

                for row_idx, station in enumerate(dashboard_data["stations"], start=2):
                    ws_stations.cell(row=row_idx, column=1, value=station["name"])
                    ws_stations.cell(row=row_idx, column=2, value=station["scans"])
                    ws_stations.cell(row=row_idx, column=3, value=station["unique"])
                    ws_stations.cell(row=row_idx, column=4, value=station["last_scan"])

                for col in ws_stations.columns:
                    max_length = max(len(str(cell.value or "")) for cell in col)
                    ws_stations.column_dimensions[col[0].column_letter].width = max_length + 2

            # Add BU breakdown sheet - computed from enriched scan data
            # (fixes #52) and counted by normalised legacy_id (#109).
            bu_export = compute_bu_breakdown(enriched_scans, employee_cache)

            if bu_export:
                ws_bu = wb.create_sheet("By Business Unit")
                bu_headers = ["Business Unit", "Registered", "Scanned", "Attendance %"]

                for col_idx, col_name in enumerate(bu_headers, start=1):
                    cell = ws_bu.cell(row=1, column=col_idx, value=col_name)
                    cell.fill = header_fill
                    cell.font = header_font

                for row_idx, bu in enumerate(bu_export, start=2):
                    ws_bu.cell(row=row_idx, column=1, value=bu["bu_name"])
                    ws_bu.cell(row=row_idx, column=2, value=bu["registered"])
                    ws_bu.cell(row=row_idx, column=3, value=bu["scanned"])
                    ws_bu.cell(row=row_idx, column=4, value=f"{bu['attendance_rate']}%")

                for col in ws_bu.columns:
                    max_length = max(len(str(cell.value or "")) for cell in col)
                    ws_bu.column_dimensions[col[0].column_letter].width = max_length + 2

            # Add "Not Yet Scanned" sheet - employees who haven't scanned.
            # Must key off each scan's resolved legacy_id (falling back to
            # badge_id only when legacy_id is absent, matching the enrichment
            # lookup above) rather than badge_id alone -- a manual-lookup or
            # reprinted-badge scan can have badge_id != the employee's actual
            # legacy_id, which previously caused employees who HAD scanned to
            # still show up here as "not yet scanned".
            # Only registered-employee scans count: walk-ins and unknown
            # badges are not roster members, and ids compare normalised.
            not_scanned = [
                emp for emp in employee_cache.values()
                if normalize_badge_id(emp.legacy_id) not in buckets["registered"]
            ]
            not_scanned.sort(key=lambda e: (e.sl_l1_desc or "", e.full_name or ""))

            ws_missing = wb.create_sheet("Not Yet Scanned")
            missing_headers = ["Legacy ID", "Full Name", "Email", "SL L1 Desc", "Position Desc", "Career Level"]
            for col_idx, col_name in enumerate(missing_headers, start=1):
                cell = ws_missing.cell(row=1, column=col_idx, value=col_name)
                cell.fill = header_fill
                cell.font = header_font
                cell.alignment = Alignment(horizontal="center")

            for row_idx, emp in enumerate(not_scanned, start=2):
                ws_missing.cell(row=row_idx, column=1, value=emp.legacy_id)
                ws_missing.cell(row=row_idx, column=2, value=emp.full_name)
                ws_missing.cell(row=row_idx, column=3, value=emp.email or "--")
                ws_missing.cell(row=row_idx, column=4, value=emp.sl_l1_desc or "--")
                ws_missing.cell(row=row_idx, column=5, value=emp.position_desc or "--")
                ws_missing.cell(row=row_idx, column=6, value=emp.career_level or "--")

            # Summary row
            summary_row = len(not_scanned) + 2
            ws_missing.cell(row=summary_row, column=1, value="Total Not Scanned:")
            ws_missing.cell(row=summary_row, column=1).font = Font(bold=True)
            ws_missing.cell(row=summary_row, column=2, value=len(not_scanned))
            ws_missing.cell(row=summary_row, column=2).font = Font(bold=True)

            for col in ws_missing.columns:
                max_length = max(len(str(cell.value or "")) for cell in col)
                ws_missing.column_dimensions[col[0].column_letter].width = max_length + 2

            logger.info(f"Dashboard export: {len(not_scanned)} employees not yet scanned")

            # Registered employees only (garbled/unrecognised badges and walk-ins
            # are not attendees). Same employee-matched data "Not Yet Scanned"
            # above is complementary to, so the sheets can never drift apart on
            # what counts as "scanned". The old "Deduplicated Attendance" sheet
            # was replaced by the "Unique Scans (Per Day)" and "Lucky Draw"
            # sheets below.
            matched_scans = [row for row in enriched_scans if row["_kind"] == "registered"]

            # One row per employee (normalised legacy_id): their earliest scan
            # across all stations.
            first_by_legacy_id: Dict[str, dict] = {}
            for row in sorted(matched_scans, key=lambda r: r["_ScannedAtDt"]):
                first_by_legacy_id.setdefault(normalize_badge_id(row["Legacy ID"]), row)
            dedup_rows = sorted(
                (
                    {
                        "Legacy ID": first["Legacy ID"],
                        "Full Name": first["Full Name"],
                        "SL L1 Desc": first["SL L1 Desc"],
                        "Position Desc": first["Position Desc"],
                        "Career Level": first["Career Level"],
                        "First Station": first["Station"],
                        "First Scanned At": first["Scanned At"],
                    }
                    for first in first_by_legacy_id.values()
                ),
                key=lambda r: r["Full Name"] or "",
            )

            # "Unique Scans (Per Day)": one row per employee per calendar day,
            # keeping that day's first scan. Raw duplicates stay in "All Scans".
            per_day: Dict[tuple, dict] = {}
            for row in sorted(matched_scans, key=lambda r: r["_ScannedAtDt"]):
                day = row["Scanned At"][:10] if row["_ScannedAtDt"] != datetime.min else "--"
                per_day.setdefault((normalize_badge_id(row["Legacy ID"]), day), row)
            per_day_rows = sorted(
                per_day.items(), key=lambda kv: (kv[0][1], kv[1]["Full Name"] or "")
            )
            self._write_simple_sheet(
                wb, "Unique Scans (Per Day)",
                ["Date", "Legacy ID", "Full Name", "SL L1 Desc", "Position Desc",
                 "Career Level", "Email", "Station", "First Scanned At", "Scan Source"],
                [[day, r["Legacy ID"], r["Full Name"], r["SL L1 Desc"], r["Position Desc"],
                  r["Career Level"], r["Email"], r["Station"], r["Scanned At"], r["Scan Source"]]
                 for (_lid, day), r in per_day_rows],
                "Unique Employee-Days:", header_fill, header_font,
            )

            # "Lucky Draw": one row per rostered employee who attended (first
            # scan overall), no Email. Partners (level 9) and interns (level 0)
            # are not eligible.
            draw_rows = [
                r for r in dedup_rows
                if r["Full Name"] != "Unknown"
                and str(r["Career Level"]).strip() not in LUCKY_DRAW_EXCLUDED_LEVELS
            ]
            self._write_simple_sheet(
                wb, "Lucky Draw",
                ["Legacy ID", "Full Name", "SL L1 Desc", "Position Desc", "Career Level",
                 "First Station", "First Scanned At"],
                [[r["Legacy ID"], r["Full Name"], r["SL L1 Desc"], r["Position Desc"],
                  r["Career Level"], r["First Station"], r["First Scanned At"]]
                 for r in draw_rows],
                "Eligible Names:", header_fill, header_font,
            )
            logger.info(
                f"Dashboard export: {len(per_day_rows)} unique employee-days, "
                f"{len(draw_rows)} lucky draw eligible"
            )

            # Walk-ins: typed names of people missing from the roster, one row
            # per distinct name. Never part of "Not Yet Scanned" or the rate.
            ws_walkins = wb.create_sheet("Walk-ins")
            walkin_headers = ["Name (as typed)", "Station", "First Scanned At"]
            for col_idx, col_name in enumerate(walkin_headers, start=1):
                cell = ws_walkins.cell(row=1, column=col_idx, value=col_name)
                cell.fill = header_fill
                cell.font = header_font
                cell.alignment = Alignment(horizontal="center")
            walkin_rows = sorted(buckets["walkins"].values(), key=lambda r: r["_ScannedAtDt"])
            for row_idx, row in enumerate(walkin_rows, start=2):
                ws_walkins.cell(row=row_idx, column=1, value=row["Scan Value"])
                ws_walkins.cell(row=row_idx, column=2, value=row["Station"])
                ws_walkins.cell(row=row_idx, column=3, value=row["Scanned At"])
            for col in ws_walkins.columns:
                max_length = max(len(str(cell.value or "")) for cell in col)
                ws_walkins.column_dimensions[col[0].column_letter].width = max_length + 2

            # Save file
            neutralize_formulas(wb)
            wb.save(file_path)
            result["ok"] = True
            result["message"] = f"Exported {len(df)} scans to Excel"
            logger.info(f"Dashboard: Exported to {file_path}")

        except ImportError as e:
            result["message"] = f"Missing dependency: {e}. Run: pip install pandas openpyxl"
            logger.error(result["message"])
        except Exception as e:
            result["message"] = f"Export failed: {e}"
            logger.error(f"Dashboard export error: {e}")

        return result


__all__ = ["DashboardService"]
