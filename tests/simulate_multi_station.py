"""Simulate scan data from multiple stations for dashboard testing.

This script sends simulated scans from multiple stations to the Cloud API
to test the dashboard's ability to display 10+ stations and BU breakdown.

Usage:
    python tests/simulate_multi_station.py --stations 10 --scans-per-station 20
"""

import argparse
import random
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import sqlite3
import requests
import config

STATION_NAMES = [
    "Main Gate",
    "Side Entrance",
    "North Wing",
    "South Wing",
    "Tower A Lobby",
    "Tower B Lobby",
    "Parking Level 1",
    "Parking Level 2",
    "VIP Entrance",
    "Staff Entrance",
    "Basement Access",
    "Rooftop Helipad",
]


def load_employee_badges(db_path: Path, sample_size: int = 50) -> list[dict]:
    """Load employee badge IDs with BU from the SQLite database."""
    if not db_path.exists():
        print(f"[ERROR] Database not found: {db_path}")
        return []

    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.execute(
            "SELECT legacy_id, sl_l1_desc FROM employees WHERE legacy_id IS NOT NULL AND legacy_id != ''"
        )
        employees = [{"badge_id": row[0], "bu": row[1] or None} for row in cursor.fetchall()]

        if len(employees) > sample_size:
            employees = random.sample(employees, sample_size)
        return employees
    finally:
        conn.close()


def send_scans_to_api(station_name: str, employees: list[dict]) -> dict:
    """Send scan events to the Cloud API."""
    events = []
    base_time = datetime.now(timezone.utc)

    for i, emp in enumerate(employees):
        badge_id = emp["badge_id"]
        idempotency_key = f"{station_name.replace(' ', '-')}-{badge_id}-test-{base_time.strftime('%Y%m%d%H%M%S')}-{i}"

        event = {
            "idempotency_key": idempotency_key,
            "badge_id": badge_id,
            "station_name": station_name,
            "scanned_at": base_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "meta": {
                "matched": True,
                "local_id": 999000 + i,
            }
        }
        if emp.get("bu"):
            event["business_unit"] = emp["bu"]
        events.append(event)

    headers = {
        "Authorization": f"Bearer {config.CLOUD_API_KEY}",
        "Content-Type": "application/json; charset=utf-8",
    }

    response = requests.post(
        f"{config.CLOUD_API_URL}/v1/scans/batch",
        headers=headers,
        json={"events": events},
        timeout=30,
    )

    if response.status_code == 200:
        return response.json()
    else:
        return {"error": f"HTTP {response.status_code}: {response.text}"}


def get_dashboard_stats() -> dict:
    """Fetch current dashboard stats (authenticated)."""
    headers = {
        "Authorization": f"Bearer {config.CLOUD_API_KEY}",
        "Content-Type": "application/json",
    }

    response = requests.get(
        f"{config.CLOUD_API_URL}/v1/dashboard/stats",
        headers=headers,
        timeout=15,
    )

    if response.status_code == 200:
        return response.json()
    return {}


def get_public_dashboard_stats() -> dict:
    """Fetch public dashboard stats (no auth — same as mobile dashboard)."""
    response = requests.get(
        f"{config.CLOUD_API_URL}/v1/dashboard/public/stats",
        timeout=15,
    )

    if response.status_code == 200:
        return response.json()
    return {}


def sync_roster_summary() -> dict:
    """Push roster BU counts to cloud so dashboard shows registered totals."""
    db_path = ROOT_DIR / "data" / "database.db"
    if not db_path.exists():
        return {"error": "No database"}

    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.execute(
            "SELECT sl_l1_desc, COUNT(*) FROM employees WHERE sl_l1_desc IS NOT NULL AND sl_l1_desc != '' GROUP BY sl_l1_desc"
        )
        bu_counts = [{"name": row[0], "registered": row[1]} for row in cursor.fetchall()]
    finally:
        conn.close()

    if not bu_counts:
        return {"error": "No BU data"}

    headers = {
        "Authorization": f"Bearer {config.CLOUD_API_KEY}",
        "Content-Type": "application/json",
    }

    response = requests.post(
        f"{config.CLOUD_API_URL}/v1/roster/summary",
        headers=headers,
        json={"business_units": bu_counts},
        timeout=10,
    )

    if response.status_code == 200:
        return response.json()
    return {"error": f"HTTP {response.status_code}: {response.text}"}


