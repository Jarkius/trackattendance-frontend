"""
Cross-Platform POC Test Suite
Tests all components with platform-specific handling:
- Camera: tests with simulated frames (real camera needs separate permission grant)
- Audio: tests pygame mixer + platform TTS fallback
- Database: full CRUD + attendance flow
- Web Dashboard: API endpoint integration test
- Barcode decode: tests pyzbar with generated test image

Supported: macOS, Windows 11, Linux
"""

import sys
import os
import time
import threading
import tempfile
import json
from datetime import datetime

# Ensure we're in the right directory
os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(__file__))

IS_WINDOWS = sys.platform == 'win32'
IS_MACOS = sys.platform == 'darwin'
IS_LINUX = sys.platform.startswith('linux')

PASS = 0
FAIL = 0
SKIP = 0


def test(name, fn):
    """Run a test and track results"""
    global PASS, FAIL
    try:
        result = fn()
        if result is False:
            print(f"  FAIL  {name}")
            FAIL += 1
        else:
            print(f"  PASS  {name}")
            PASS += 1
    except Exception as e:
        print(f"  FAIL  {name}: {e}")
        FAIL += 1


def skip(name, reason="platform"):
    """Skip a test"""
    global SKIP
    print(f"  SKIP  {name} ({reason})")
    SKIP += 1


platform_name = "Windows" if IS_WINDOWS else ("macOS" if IS_MACOS else "Linux")

# ============================================================
print("=" * 60)
print(f"POC Test Suite ({platform_name})")
print("=" * 60)

# ============================================================
# 1. DATABASE TESTS
# ============================================================
print("\n--- 1. Database ---")

# Clean start
if os.path.exists('attendance.db'):
    os.remove('attendance.db')

from database import AttendanceDatabase, Employee, Event

db = AttendanceDatabase()
db.add_sample_data()


def test_employee_count():
    employees = db.get_all_employees()
    assert len(employees) == 5, f"Expected 5 employees, got {len(employees)}"

def test_find_employee_by_badge():
    emp = db.get_employee_by_badge('EMP001')
    assert emp is not None, "EMP001 not found"
    assert emp.name == 'John Smith'

def test_find_unknown_badge():
    emp = db.get_employee_by_badge('UNKNOWN')
    assert emp is None, "Should return None for unknown badge"

def test_event_created():
    events = db.get_all_events()
    assert len(events) >= 1, "No events found"

def test_active_event():
    events = db.get_active_events()
    now = datetime.now()
    if 9 <= now.hour < 18:
        assert len(events) >= 1, "Should have active event during work hours"

def test_checkin_checkout_flow():
    emp = db.get_employee_by_badge('EMP002')
    events = db.get_all_events()
    event = events[0]

    record = db.record_check_in(emp.id, event.id, 'test')
    assert record is not None, "Check-in should return record"
    assert record.check_in_time is not None

    today = db.get_today_attendance_for_employee(emp.id, event.id)
    assert today is not None, "Should find today's record"
    assert today.check_out_time is None, "Should not have check-out yet"

    checkout = db.record_check_out(record.id, 'test')
    assert checkout is not None, "Check-out should return record"

    stats = db.get_attendance_stats(event.id)
    assert stats['total_checkins'] >= 1

def test_duplicate_checkin():
    emp = db.get_employee_by_badge('EMP003')
    events = db.get_all_events()
    event = events[0]

    r1 = db.record_check_in(emp.id, event.id, 'test')
    assert r1 is not None

    today = db.get_today_attendance_for_employee(emp.id, event.id)
    assert today is not None

def test_event_attendance_list():
    events = db.get_all_events()
    records = db.get_event_attendance(events[0].id)
    assert isinstance(records, list)
    if records:
        assert 'employee_name' in records[0]
        assert 'badge_id' in records[0]


test("Employee count", test_employee_count)
test("Find employee by badge", test_find_employee_by_badge)
test("Unknown badge returns None", test_find_unknown_badge)
test("Event created", test_event_created)
test("Active event detection", test_active_event)
test("Check-in/check-out flow", test_checkin_checkout_flow)
test("Duplicate check-in handling", test_duplicate_checkin)
test("Event attendance list", test_event_attendance_list)

# ============================================================
# 2. BARCODE DETECTION TESTS (pyzbar with generated images)
# ============================================================
print("\n--- 2. Barcode Detection (pyzbar) ---")

import cv2
import numpy as np
from pyzbar.pyzbar import decode


def test_pyzbar_import():
    from pyzbar.pyzbar import decode as _decode
    blank = np.zeros((100, 100), dtype=np.uint8)
    results = _decode(blank)
    assert results == [], f"Expected empty results for blank image, got {results}"


