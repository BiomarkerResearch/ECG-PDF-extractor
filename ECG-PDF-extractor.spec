# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for ECG-PDF-extractor standalone builds."""

import sys

block_cipher = None

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
    pathex=[],
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

pyz = PYZ(a.pure, cipher=block_cipher)

if sys.platform == "win32":
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.datas,
        name="ECG-PDF-extractor",
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        console=False,
        disable_windowed_traceback=False,
    )
elif sys.platform == "darwin":
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.datas,
        name="ECG-PDF-extractor",
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        console=False,
        disable_windowed_traceback=False,
    )
    app = BUNDLE(
        exe,
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
        a.binaries,
        a.datas,
        name="ECG-PDF-extractor",
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        console=False,
        disable_windowed_traceback=False,
    )
