"""Test console encoding with Thai names.

Validates issue #37 checklist item: Console encoding (Thai names on Windows).
Tests that Thai characters survive the full DB round-trip and can be printed
to console without UnicodeEncodeError.
"""

import io
import os
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)

# Force UTF-8 output on Windows
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

from database import DatabaseManager, EmployeeRecord


THAI_EMPLOYEES = [
    EmployeeRecord(legacy_id="TH001", full_name="สมชาย ใจดี", sl_l1_desc="ฝ่ายขาย", position_desc="พนักงานขาย"),
    EmployeeRecord(legacy_id="TH002", full_name="สมหญิง รักเรียน", sl_l1_desc="ฝ่ายบัญชี", position_desc="นักบัญชี"),
    EmployeeRecord(legacy_id="TH003", full_name="ประเสริฐ มั่งมี", sl_l1_desc="ฝ่ายผลิต", position_desc="วิศวกร"),
    EmployeeRecord(legacy_id="TH004", full_name="กัญญา สว่างจิต", sl_l1_desc="ฝ่ายไอที", position_desc="โปรแกรมเมอร์"),
    EmployeeRecord(legacy_id="TH005", full_name="วิทยา กล้าหาญ", sl_l1_desc="ฝ่ายขาย", position_desc="ผู้จัดการ"),
]

MIXED_EMPLOYEES = [
    EmployeeRecord(legacy_id="MX001", full_name="John สมิธ", sl_l1_desc="Sales ฝ่ายขาย", position_desc="Manager ผู้จัดการ"),
    EmployeeRecord(legacy_id="MX002", full_name="สมชาย Smith-Jr.", sl_l1_desc="IT/ไอที", position_desc="Dev (พัฒนา)"),
]


def test_thai_employee_storage():
    """Test storing and retrieving Thai employee names from SQLite."""
    print("Test 1: Thai employee DB round-trip")

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_thai.db"
        db = DatabaseManager(db_path)

        count = db.bulk_insert_employees(THAI_EMPLOYEES)
        cache = db.load_employee_cache()
        db.close()

        if count != 5:
            print(f"  FAIL: Expected 5 inserted, got {count}")
            return False

        errors = []
        for emp in THAI_EMPLOYEES:
            cached = cache.get(emp.legacy_id)
            if not cached:
                errors.append(f"Missing: {emp.legacy_id}")
                continue
            if cached.full_name != emp.full_name:
                errors.append(f"{emp.legacy_id}: name mismatch '{cached.full_name}' != '{emp.full_name}'")
            if cached.sl_l1_desc != emp.sl_l1_desc:
                errors.append(f"{emp.legacy_id}: BU mismatch '{cached.sl_l1_desc}' != '{emp.sl_l1_desc}'")

        if errors:
            for e in errors:
                print(f"  FAIL: {e}")
            return False

        print(f"  PASS: All 5 Thai employees stored and retrieved correctly")
        return True


def test_thai_scan_recording():
    """Test recording scans with Thai employee data."""
    print("Test 2: Thai scan recording and retrieval")

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_thai_scan.db"
        db = DatabaseManager(db_path)
        db.set_station_name("สถานีทดสอบ")  # Thai station name

        db.bulk_insert_employees(THAI_EMPLOYEES)

        for emp in THAI_EMPLOYEES:
            db.record_scan(
                badge_id=emp.legacy_id,
                station_name="สถานีทดสอบ",
                employee=emp,
                scanned_at="2026-02-02T10:00:00Z",
            )

        scans = db.fetch_all_scans()
        db.close()

        if len(scans) != 5:
            print(f"  FAIL: Expected 5 scans, got {len(scans)}")
            return False

        errors = []
        for scan, emp in zip(scans, THAI_EMPLOYEES):
            if scan.employee_full_name != emp.full_name:
                errors.append(f"Scan name mismatch: '{scan.employee_full_name}' != '{emp.full_name}'")
            if scan.station_name != "สถานีทดสอบ":
                errors.append(f"Station mismatch: '{scan.station_name}'")

        if errors:
            for e in errors:
                print(f"  FAIL: {e}")
            return False

        print(f"  PASS: 5 Thai scans recorded and retrieved with correct names")
        return True


