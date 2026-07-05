# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for FabInventory standalone executable."""

import sys
from pathlib import Path

_block_cipher = None

# Collect all template and static files
# PyInstaller datas format: (source_path, dest_directory)
ROOT = Path(SPECPATH)
_templates = [(str(p), str(p.parent.relative_to(ROOT)))
              for p in (ROOT / 'templates').rglob('*') if p.is_file()]
_static = [(str(p), str(p.parent.relative_to(ROOT)))
           for p in (ROOT / 'static').rglob('*') if p.is_file()]

a = Analysis(
    ['run.py'],
    pathex=[],
    binaries=[],
    datas=_templates + _static,
    hiddenimports=[
        'flask',
        'flask_wtf',
        'jinja2',
        'jinja2.ext',
        'werkzeug',
        'pandas',
        'openpyxl',
        'dotenv',
        'python_dotenv',
        'markdown',
        'pydantic',
        'requests',
        'zipfile',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=_block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=_block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='FabInventory',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='FabInventory',
)
