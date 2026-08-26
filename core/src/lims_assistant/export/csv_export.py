"""Atomarer Fuenffach-CSV-Export.

- Genau fuenf einspaltige Dateien mit festen Namen, ohne Header.
- Eine Probe je Zeile; leere Werte bleiben leere Zeilen an gleicher Position.
- CRLF; UTF-8 mit BOM (Standard) oder Windows-1252.
- Erst werden alle fuenf Temporaerdateien vollstaendig geschrieben, dann
  werden alle Ziele ersetzt. Schlaegt irgendein Schritt der Temp-Phase fehl,
  bleiben vorhandene Zieldateien unveraendert.
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path

from lims_assistant.domain.entities import EXPORT_FILENAMES, FIELDS
from lims_assistant.textutil import sanitize_lims_value, sha256_text

BOM_UTF8 = b"\xef\xbb\xbf"
CRLF = "\r\n"

# Transliteration fuer Windows-1252 (typografische Zeichen sichern).
_CP1252_FALLBACK = str.maketrans(
    {
        "–": "-",
        "—": "-",
        "‘": "'",
        "’": "'",
        "‚": "'",
        "“": '"',
        "”": '"',
        "„": '"',
        "…": "...",
        " ": " ",
        "•": "*",
    }
)


def render_column(values: list[str]) -> str:
    """Dateiinhalt einer Spalte (jede Zeile mit CRLF terminiert).

    Bewusst KEIN CSV-Quoting: Die Dateien sind einspaltige Zeilenlisten fuer
    die LIMS-Uebernahme. Kommas sind regulaerer Bestandteil der Werte
    ("5. OG, Zimmer 530, ..."); Anfuehrungszeichen wuerden die Werte
    verfaelschen. Zeilenumbrueche/Tabs sind bereits deterministisch zu
    Leerzeichen normalisiert, daher ist jede Zeile exakt ein Wert.
    """
    lines = [sanitize_lims_value(v) for v in values]
    if not lines:
        return ""
    return CRLF.join(lines) + CRLF


def encode_content(content: str, encoding: str) -> bytes:
    if encoding == "utf8_bom":
        return BOM_UTF8 + content.encode("utf-8")
    if encoding == "cp1252":
        return content.translate(_CP1252_FALLBACK).encode("cp1252", errors="replace")
    raise ValueError(f"Unbekannte Kodierung: {encoding}")


def _write_tmp(path: Path, data: bytes) -> None:
    with open(path, "wb") as fh:
        fh.write(data)
        fh.flush()
        os.fsync(fh.fileno())


def export_five(
    rows: list[list[str]],
    target_dir: str | Path,
    *,
    encoding: str = "utf8_bom",
) -> tuple[list[str], dict[str, str]]:
    """Schreibt die fuenf Exportdateien atomar. Rueckgabe: (Dateien, Hashes).

    rows: Liste von Zeilen mit genau fuenf Textwerten in Feldreihenfolge.
    """
    target = Path(target_dir)
    if not target.is_dir():
        raise FileNotFoundError(f"Zielordner fehlt: {target}")
    for row in rows:
        if len(row) != len(FIELDS):
            raise ValueError("Jede Exportzeile braucht genau fuenf Werte")

    token = uuid.uuid4().hex[:12]
    tmp_files: list[tuple[Path, Path]] = []
    hashes: dict[str, str] = {}
    try:
        for col, filename in enumerate(EXPORT_FILENAMES):
            content = render_column([row[col] for row in rows])
            data = encode_content(content, encoding)
            tmp = target / f".{filename}.{token}.tmp"
            _write_tmp(tmp, data)
            hashes[filename] = sha256_text(content)
            tmp_files.append((tmp, target / filename))
    except BaseException:
        for tmp, _ in tmp_files:
            try:
                tmp.unlink(missing_ok=True)
            except OSError:
                pass
        raise

    # Temp-Phase vollstaendig erfolgreich -> jetzt alle Ziele ersetzen.
    for tmp, final in tmp_files:
        os.replace(tmp, final)
    return [str(target / f) for f in EXPORT_FILENAMES], hashes
