r"""Run the APP's ProximityDetector in People mode on saved frames: checks the shipped
code (plugins/camera/person_detector.py + Min Person) gives the POC's YOLOX-Nano results.

Usage (project venv):
  .venv\Scripts\python.exe scripts\detector-poc\app_detector_check.py <frames_dir> [min_person_pct]
Prints, per frame: persons found, tallest box height % of frame, and whether it counts.
"""
import sys
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from plugins.camera.person_detector import PersonDetector  # noqa: E402

frames_dir = Path(sys.argv[1])
min_pct = float(sys.argv[2]) if len(sys.argv) > 2 else 0.30
det = PersonDetector()
total = counted = 0
for fp in sorted(frames_dir.rglob("*.png")):
    if fp.stem.endswith(("_cmp", "_yolo", "_haar", "_evidence")) or "sheet" in fp.stem \
            or "_yolo_" in fp.stem or fp.stem.startswith("COMPARE"):
        continue
    img = cv2.imread(str(fp))
    h = img.shape[0]
    boxes = det.detect(img)
    tallest = max((b[3] / h for b in boxes), default=0.0)
    ok = tallest >= min_pct
    total += 1
    counted += ok
    print(f"{fp.relative_to(frames_dir)!s:28} persons={len(boxes)} tallest={100 * tallest:3.0f}% "
          f"{'PRESENT' if ok else '-'}")
print(f"\n{counted}/{total} frames count as present at Min Person {100 * min_pct:.0f}%")
