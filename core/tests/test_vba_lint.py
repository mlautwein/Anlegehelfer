"""VBA-Textmodule muessen die Repo-Regeln einhalten (Lint als Test-Gate)."""

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def test_vba_lint_gruen():
    proc = subprocess.run(
        [sys.executable, str(REPO / "scripts" / "vba_lint.py")],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_alle_module_vorhanden():
    vba = REPO / "excel" / "vba-src"
    expected = {
        "modConfig.bas",
        "modJson.bas",
        "modJobClient.bas",
        "modClipboard.bas",
        "modErgebnisse.bas",
        "modAssistent.bas",
        "modCopyConfirm.bas",
        "modExport.bas",
        "modUndo.bas",
        "modMain.bas",
        "modSetup.bas",
        "ThisWorkbook.cls",
        "SheetErgebnisse.cls",
        "SheetAssistent.cls",
    }
    present = {p.name for p in vba.iterdir() if p.suffix in (".bas", ".cls")}
    assert expected <= present, expected - present