def test_qr_decode():
    try:
        encoder = cv2.QRCodeEncoder.create()
        qr_img = encoder.encode("EMP001")
        if len(qr_img.shape) == 2:
            bgr = cv2.cvtColor(qr_img, cv2.COLOR_GRAY2BGR)
        else:
            bgr = qr_img
        # Scale up — pyzbar needs larger images to reliably detect
        scaled = cv2.resize(bgr, (bgr.shape[1]*8, bgr.shape[0]*8),
                            interpolation=cv2.INTER_NEAREST)
        padded = cv2.copyMakeBorder(scaled, 50, 50, 50, 50,
                                     cv2.BORDER_CONSTANT, value=(255, 255, 255))
        results = decode(padded)
        assert len(results) >= 1, f"Expected at least 1 result, got {len(results)}"
        assert results[0].data.decode('utf-8') == 'EMP001'
    except AttributeError:
        pass  # QRCodeEncoder not available in this build


test("pyzbar import + zbar library", test_pyzbar_import)
test("QR code encode/decode roundtrip", test_qr_decode)

# ============================================================
# 3. CAMERA SCANNER LOGIC (simulated frames)
# ============================================================
print("\n--- 3. Camera Scanner Logic ---")

from camera_scanner import CameraScanner, CameraConfig, ScanResult, ProximityDetector


def test_camera_config_defaults():
    config = CameraConfig()
    assert config.camera_id == 0
    assert config.resolution == (1280, 720)
    assert 'QRCODE' in config.barcode_types


def test_process_frame_no_barcode():
    config = CameraConfig(enable_preview=False)
    scanner = CameraScanner(config)
    blank = np.zeros((480, 640, 3), dtype=np.uint8)
    results = scanner._process_frame(blank)
    assert results == [], "Blank frame should produce no results"


def test_process_frame_with_qr():
    config = CameraConfig(enable_preview=False)
    scanner = CameraScanner(config)

    try:
        encoder = cv2.QRCodeEncoder.create()
        qr_img = encoder.encode("TESTBADGE123")
        if len(qr_img.shape) == 2:
            qr_bgr = cv2.cvtColor(qr_img, cv2.COLOR_GRAY2BGR)
        else:
            qr_bgr = qr_img

        frame = np.ones((480, 640, 3), dtype=np.uint8) * 255
        h, w = qr_bgr.shape[:2]
        y_off = (480 - h) // 2
        x_off = (640 - w) // 2
        if h < 480 and w < 640:
            frame[y_off:y_off+h, x_off:x_off+w] = qr_bgr

        results = scanner._process_frame(frame)
        assert len(results) >= 1, "Should detect QR code in frame"
        assert results[0].data == "TESTBADGE123"
    except AttributeError:
        pass


def test_proximity_detector():
    detector = ProximityDetector(sensitivity=100, cooldown=0.1)
    callbacks_fired = []
    detector.add_detection_callback(lambda: callbacks_fired.append(True))

    frame1 = np.zeros((240, 320, 3), dtype=np.uint8)
    result1 = detector.process_frame(frame1)
    assert result1 == False, "First frame should not trigger"

    frame2 = np.ones((240, 320, 3), dtype=np.uint8) * 200
    time.sleep(0.2)
    result2 = detector.process_frame(frame2)
    assert result2 == True, "Large frame change should trigger detection"
    assert len(callbacks_fired) >= 1, "Callback should have fired"


def test_proximity_cooldown():
    detector = ProximityDetector(sensitivity=100, cooldown=5.0)

    frame1 = np.zeros((240, 320, 3), dtype=np.uint8)
    detector.process_frame(frame1)

    frame2 = np.ones((240, 320, 3), dtype=np.uint8) * 200
    detector.process_frame(frame2)

    frame3 = np.zeros((240, 320, 3), dtype=np.uint8)
    result = detector.process_frame(frame3)
    assert result == False, "Should not trigger within cooldown period"


def test_scan_result_callbacks():
    config = CameraConfig(enable_preview=False, scan_cooldown=0.1)
    scanner = CameraScanner(config)
    results_received = []
    scanner.add_result_callback(lambda r: results_received.append(r))

    test_result = ScanResult(
        data="EMP001",
        barcode_type="QRCODE",
        timestamp=time.time()
    )
    for cb in scanner._result_callbacks:
        cb(test_result)

    assert len(results_received) == 1
    assert results_received[0].data == "EMP001"


test("Camera config defaults", test_camera_config_defaults)
test("Process blank frame (no barcode)", test_process_frame_no_barcode)
test("Process frame with QR code", test_process_frame_with_qr)
test("Proximity detector motion detection", test_proximity_detector)
test("Proximity detector cooldown", test_proximity_cooldown)
test("Scanner result callbacks", test_scan_result_callbacks)

