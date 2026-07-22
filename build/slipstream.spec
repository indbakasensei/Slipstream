# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller build spec for Slipstream — see build/README.md for usage.

Invoke via the provided scripts (build/build.ps1), or directly:

    pyinstaller build/slipstream.spec --distpath dist --workpath .pyinstaller_cache

One-folder build (not one-file): this keeps PySide6's LGPLv3-licensed Qt
DLLs as separate, individually replaceable files rather than unpacked into
a hidden temp directory at runtime — the LGPL-compliance approach already
named in docs/CFD_PLATFORM_BLUEPRINT.md §20 ("PyInstaller one-folder keeps
Qt DLLs separate"). Do not switch this to a one-file build without
revisiting that compliance note.

Version metadata is generated from cfdauto.__version__ (the single
authoritative version source — see cfdauto/__init__.py) by
build/make_version_info.py, never duplicated here.
"""

import sys
from pathlib import Path

REPO_ROOT = Path(SPECPATH).resolve().parent  # build/../ = repo root
sys.path.insert(0, str(REPO_ROOT))

# No icon asset exists in this repository yet (Sprint 6: "do not invent
# branding assets"). Drop a .ico here to enable one — nothing else to
# change; the spec picks it up automatically.
ICON_PATH = REPO_ROOT / "gui" / "resources" / "slipstream.ico"
ICON = str(ICON_PATH) if ICON_PATH.exists() else None

VERSION_INFO_PATH = REPO_ROOT / "build" / "version_info.txt"
VERSION_INFO = str(VERSION_INFO_PATH) if VERSION_INFO_PATH.exists() else None

block_cipher = None

a = Analysis(
    [str(REPO_ROOT / "gui_main.py")],
    pathex=[str(REPO_ROOT)],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    cipher=block_cipher,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Slipstream",
    icon=ICON,
    version=VERSION_INFO,
    console=False,          # windowed GUI app, no console window
    disable_windowed_traceback=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name="Slipstream",
)
