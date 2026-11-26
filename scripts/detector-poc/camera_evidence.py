"""Grab frames from the kiosk camera and run the app's own detectors on them; draw every box.

Green = YuNet face (passes the face minimum), cyan = upper-body box, labelled with its width %
and whether it passes the OLD rule (same minimum as faces) and the NEW rule (2x the face
minimum). Saves one annotated image; prints a summary. Run with the kiosk app closed.

Usage: python camera_evidence.py <camera_index> <min_size_pct> <out.png>
"""
import sys
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from plugins.camera.proximity_detector import ProximityDetector  # noqa: E402

cam_index, min_pct, out = int(sys.argv[1]), float(sys.argv[2]), sys.argv[3]
cap = cv2.VideoCapture(cam_index)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
frames = []
for _ in range(40):                      # let exposure settle, keep the last few
    ok, f = cap.read()
    if ok:
        frames.append(f)
cap.release()
if not frames:
    sys.exit("could not read from camera")
frame = frames[-1]
h, w = frame.shape[:2]

det = ProximityDetector(min_size_pct=min_pct)
gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
shown = frame.copy()

# Faces: YuNet, any size (to see what is there), marked whether they pass the face minimum
faces = []
if det._yunet is not None:
    det._yunet.setInputSize((w, h))
    _, found = det._yunet.detect(frame)
    for f in (found if found is not None else []):
        x, y, fw, fh = map(int, f[:4])
        ok = fw >= w * min_pct
        faces.append((fw, ok, float(f[-1])))
        cv2.rectangle(shown, (x, y), (x + fw, y + fh), (0, 255, 0) if ok else (0, 120, 0), 2)
        cv2.putText(shown, f"face {100*fw/w:.0f}% {'OK' if ok else 'small'}", (x, max(12, y - 4)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 0), 1)

# Upper body: run the cascade with the OLD minimum (smaller), then judge each box both ways
bodies = []
if det._haar_upperbody is not None:
    found = det._haar_upperbody.detectMultiScale(
        gray, scaleFactor=1.05, minNeighbors=det.haar_min_neighbors,
        minSize=(int(w * min_pct), int(w * min_pct)))
    for (x, y, bw, bh) in found:
        old_ok = bw >= w * min_pct
        new_ok = bw >= w * min(0.8, 2 * min_pct)
        bodies.append((int(bw), old_ok, new_ok))
        cv2.rectangle(shown, (x, y), (x + bw, y + bh), (255, 255, 0), 2)
        cv2.putText(shown, f"body {100*bw/w:.0f}% old:{'Y' if old_ok else 'n'} new:{'Y' if new_ok else 'n'}",
                    (x, min(h - 4, y + bh + 14)), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 0), 1)

cv2.imwrite(out, shown)
print(f"frame {w}x{h}, brightness {frame.mean():.0f}/255, face minimum {100*min_pct:.0f}%,"
      f" body minimum old {100*min_pct:.0f}% / new {100*min(0.8, 2*min_pct):.0f}%")
print("faces:", [(f"{100*fw/w:.0f}%", "passes" if ok else "too small", f"score {s:.2f}") for fw, ok, s in faces] or "none")
print("bodies:", [(f"{100*bw/w:.0f}%", f"old rule {'PRESENT' if o else 'no'}", f"new rule {'PRESENT' if n else 'no'}")
                  for bw, o, n in bodies] or "none")
print("saved", out)
