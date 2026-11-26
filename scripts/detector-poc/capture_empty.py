"""Capture N frames of the empty scene, one every 3 s, after a 20 s delay to leave the view.
Usage: python capture_empty.py <out_dir> <n> [camera_index]"""
import sys, time, cv2
out, n = sys.argv[1], int(sys.argv[2])
time.sleep(20)
c = cv2.VideoCapture(int(sys.argv[3]) if len(sys.argv) > 3 else 1); c.set(3, 640); c.set(4, 480)
for _ in range(30): c.read()
for i in range(n):
    t = time.time()
    while time.time() - t < 3: c.read()
    ok, f = c.read(); cv2.imwrite(f"{out}/empty_{i:02d}.png", f)
c.release(); print("captured", n)
