#!/usr/bin/env python3
"""Schneidet den Abschnitt einer Version aus CHANGELOG.md heraus.

Wird vom Release-Workflow als Quelle der Releasenotizen benutzt, damit
Changelog und Release nicht auseinanderlaufen. Aufruf:

    python scripts/release_notes.py 0.1.0 [--out release/NOTES.md]
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CHANGELOG = REPO / "CHANGELOG.md"


def extract(version: str, text: str) -> str:
    """Liefert den Rumpf von '## [<version>] ...' bis zur naechsten '## '-Zeile."""
    start = re.search(rf"^## \[{re.escape(version)}\].*$", text, re.MULTILINE)
    if start is None:
        raise SystemExit(
            f"Kein Abschnitt '## [{version}]' in {CHANGELOG.name} gefunden."
        )
    rest = text[start.end() :]
    nxt = re.search(r"^## ", rest, re.MULTILINE)
    body = rest[: nxt.start()] if nxt else rest
    # Verweislinks am Dateiende gehoeren nicht in die Notizen.
    body = re.sub(r"^\[[^\]]+\]:.*$", "", body, flags=re.MULTILINE)
    body = body.strip()
    if not body:
        raise SystemExit(f"Abschnitt '## [{version}]' ist leer.")
    return body


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("version", help="Version ohne fuehrendes 'v', z. B. 0.1.0")
    ap.add_argument("--out", help="Zieldatei (Standard: Ausgabe auf stdout)")
    args = ap.parse_args(argv)

    body = extract(args.version, CHANGELOG.read_text(encoding="utf-8"))
    notes = (
        f"{body}\n\n---\n\n"
        "## Die beiden Archive\n\n"
        f"**`lims-probenassistent-{args.version}-einrichtung.zip`** - hiermit\n"
        "anfangen. Enthaelt `einrichten.ps1`, die VBA-Quellen der Arbeitsmappe,\n"
        "`build_workbook.ps1` und die Anleitungen. Entpacken und ausfuehren:\n\n"
        "```\n"
        'powershell -ExecutionPolicy Bypass -File einrichten.ps1 -Ziel "C:\\LIMS-PA"\n'
        "```\n\n"
        f"**`lims_core-{args.version}-windows-x64.zip`** - der Rechenkern\n"
        "(portable onedir-EXE inklusive `hashes.json`). Wird von\n"
        "`einrichten.ps1` automatisch geladen; separat nur noetig, wenn der\n"
        "Zielrechner kein Internet hat (dann mit `-Paket` uebergeben).\n\n"
        "Pruefsummen liegen jeweils als `.sha256` daneben.\n\n"
        "## Zwei Dinge vorab\n\n"
        "**Die Excel-Arbeitsmappe ist in keinem der Archive.** Sie entsteht\n"
        "einmalig aus den VBA-Textmodulen und braucht dafuer Excel selbst -\n"
        "das laesst sich nicht vorbauen. Schritt 2 in `ERSTE_SCHRITTE.md`\n"
        "beschreibt beide Wege (Skript oder von Hand, ca. 5 Minuten).\n\n"
        "**`lims_core.exe` per Doppelklick tut nichts Sichtbares.** Der Kern\n"
        "hat keine eigene Oberflaeche, er wird von der Arbeitsmappe\n"
        "gesteuert. Zum Pruefen: `lims_core.exe health` in einer\n"
        "Eingabeaufforderung.\n\n"
        "**Fuer deutsche Umlaute in Scans:** Das Paket bringt nur die\n"
        "RapidOCR-Standardmodelle (chinesisch/englisch) mit, die Umlaute\n"
        "verlieren. Latin-Modell nachruesten mit\n"
        "`provision_offline.ps1 -Step model`. Digitale PDFs und Excel-Dateien\n"
        "sind nicht betroffen.\n"
    )
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(notes, encoding="utf-8")
        print(f"Releasenotizen geschrieben: {out}")
    else:
        sys.stdout.write(notes)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
