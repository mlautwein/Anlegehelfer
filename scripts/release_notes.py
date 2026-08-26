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
        "Das Paket `lims_core-<version>-windows-x64.zip` enthaelt die portable\n"
        "onedir-EXE inklusive `hashes.json`. Pruefsumme des ZIP siehe\n"
        "beiliegende `.sha256`-Datei. Bereitstellung: `docs/WINDOWS_BUILD.md`.\n"
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
