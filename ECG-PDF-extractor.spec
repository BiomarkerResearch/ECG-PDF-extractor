# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for ECG-PDF-extractor standalone builds."""

import sys
from pathlib import Path

block_cipher = None

base_dir = Path(__file__).resolve().parent
datas = [
    ("config.ini", "."),
]

hidden_imports = [
    "matplotlib.backends.backend_qtagg",
    "matplotlib.font_manager",
    "PySide6.QtGui",
    "PySide6.QtWidgets",
    "PySide6.QtCore",
    "scipy.interpolate",
    "PyPDF2",
    "PIL",
    "PIL.Image",
    "PIL.ImageDraw",
    "PIL.ImageFont",
]

a = Analysis(
    ["ui.py"],
    pathex=[str(base_dir)],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "unittest",
        "pytest",
        "setuptools",
        "distutils",
        "email",
        "http",
        "xml",
        "pydoc",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure, a.binaries, a.datas, cipher=block_cipher)

if sys.platform == "win32":
    exe = EXE(
        pyz,
        a.scripts,
        [],
        name="ECG-PDF-extractor",
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        console=False,
        disable_windowed_traceback=False,
    )
elif sys.platform == "darwin":
    app = BUNDLE(
        pyz,
        a.scripts,
        [],
        name="ECG-PDF-extractor.app",
        icon=None,
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        upx_exclude=[],
    )
else:
    exe = EXE(
        pyz,
        a.scripts,
        [],
        name="ECG-PDF-extractor",
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        console=False,
        disable_windowed_traceback=False,
    )