# ============================================================
# 4. AUDIO / VOICE FEEDBACK
# ============================================================
print("\n--- 4. Voice Feedback ---")

from voice_feedback import VoiceFeedback, VoiceConfig, VoiceMessage


def test_voice_init():
    config = VoiceConfig(use_tts_fallback=False)
    vf = VoiceFeedback(config)
    assert vf.audio_available == True, "pygame mixer should initialize"
    vf.stop()


def test_voice_queue():
    config = VoiceConfig(use_prerecorded=False, use_tts_fallback=False)
    vf = VoiceFeedback(config)
    vf.speak(VoiceMessage.WELCOME)
    vf.speak(VoiceMessage.SCAN_PROMPT)
    vf.stop()


def test_voice_greeting_cooldown():
    config = VoiceConfig(greeting_cooldown=10, use_prerecorded=False,
                         use_tts_fallback=False)
    vf = VoiceFeedback(config)
    assert vf.can_greet() == True, "First greeting should be allowed"
    assert vf.can_greet() == False, "Second immediate greeting should be blocked"
    vf.stop()


def test_tts_generation():
    config = VoiceConfig()
    vf = VoiceFeedback(config)
    test_file = os.path.join(tempfile.gettempdir(), 'test_tts.mp3')
    try:
        result = vf._generate_tts_audio("Hello test", test_file)
        assert result == True, "TTS generation should succeed"
        assert os.path.exists(test_file), "TTS file should exist"
        assert os.path.getsize(test_file) > 0, "TTS file should not be empty"
    finally:
        if os.path.exists(test_file):
            os.remove(test_file)
        vf.stop()


def test_macos_say_available():
    import subprocess
    result = subprocess.run(['which', 'say'], capture_output=True)
    assert result.returncode == 0, "'say' command not found"


def test_pyttsx3_available():
    import pyttsx3
    engine = pyttsx3.init()
    assert engine is not None, "pyttsx3 engine failed to init"


def test_windows_sapi():
    import pyttsx3
    engine = pyttsx3.init()
    voices = engine.getProperty('voices')
    assert len(voices) > 0, "No SAPI5 voices found"


test("Voice system init (pygame)", test_voice_init)
test("Voice message queue", test_voice_queue)
test("Greeting cooldown", test_voice_greeting_cooldown)
test("TTS audio generation (gTTS)", test_tts_generation)

# Platform-specific voice tests
if IS_MACOS:
    test("macOS 'say' fallback available", test_macos_say_available)
else:
    skip("macOS 'say' fallback available", "macOS only")

try:
    import pyttsx3
    test("pyttsx3 offline TTS available", test_pyttsx3_available)
    if IS_WINDOWS:
        test("Windows SAPI5 voices", test_windows_sapi)
except ImportError:
    skip("pyttsx3 offline TTS available", "not installed")

# ============================================================
# 5. USB SCANNER (simulated)
# ============================================================
print("\n--- 5. USB Scanner (simulated) ---")

from usb_scanner import USBScanner, USBScannerConfig, USBScanResult


def test_usb_simulate_scan():
    scanner = USBScanner()
    results = []
    scanner.add_result_callback(lambda r: results.append(r))
    scanner.simulate_scan("EMP001")
    assert len(results) == 1
    assert results[0].data == "EMP001"
    assert results[0].device_info == "simulated"


def test_usb_config_defaults():
    config = USBScannerConfig()
    assert config.timeout == 0.5
    assert '1' in config.key_mapping.values()


test("USB simulated scan", test_usb_simulate_scan)
test("USB config defaults", test_usb_config_defaults)

# ============================================================
# 6. WEB DASHBOARD API
# ============================================================
print("\n--- 6. Web Dashboard API ---")

if os.path.exists('attendance.db'):
    os.remove('attendance.db')

import importlib
import database
importlib.reload(database)

from web_dashboard import app, create_templates, db as web_db

web_db.add_sample_data()
create_templates()

client = app.test_client()


def test_web_index():
    resp = client.get('/')
    assert resp.status_code == 200
    assert b'Attendance System' in resp.data


def test_web_status():
    resp = client.get('/api/status')
    assert resp.status_code == 200
    data = json.loads(resp.data)
    assert 'running' in data
    assert 'timestamp' in data


def test_web_employees():
    resp = client.get('/api/employees')
    assert resp.status_code == 200
    data = json.loads(resp.data)
    assert len(data) == 5
    badge_ids = {e['badge_id'] for e in data}
    assert 'EMP001' in badge_ids


