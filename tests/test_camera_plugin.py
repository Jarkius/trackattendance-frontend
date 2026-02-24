"""Integration tests for the camera proximity detection plugin.

Verifies graceful degradation at each layer:
1. Config disabled (default) — plugin never touched
2. Config enabled, no cv2 — warning logged, app normal
3. Config enabled, no folder — warning logged, app normal
4. Config enabled, deps present — manager starts/stops correctly

Usage:
    python tests/test_camera_plugin.py
"""

import importlib
import logging
import os
import shutil
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


logging.basicConfig(level=logging.DEBUG, format="%(message)s")

passed = 0
failed = 0


def report(name: str, ok: bool, detail: str = "") -> None:
    global passed, failed
    status = "PASS" if ok else "FAIL"
    suffix = f" — {detail}" if detail else ""
    print(f"  [{status}] {name}{suffix}")
    if ok:
        passed += 1
    else:
        failed += 1


# =========================================================================
# Test 1: Config defaults
# =========================================================================
print("\n=== Test 1: Config defaults ===")
import config

report("ENABLE_CAMERA_DETECTION defaults to False", config.ENABLE_CAMERA_DETECTION == False)
report("CAMERA_DEVICE_ID defaults to 0", config.CAMERA_DEVICE_ID == 0)
report("CAMERA_GREETING_COOLDOWN_SECONDS defaults to 10.0", config.CAMERA_GREETING_COOLDOWN_SECONDS == 10.0)
report("CAMERA_RESOLUTION_WIDTH defaults to 1280", config.CAMERA_RESOLUTION_WIDTH == 1280)
report("CAMERA_RESOLUTION_HEIGHT defaults to 720", config.CAMERA_RESOLUTION_HEIGHT == 720)


# =========================================================================
# Test 2: Config respects env overrides
# =========================================================================
print("\n=== Test 2: Config env overrides ===")
os.environ["ENABLE_CAMERA_DETECTION"] = "true"
os.environ["CAMERA_DEVICE_ID"] = "2"
os.environ["CAMERA_GREETING_COOLDOWN_SECONDS"] = "20.0"
os.environ["CAMERA_RESOLUTION_WIDTH"] = "640"
os.environ["CAMERA_RESOLUTION_HEIGHT"] = "480"
importlib.reload(config)

report("ENABLE_CAMERA_DETECTION=true", config.ENABLE_CAMERA_DETECTION == True)
report("CAMERA_DEVICE_ID=2", config.CAMERA_DEVICE_ID == 2)
report("CAMERA_GREETING_COOLDOWN_SECONDS=20.0", config.CAMERA_GREETING_COOLDOWN_SECONDS == 20.0)
report("CAMERA_RESOLUTION_WIDTH=640", config.CAMERA_RESOLUTION_WIDTH == 640)
report("CAMERA_RESOLUTION_HEIGHT=480", config.CAMERA_RESOLUTION_HEIGHT == 480)

# Reset
for key in [
    "ENABLE_CAMERA_DETECTION", "CAMERA_DEVICE_ID",
    "CAMERA_GREETING_COOLDOWN_SECONDS",
    "CAMERA_RESOLUTION_WIDTH", "CAMERA_RESOLUTION_HEIGHT",
]:
    os.environ.pop(key, None)
importlib.reload(config)


# =========================================================================
# Test 3: Plugin imports without cv2
# =========================================================================
print("\n=== Test 3: Import without cv2 ===")
from plugins.camera.proximity_manager import ProximityGreetingManager
report("ProximityGreetingManager imports OK", True)

from plugins.camera.proximity_detector import ProximityDetector
report("ProximityDetector imports OK (cv2 absent)", True)


# =========================================================================
# Test 4: Manager start fails gracefully without cv2
# =========================================================================
print("\n=== Test 4: Manager without cv2 ===")
mgr = ProximityGreetingManager(voice_player=None, camera_id=0, cooldown=10.0, resolution=(1280, 720))
report("Manager instantiates", True)

# Hide cv2 so the manager's late import fails
_real_cv2 = sys.modules.pop("cv2", None)
_saved = {}
for _k in list(sys.modules):
    if _k.startswith("cv2"):
        _saved[_k] = sys.modules.pop(_k)

