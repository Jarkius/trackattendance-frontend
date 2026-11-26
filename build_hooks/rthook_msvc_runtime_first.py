"""PyInstaller run-time hook (TrackAttendance.spec): runs before PyInstaller's own hooks.

PyInstaller's PyQt6 hook imports QtCore, which loads PyQt6's bundled MSVC runtime 14.26.
onnxruntime (camera People mode) crashes the process (access violation) on that runtime.
On camera stations, load the current runtime bundled next to the app (TrackAttendance.spec
msvc_binaries) by full path first: Windows then reuses these copies for every later load by
name, so Qt and onnxruntime share the new runtime. Other stations are left untouched.
"""


def _load_current_msvc_runtime():
    import ctypes
    import os
    import sys

    if sys.platform != "win32":
        return
    try:
        import config  # reads .env next to the exe; no Qt
        if not config.ENABLE_CAMERA_DETECTION:
            return
    except Exception:
        return
    for name in ("vcruntime140.dll", "vcruntime140_1.dll",
                 "msvcp140.dll", "msvcp140_1.dll", "msvcp140_2.dll"):
        try:
            ctypes.WinDLL(os.path.join(sys._MEIPASS, name))
        except OSError:
            pass


_load_current_msvc_runtime()
del _load_current_msvc_runtime
