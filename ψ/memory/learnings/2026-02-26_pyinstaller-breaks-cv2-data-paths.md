# PyInstaller Breaks cv2.data Path Resolution

**Date**: 2026-02-26
**Project**: trackattendance-frontend
**Context**: Haar cascade XML not found in .exe because cv2.data.haarcascades path doesn't resolve inside _MEIPASS

## Pattern

When bundling OpenCV features that depend on data files (Haar cascades, DNN models), `cv2.data.haarcascades` resolves to the installed package path, which doesn't exist inside PyInstaller's temp extraction directory.

## Fix

Try multiple path candidates:
```python
candidates = []
if hasattr(cv2, 'data') and hasattr(cv2.data, 'haarcascades'):
    candidates.append(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
candidates.append(os.path.join(os.path.dirname(cv2.__file__), 'data', 'file.xml'))
if getattr(sys, 'frozen', False):
    candidates.append(os.path.join(sys._MEIPASS, 'cv2', 'data', 'file.xml'))
```

And bundle the data directory in the .spec:
```python
_cv2_data = os.path.join(os.path.dirname(cv2.__file__), 'data')
haar_datas = [(_cv2_data, os.path.join('cv2', 'data'))]
```

## General Rule

For ANY file-path-dependent feature in a PyInstaller project: update the .spec file `datas` AND add `_MEIPASS` path resolution in the same commit.
