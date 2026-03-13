# -*- mode: python ; coding: utf-8 -*-

import certifi
import cv2
import os
from PyInstaller.utils.hooks import collect_data_files

# Collect certifi's certificate bundle
certifi_datas = collect_data_files('certifi')

# Haar cascade XML for face detection fallback
_cv2_data = os.path.join(os.path.dirname(cv2.__file__), 'data')
haar_datas = [(_cv2_data, os.path.join('cv2', 'data'))] if os.path.isdir(_cv2_data) else []

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('.env', '.'),
        ('web', 'web'),
        ('assets/voices', 'assets/voices'),
        ('plugins/camera/models', 'plugins/camera/models'),
        ('plugins/camera/greetings', 'plugins/camera/greetings'),
    ] + certifi_datas + haar_datas,
    hiddenimports=['certifi', 'truststore'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Unused PyQt6 modules — reduces bundle by ~30-50MB
        'PyQt6.QtDesigner',
        'PyQt6.QtHelp',
        'PyQt6.QtNetwork',       # requests handles HTTP
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
    icon=['C:\\Workspace\\Dev\\Python\\greendot.ico'],
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name='TrackAttendance',
)
