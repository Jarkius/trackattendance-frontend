"""Contact sheet (4 per row) of frames matching a glob, labelled by file name, to score by eye.
Usage: python sheet.py "<glob>" <out.png>"""
import sys, cv2, glob, numpy as np
from pathlib import Path
fs = sorted(glob.glob(sys.argv[1])); t = []
for f in fs:
    i = cv2.resize(cv2.imread(f), (320, 240)); cv2.putText(i, Path(f).stem, (5, 22), 0, 0.6, (0, 255, 255), 2); t.append(i)
while len(t) % 4: t.append(np.zeros_like(t[0]))
cv2.imwrite(sys.argv[2], np.vstack([np.hstack(t[r:r + 4]) for r in range(0, len(t), 4)]))
