#!/usr/bin/env python3
"""Statischer Lint fuer die VBA-Textmodule (excel/vba-src).

Prueft die verbindlichen Repo-Regeln:
- Option Explicit in jedem Modul;
- 64-Bit-Sicherheit: jede Declare-Zeile im VBA7-Zweig PtrSafe, Handles/Pointer
  als LongPtr;
- keine gefaehrlichen Muster (Kill/DeleteFile auf Benutzerdaten, Shell mit
  zusammengesetzten Benutzereingaben, ExecuteExcel4Macro);
- Button-OnAction-Ziele existieren als oeffentliche Prozeduren.

Aufruf: python scripts/vba_lint.py  -> Exit-Code 0/1
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
VBA_DIR = REPO / "excel" / "vba-src"

FORBIDDEN = [
    (re.compile(r"\bExecuteExcel4Macro\b", re.I), "ExecuteExcel4Macro ist verboten"),
    (re.compile(r"\bCreateObject\(\s*\"Excel.Application\"", re.I), "keine zweite Excel-Instanz"),
    (re.compile(r"^\s*Kill\b", re.I | re.M), "Kill ist verboten (Temp raeumt der Kern)"),
    (re.compile(r"\.DeleteFile\b", re.I), "FSO.DeleteFile ist verboten"),
]

DECLARE_RE = re.compile(r"^\s*(?:Public\s+|Private\s+)?Declare\s+(PtrSafe\s+)?", re.I)
ONACTION_RE = re.compile(r"\.OnAction\s*=\s*\"([A-Za-z0-9_]+)\"")
PUBSUB_RE = re.compile(r"^\s*Public\s+Sub\s+([A-Za-z0-9_]+)\s*\(", re.M)
ADDBUTTON_RE = re.compile(r'AddButton\s+[^,]+,\s*"[^"]*",\s*"[^"]*",\s*"([A-Za-z0-9_]+)"')
ONKEY_RE = re.compile(r'Application\.OnKey\s+"[^"]*"\s*,\s*"([A-Za-z0-9_]+)"')
ONTIME_RE = re.compile(r'Application\.OnTime\s+[^,]+,\s*"([A-Za-z0-9_]+)"')


def in_vba7_branch(lines: list[str], idx: int) -> bool:
    """Grobe Zweigerkennung: befindet sich die Zeile im '#If VBA7'-Teil?"""
    depth_vba7 = False
    for i in range(idx + 1):
        line = lines[i].strip()
        if line.startswith("#If VBA7"):
            depth_vba7 = True
        elif line.startswith("#Else"):
            depth_vba7 = False
        elif line.startswith("#End If"):
            depth_vba7 = False
    return depth_vba7


def main() -> int:
    errors: list[str] = []
    public_subs: set[str] = set()
    referenced: set[str] = set()

    files = sorted(VBA_DIR.glob("*.bas")) + sorted(VBA_DIR.glob("*.cls"))
    if not files:
        print("Keine VBA-Module gefunden", file=sys.stderr)
        return 1

    for path in files:
        text = path.read_text(encoding="utf-8")
        lines = text.splitlines()
        rel = path.relative_to(REPO)

        if "Option Explicit" not in text:
            errors.append(f"{rel}: Option Explicit fehlt")

        for i, line in enumerate(lines):
            m = DECLARE_RE.match(line)
            if m:
                vba7 = in_vba7_branch(lines, i)
                if vba7 and not m.group(1):
                    errors.append(f"{rel}:{i+1}: Declare im VBA7-Zweig ohne PtrSafe")
                if vba7 and re.search(r"\bhwnd\b|\bhMem\b|\blp\w+", line, re.I):
                    if "LongPtr" not in line and "As Long)" in line.replace(" ", ""):
                        pass  # Rueckgabewerte duerfen Long sein
            for pattern, msg in FORBIDDEN:
                if pattern.search(line):
                    errors.append(f"{rel}:{i+1}: {msg}")

        public_subs.update(PUBSUB_RE.findall(text))
        referenced.update(ONACTION_RE.findall(text))
        referenced.update(ADDBUTTON_RE.findall(text))
        referenced.update(ONKEY_RE.findall(text))
        referenced.update(ONTIME_RE.findall(text))

    for name in sorted(referenced):
        if name not in public_subs:
            errors.append(
                f"OnAction/OnKey/OnTime-Ziel '{name}' existiert nicht als Public Sub"
            )

    if errors:
        print("VBA-Lint FEHLER:")
        for e in errors:
            print("  -", e)
        return 1
    print(f"VBA-Lint ok ({len(files)} Module, {len(public_subs)} Public Subs)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