def main():
    parser = argparse.ArgumentParser(description="Simulate multi-station scans for dashboard testing")
    parser.add_argument("--stations", type=int, default=10, help="Number of stations to simulate")
    parser.add_argument("--scans-per-station", type=int, default=15, help="Scans per station")
    parser.add_argument("--sample-size", type=int, default=100, help="Number of employee badges to sample (0 = all)")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be sent without sending")
    args = parser.parse_args()

    # Load employee badges from SQLite database
    db_path = ROOT_DIR / "data" / "database.db"
    sample_size = args.sample_size if args.sample_size > 0 else 999999
    employees = load_employee_badges(db_path, sample_size=sample_size)

    if not employees:
        print("[ERROR] No employee badges found in database")
        return 1

    bu_set = {e["bu"] for e in employees if e.get("bu")}
    print(f"Loaded {len(employees)} employees ({len(bu_set)} BUs) from database")

    # Select stations
    stations = STATION_NAMES[:args.stations]
    print(f"Simulating {len(stations)} stations with {args.scans_per_station} scans each")
    print(f"Stations: {', '.join(stations)}")

    if args.dry_run:
        print("\n[DRY RUN] Would send:")
        for station in stations:
            sample = random.sample(employees, min(args.scans_per_station, len(employees)))
            print(f"  {station}: {len(sample)} scans")
        return 0

    # Sync roster summary first (so dashboard has registered counts)
    print("\n[roster] Syncing roster BU counts to cloud...")
    roster_result = sync_roster_summary()
    if "error" in roster_result:
        print(f"  [WARN] Roster sync: {roster_result['error']}")
    else:
        print(f"  [OK] Roster sync: saved={roster_result.get('saved', 0)}, skipped={roster_result.get('skipped', False)}")

    # Send scans for each station
    total_saved = 0
    total_duplicates = 0

    for station in stations:
        sample = random.sample(employees, min(args.scans_per_station, len(employees)))
        print(f"\n[{station}] Sending {len(sample)} scans...")

        result = send_scans_to_api(station, sample)

        if "error" in result:
            print(f"  [ERROR] {result['error']}")
        else:
            saved = result.get("saved", 0)
            duplicates = result.get("duplicates", 0)
            total_saved += saved
            total_duplicates += duplicates
            print(f"  [OK] Saved: {saved}, Duplicates: {duplicates}")

    # Show dashboard stats after upload
    print("\n" + "=" * 60)
    print("AUTHENTICATED DASHBOARD STATS (/v1/dashboard/stats)")
    print("=" * 60)

    stats = get_dashboard_stats()
    print(f"Total scans: {stats.get('total_scans', 0)}")
    print(f"Unique badges: {stats.get('unique_badges', 0)}")
    print(f"\nStations ({len(stats.get('stations', []))}):")
    for s in stats.get("stations", []):
        print(f"  {s.get('name', '--')}: {s.get('scans', 0)} scans, {s.get('unique', 0)} unique")
    if stats.get("business_units"):
        print(f"\nBusiness Units ({len(stats['business_units'])}):")
        for bu in stats["business_units"]:
            name = bu.get("name", "--")
            unique = bu.get("unique", 0)
            registered = bu.get("registered", 0)
            pct = f" ({unique*100/registered:.1f}%)" if registered > 0 else ""
            print(f"  {name}: {unique}/{registered}{pct}")

    # Show PUBLIC dashboard stats (what mobile users see)
    print("\n" + "=" * 60)
    print("PUBLIC DASHBOARD STATS (/v1/dashboard/public/stats)")
    print("=" * 60)

    pub = get_public_dashboard_stats()
    print(f"Total scans: {pub.get('total_scans', 0)}")
    print(f"Unique badges: {pub.get('unique_badges', 0)}")
    print(f"\nStations ({len(pub.get('stations', []))}):")
    for s in pub.get("stations", []):
        print(f"  {s.get('name', '--')}: {s.get('unique', 0)} unique")
    if pub.get("business_units"):
        print(f"\nBusiness Units ({len(pub['business_units'])}):")
        for bu in pub["business_units"]:
            name = bu.get("name", "--")
            unique = bu.get("unique", 0)
            registered = bu.get("registered", 0)
            pct = f" ({unique*100/registered:.1f}%)" if registered > 0 else ""
            print(f"  {name}: {unique}/{registered}{pct}")

    print(f"\n--- Summary ---")
    print(f"Total saved: {total_saved}")
    print(f"Total duplicates: {total_duplicates}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
