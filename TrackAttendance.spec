# -*- mode: python ; coding: utf-8 -*-

import certifi
import cv2
import os
from PyInstaller.utils.hooks import collect_data_files

# Collect certifi's certificate bundle
certifi_datas = collect_data_files('certifi')

# onnxruntime (camera People mode, YOLOX-Nano) is shipped as plain files, NOT analysed:
# PyInstaller's dependency scan imports every package in one subprocess with PyQt6 first,
# and onnxruntime crashes when loaded after PyQt6's old MSVC runtime (14.26). At run time
# main.py imports it before PyQt6 from _internal/onnxruntime. It needs only numpy + stdlib.
import glob
import importlib.util
_ort_spec = importlib.util.find_spec('onnxruntime')  # locates without importing
ort_datas = []
if _ort_spec is not None:
    _ort_dir = os.path.dirname(_ort_spec.origin)
    ort_datas.append((_ort_dir, 'onnxruntime'))
    for _dist in glob.glob(os.path.join(os.path.dirname(_ort_dir), 'onnxruntime-*.dist-info')):
        ort_datas.append((_dist, os.path.basename(_dist)))
# A current MSVC C++ runtime next to the exe, so onnxruntime (loaded first) never needs the
# PC's own copy and Qt then shares it. Microsoft allows app-local deployment of these DLLs.
_sys32 = os.path.join(os.environ.get('SystemRoot', r'C:\Windows'), 'System32')
msvc_binaries = [(os.path.join(_sys32, n), '.') for n in ('msvcp140.dll', 'msvcp140_1.dll', 'msvcp140_2.dll')
                 if os.path.exists(os.path.join(_sys32, n))]

# Haar cascade XML for face detection fallback
_cv2_data = os.path.join(os.path.dirname(cv2.__file__), 'data')
haar_datas = [(_cv2_data, os.path.join('cv2', 'data'))] if os.path.isdir(_cv2_data) else []

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=msvc_binaries,
    datas=[
        ('.env', '.'),
        ('web', 'web'),
        ('assets/voices', 'assets/voices'),
        ('assets/media', 'assets/media'),  # neutral screensaver defaults; event files go in media/
        ('plugins/camera/models', 'plugins/camera/models'),
        ('plugins/camera/greetings', 'plugins/camera/greetings'),
    ] + certifi_datas + haar_datas + ort_datas,
    # stdlib modules onnxruntime imports (it is shipped as files, so not analysed)
    hiddenimports=['certifi', 'truststore', 'pycaw', 'pycaw.pycaw', 'comtypes', 'comtypes.stream',
                   'platform', 'linecache', 'ctypes', 'importlib.metadata', 'weakref', 'typing',
                   'collections.abc', 'enum', 'contextlib', 'warnings'],
    hookspath=[],
    hooksconfig={},
    # must run before PyInstaller's PyQt6 hook (custom run-time hooks run first)
    runtime_hooks=['build_hooks/rthook_msvc_runtime_first.py'],
    excludes=[
        'onnxruntime',  # shipped as plain files, see ort_datas above
        # Unused PyQt6 modules — reduces bundle by ~30-50MB
        'PyQt6.QtDesigner',
        'PyQt6.QtHelp',
        # NOTE: QtNetwork was previously excluded on the assumption that
        # `requests` covers all HTTP needs, but QtWebEngineWidgets depends on
        # it internally (QWebEngineView fails to import without it) — keep it.
        'PyQt6.QtSql',
        'PyQt6.QtSvg',
        'PyQt6.QtSvgWidgets',
        'PyQt6.QtTest',
        'PyQt6.QtXml',
        'PyQt6.QtDBus',
        'PyQt6.QtBluetooth',
        'PyQt6.QtNfc',
        'PyQt6.QtPositioning',
        'PyQt6.QtRemoteObjects',
        'PyQt6.QtSensors',
        'PyQt6.QtSerialPort',
        'PyQt6.QtTextToSpeech',
        'PyQt6.Qt3DCore',
        'PyQt6.Qt3DRender',
        'PyQt6.Qt3DInput',
        'PyQt6.Qt3DExtras',
    ],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

# --onedir mode: no _MEIPASS extraction delay on startup
exe = EXE(
    pyz,
    a.scripts,
    [],          # binaries/datas go to COLLECT, not EXE
    name='TrackAttendance',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['assets/greendot.ico'],
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name='TrackAttendance',
)
