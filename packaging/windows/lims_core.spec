# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller-Spezifikation: portable Windows-x64-onedir-EXE.

onedir statt onefile (bewusste Entscheidung): Modelle/OCR-Dateien liegen
ohnehin als Begleitartefakte daneben; onefile wuerde bei grossen Artefakten
nur Start- und Temporaerprobleme erzeugen. Kein Installer, keine Adminrechte.

Aufruf (auf Windows x64):
    pyinstaller --clean --noconfirm packaging\\windows\\lims_core.spec
"""

import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

REPO = Path(SPECPATH).resolve().parents[1]
SRC = REPO / "core" / "src"
sys.path.insert(0, str(SRC))

hiddenimports = (
    collect_submodules("lims_assistant")
    + collect_submodules("pdfplumber")
    + collect_submodules("pypdfium2")
    + ["pillow_heif", "openpyxl", "xlrd"]
)

datas = []
binaries = []
try:
    # RapidOCR (optional): gebuendelte ONNX-Modelle und Konfiguration mitnehmen
    datas += collect_data_files("rapidocr_onnxruntime")
    hiddenimports += collect_submodules("rapidocr_onnxruntime")
    hiddenimports += ["onnxruntime"]
except Exception:  # noqa: BLE001 - OCR-Extra nicht installiert
    pass

a = Analysis(
    [str(SRC / "lims_assistant" / "jobs" / "cli.py")],
    pathex=[str(SRC)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "IPython", "pytest", "reportlab", "xlwt"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="lims_core",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="lims_core",
)
