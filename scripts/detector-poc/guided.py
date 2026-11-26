"""Beep-guided capture of a person in 5 poses (4 frames each) into .scratchpad/yolo-poc/frames/person/.
Beeps = pose number: 1 close, 2 far, 3 side-on, 4 edge, 5 walk past; long beep = done. Starts after 10 s.
Usage: python guided.py [camera_index]   (Windows only: uses winsound)"""
import sys, time, winsound, cv2
from pathlib import Path
OUT = Path(__file__).resolve().parents[2] / ".scratchpad" / "yolo-poc" / "frames" / "person"
OUT.mkdir(parents=True, exist_ok=True)
POSES = ["close", "far", "side", "edge", "walk"]
c = cv2.VideoCapture(int(sys.argv[1]) if len(sys.argv) > 1 else 1); c.set(3, 640); c.set(4, 480)
def idle(sec):
    t = time.time()
    while time.time() - t < sec: c.read()
idle(10)
for n, pose in enumerate(POSES, 1):
    for _ in range(n): winsound.Beep(1000, 200); time.sleep(0.15)
    idle(5)
    for k in range(4):
        idle(2); ok, f = c.read(); cv2.imwrite(str(OUT / f"{n}_{pose}_{k}.png"), f)
winsound.Beep(600, 900); c.release(); print("done")
