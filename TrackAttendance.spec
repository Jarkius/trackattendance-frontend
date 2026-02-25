# -*- mode: python ; coding: utf-8 -*-

import certifi
from PyInstaller.utils.hooks import collect_data_files

# Collect certifi's certificate bundle
certifi_datas = collect_data_files('certifi')

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
    ] + certifi_datas,
    hiddenimports=['certifi', 'truststore'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
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