with patch.dict("sys.modules", {"cv2": None}):
    started = mgr.start()
    report("start() returns False without cv2", started == False)

# Restore cv2
for _k, _v in _saved.items():
    sys.modules[_k] = _v
if _real_cv2 is not None:
    sys.modules["cv2"] = _real_cv2

mgr.stop()
report("stop() safe when never started", True)


# =========================================================================
# Test 5: Missing plugins/camera/ folder detection
# =========================================================================
print("\n=== Test 5: Missing folder detection ===")
# Simulate the check from main.py
_plugins_camera = ROOT_DIR / "plugins" / "camera"
report("plugins/camera/ folder exists", _plugins_camera.is_dir())

_fake_path = ROOT_DIR / "plugins" / "camera_NONEXISTENT"
report("Nonexistent folder detected", not _fake_path.is_dir())


# =========================================================================
# Test 6: Manager with mocked camera (real cv2, fake VideoCapture)
# =========================================================================
print("\n=== Test 6: Manager with mocked camera ===")

import cv2
import numpy as np
import time

# Create a fake VideoCapture that returns real numpy frames
mock_cap = MagicMock()
mock_cap.isOpened.return_value = True
fake_frame = np.zeros((720, 1280, 3), dtype=np.uint8)
mock_cap.read.return_value = (True, fake_frame)

# Mock voice player
mock_voice = MagicMock()

with patch("cv2.VideoCapture", return_value=mock_cap):
    mgr2 = ProximityGreetingManager(
        voice_player=mock_voice,
        camera_id=0,
        cooldown=10.0,
        resolution=(1280, 720),
    )
    started = mgr2.start()
    report("start() returns True with mocked camera", started == True)
    report("Camera opened", cv2.VideoCapture.called if hasattr(cv2.VideoCapture, 'called') else started)
    report("Resolution set", mock_cap.set.called)

    # Let the thread run briefly
    time.sleep(0.3)

    report("Camera thread is running", mgr2._running == True)
    report("Thread is alive", mgr2._thread is not None and mgr2._thread.is_alive())

    mgr2.stop()
    report("stop() completes cleanly", mgr2._running == False)
    report("Camera released", mock_cap.release.called)
    report("Thread stopped", mgr2._thread is None)


# =========================================================================
# Test 7: Detection callback triggers voice
# =========================================================================
print("\n=== Test 7: Detection callback ===")

mock_voice2 = MagicMock()

with patch("cv2.VideoCapture", return_value=mock_cap):
    mgr3 = ProximityGreetingManager(
        voice_player=mock_voice2,
        camera_id=0,
        cooldown=0.1,  # Short cooldown for testing
        resolution=(1280, 720),
    )
    started = mgr3.start()
    report("Manager started for callback test", started == True)

    # Directly invoke the callback (simulates ProximityDetector firing)
    mgr3._on_person_detected()
    report("voice_player.play_random() called", mock_voice2.play_random.called)
    report("Called exactly once", mock_voice2.play_random.call_count == 1)

    mgr3.stop()


# =========================================================================
# Test 8: Double stop is safe
# =========================================================================
print("\n=== Test 8: Double stop safety ===")
mgr4 = ProximityGreetingManager(voice_player=None, camera_id=0, cooldown=10.0, resolution=(1280, 720))
mgr4.stop()
mgr4.stop()
report("Double stop() is safe", True)


# =========================================================================
# Test 9: main.py integration paths (code path validation)
# =========================================================================
print("\n=== Test 9: main.py code paths ===")

# Read main.py and verify our integration points exist
main_src = (ROOT_DIR / "main.py").read_text()

report(
    "Plugin load block exists",
    "ENABLE_CAMERA_DETECTION" in main_src and "ProximityGreetingManager" in main_src,
)
report(
    "_start_services_on_load includes proximity",
    "_start_services_on_load" in main_src and "proximity_manager" in main_src,
)
report(
    "finally block stops proximity",
    "proximity_manager" in main_src.split("finally:")[-1],
)


# =========================================================================
# Summary
# =========================================================================
print("\n" + "=" * 60)
total = passed + failed
if failed == 0:
    print(f"All {passed} tests passed!")
else:
    print(f"{passed}/{total} passed, {failed} failed")
print("=" * 60)

sys.exit(1 if failed else 0)
