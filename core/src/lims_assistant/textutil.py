"""Deterministische Textwerkzeuge fuer LIMS-Werte und Signaturen."""

from __future__ import annotations

import hashlib
import re
import unicodedata

_WS_RE = re.compile(r"[ \t\r\n\f\v ]+")
_CTRL_RE = re.compile(r"[\x00-\x1f\x7f]")


def sanitize_lims_value(value: str | None) -> str:
    """Normalisiert einen LIMS-Zellwert deterministisch.

    - Zeilenumbrueche/Tabs -> genau ein Leerzeichen
    - Steuerzeichen entfernen, Mehrfach-Leerraum kollabieren, trimmen
    - "" bleibt ein gueltiger, positionshaltender Wert
    """
    if value is None:
        return ""
    s = unicodedata.normalize("NFC", str(value))
    s = _CTRL_RE.sub(" ", s)
    s = _WS_RE.sub(" ", s)
    return s.strip()


def collapse_ws(value: str) -> str:
    return _WS_RE.sub(" ", value or "").strip()


def fold_for_match(value: str) -> str:
    """Vergleichsform: klein, Umlaute ausgeschrieben, Satzzeichen -> Raum.

    Nur fuer Matching/Signaturen - niemals fuer Ausgabewerte.
    """
    s = sanitize_lims_value(value).lower()
    s = (
        s.replace("ä", "ae")
        .replace("ö", "oe")
        .replace("ü", "ue")
        .replace("ß", "ss")
    )
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return collapse_ws(s)


def join_parts(parts: list[str | None], sep: str = ", ") -> str:
    """Verbindet Teile ohne Platzhalter, doppelte Kommas oder haengende Trenner."""
    cleaned = [sanitize_lims_value(p) for p in parts]
    cleaned = [p for p in cleaned if p]
    return sep.join(cleaned)


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def sha256_file(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def levenshtein(a: str, b: str, max_dist: int | None = None) -> int:
    """Einfache Levenshtein-Distanz (klein genug fuer Vokabular-Fuzzy-Match)."""
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    if max_dist is not None and abs(len(a) - len(b)) > max_dist:
        return max_dist + 1
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        best = i
        for j, cb in enumerate(b, 1):
            cost = 0 if ca == cb else 1
            v = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost)
            cur.append(v)
            best = min(best, v)
        if max_dist is not None and best > max_dist:
            return max_dist + 1
        prev = cur
    return prev[-1]


def token_set(value: str) -> set[str]:
    return set(fold_for_match(value).split())