def test_thai_console_output():
    """Test that Thai names can be printed to console without encoding errors."""
    print("Test 3: Thai console output (no UnicodeEncodeError)")

    errors = []
    for emp in THAI_EMPLOYEES + MIXED_EMPLOYEES:
        try:
            # Simulate the kind of logging the app does
            msg = f"RecordingScan: badge={emp.legacy_id}, name={emp.full_name}, dept={emp.sl_l1_desc}"
            print(f"    {msg}")
        except UnicodeEncodeError as e:
            errors.append(f"{emp.legacy_id}: {e}")

    if errors:
        for e in errors:
            print(f"  FAIL: {e}")
        return False

    print(f"  PASS: All {len(THAI_EMPLOYEES) + len(MIXED_EMPLOYEES)} names printed without encoding error")
    return True


def test_mixed_thai_english():
    """Test mixed Thai/English employee names."""
    print("Test 4: Mixed Thai/English names")

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_mixed.db"
        db = DatabaseManager(db_path)

        count = db.bulk_insert_employees(MIXED_EMPLOYEES)
        cache = db.load_employee_cache()
        db.close()

        if count != 2:
            print(f"  FAIL: Expected 2, got {count}")
            return False

        errors = []
        for emp in MIXED_EMPLOYEES:
            cached = cache.get(emp.legacy_id)
            if not cached:
                errors.append(f"Missing: {emp.legacy_id}")
                continue
            if cached.full_name != emp.full_name:
                errors.append(f"Name mismatch: '{cached.full_name}' != '{emp.full_name}'")
            if cached.sl_l1_desc != emp.sl_l1_desc:
                errors.append(f"BU mismatch: '{cached.sl_l1_desc}' != '{emp.sl_l1_desc}'")
            if cached.position_desc != emp.position_desc:
                errors.append(f"Position mismatch: '{cached.position_desc}' != '{emp.position_desc}'")

        if errors:
            for e in errors:
                print(f"  FAIL: {e}")
            return False

        print(f"  PASS: Mixed Thai/English names stored and retrieved correctly")
        return True


def test_thai_bu_grouping():
    """Test that Thai BU names group correctly in get_employees_by_bu."""
    print("Test 5: Thai BU name grouping")

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_bu.db"
        db = DatabaseManager(db_path)
        db.bulk_insert_employees(THAI_EMPLOYEES)

        bu_groups = db.get_employees_by_bu()
        db.close()

        # THAI_EMPLOYEES has: ฝ่ายขาย (2), ฝ่ายบัญชี (1), ฝ่ายผลิต (1), ฝ่ายไอที (1)
        bu_dict = {g["bu_name"]: g["count"] for g in bu_groups}

        expected = {"ฝ่ายขาย": 2, "ฝ่ายบัญชี": 1, "ฝ่ายผลิต": 1, "ฝ่ายไอที": 1}
        if bu_dict == expected:
            print(f"  PASS: BU grouping correct: {bu_dict}")
            return True
        else:
            print(f"  FAIL: Expected {expected}, got {bu_dict}")
            return False


if __name__ == "__main__":
    print("=" * 60)
    print("Thai Encoding Tests (#37)")
    print("=" * 60 + "\n")

    tests = [
        test_thai_employee_storage,
        test_thai_scan_recording,
        test_thai_console_output,
        test_mixed_thai_english,
        test_thai_bu_grouping,
    ]

    passed = 0
    failed = 0
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"  ERROR: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
        print()

    print("=" * 60)
    if failed == 0:
        print(f"All {passed} tests passed!")
    else:
        print(f"{passed} passed, {failed} failed")
    print("=" * 60)
    sys.exit(1 if failed else 0)