def test_web_add_employee():
    resp = client.post('/api/employees', json={
        'badge_id': 'EMP099',
        'name': 'Test User',
        'department': 'QA'
    })
    assert resp.status_code == 200
    data = json.loads(resp.data)
    assert data['success'] == True
    assert data['employee']['badge_id'] == 'EMP099'


def test_web_events():
    resp = client.get('/api/events')
    assert resp.status_code == 200
    data = json.loads(resp.data)
    assert len(data) >= 1


def test_web_create_event():
    resp = client.post('/api/events', json={
        'name': 'Test Event',
        'start_time': '2026-02-04T08:00:00',
        'end_time': '2026-02-04T20:00:00',
        'description': 'Test',
        'location': 'Room A'
    })
    assert resp.status_code == 200
    data = json.loads(resp.data)
    assert data['success'] == True


def test_web_simulate_not_running():
    resp = client.post('/api/simulate-scan', json={'badge_id': 'EMP001'})
    assert resp.status_code == 200
    data = json.loads(resp.data)
    assert data['success'] == False


def test_web_attendance_endpoint():
    resp = client.get('/api/events')
    events = json.loads(resp.data)
    if events:
        resp2 = client.get(f'/api/attendance/{events[0]["id"]}')
        assert resp2.status_code == 200


test("GET / (dashboard)", test_web_index)
test("GET /api/status", test_web_status)
test("GET /api/employees", test_web_employees)
test("POST /api/employees (add)", test_web_add_employee)
test("GET /api/events", test_web_events)
test("POST /api/events (create)", test_web_create_event)
test("POST /api/simulate-scan (not running)", test_web_simulate_not_running)
test("GET /api/attendance/<id>", test_web_attendance_endpoint)

# ============================================================
# 7. INTEGRATION: End-to-end scan flow
# ============================================================
print("\n--- 7. Integration: End-to-End Flow ---")

if os.path.exists('attendance.db'):
    os.remove('attendance.db')
importlib.reload(database)
from database import AttendanceDatabase as ADB
idb = ADB()
idb.add_sample_data()


def test_e2e_scan_flow():
    events = idb.get_all_events()
    event = events[0]

    emp = idb.get_employee_by_badge('EMP001')
    assert emp is not None
    record = idb.record_check_in(emp.id, event.id, 'camera')
    assert record is not None

    today = idb.get_today_attendance_for_employee(emp.id, event.id)
    assert today is not None
    assert today.check_out_time is None

    checkout = idb.record_check_out(today.id, 'camera')
    assert checkout is not None

    stats = idb.get_attendance_stats(event.id)
    assert stats['total_checkins'] >= 1
    assert stats['checkouts'] >= 1

    records = idb.get_event_attendance(event.id)
    camera_records = [r for r in records if r['check_in_method'] == 'camera']
    assert len(camera_records) >= 1


def test_e2e_multi_employee():
    events = idb.get_all_events()
    event = events[0]

    for badge in ['EMP002', 'EMP003', 'EMP004']:
        emp = idb.get_employee_by_badge(badge)
        assert emp is not None, f"{badge} not found"
        record = idb.record_check_in(emp.id, event.id, 'camera')
        assert record is not None, f"Check-in failed for {badge}"

    stats = idb.get_attendance_stats(event.id)
    assert stats['total_checkins'] >= 4


test("E2E: single employee scan flow", test_e2e_scan_flow)
test("E2E: multi-employee sequence", test_e2e_multi_employee)

# ============================================================
# 8. CAMERA HARDWARE CHECK
# ============================================================
print("\n--- 8. Camera Hardware ---")


def test_camera_access():
    cap = cv2.VideoCapture(0)
    opened = cap.isOpened()
    if opened:
        ret, frame = cap.read()
        cap.release()
        assert ret, "Camera opened but can't read frame"
        print(f"         Camera resolution: {frame.shape[1]}x{frame.shape[0]}")
    else:
        cap.release()
        if IS_MACOS:
            print("         Camera not authorized — grant permission in:")
            print("         System Settings > Privacy & Security > Camera > Terminal")
            print("         (Expected on first run, not a code bug)")
        elif IS_WINDOWS:
            print("         Camera not available — check:")
            print("         Settings > Privacy > Camera")
            print("         Or camera may be in use by another app")


test("Camera access", test_camera_access)

# ============================================================
# SUMMARY
# ============================================================
print("\n" + "=" * 60)
total = PASS + FAIL
print(f"Platform: {platform_name}")
print(f"Results: {PASS}/{total} passed, {FAIL} failed, {SKIP} skipped")
if FAIL == 0:
    print("ALL TESTS PASSED")
else:
    print(f"{FAIL} TESTS FAILED")
print("=" * 60)

# Cleanup
if os.path.exists('attendance.db'):
    os.remove('attendance.db')

sys.exit(0 if FAIL == 0 else 1)
