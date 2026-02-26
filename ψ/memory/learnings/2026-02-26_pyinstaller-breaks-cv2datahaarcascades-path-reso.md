---
title: PyInstaller breaks cv2.data.haarcascades path resolution — the attribute points 
tags: [PyInstaller, OpenCV, Haar-cascade, path-resolution, bundling, deployment]
created: 2026-02-26
source: rrr: trackattendance-frontend
---

# PyInstaller breaks cv2.data.haarcascades path resolution — the attribute points 

PyInstaller breaks cv2.data.haarcascades path resolution — the attribute points to the installed package path, not the _MEIPASS extraction. Fix: try multiple candidates (cv2.data attr, cv2 package dir, _MEIPASS). Always bundle data files in the .spec and add _MEIPASS path resolution in the same commit as the feature. General rule: for ANY file-path-dependent feature in a PyInstaller project, update spec datas AND runtime path resolution together.

---
*Added via Oracle Learn*
