r"""Run the app's current detector (YuNet face >= min, else Haar upper body >= min) on frames.
Use the PROJECT venv:  .venv\Scripts\python.exe scripts\detector-poc\current_detector.py <frame>..."""
import sys
from pathlib import Path
import cv2
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from plugins.camera.proximity_detector import ProximityDetector
MIN = 0.09
d = ProximityDetector(min_size_pct=MIN)
for fp in sys.argv[1:]:
    img = cv2.imread(fp); h, w = img.shape[:2]
    d._yunet.setInputSize((w, h)); _, faces = d._yunet.detect(img)
    faces = [f for f in (faces if faces is not None else []) if f[2] >= w * MIN]
    bodies = [] if faces else d._haar_upperbody.detectMultiScale(
        cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), 1.05, d.haar_min_neighbors, minSize=(int(w * MIN),) * 2)
    res = (f"face {100 * faces[0][2] / w:.0f}%w" if len(faces) else
           f"body {100 * bodies[0][2] / w:.0f}%w" if len(bodies) else "0")
    print(f"{Path(fp).name:22} {res}")
