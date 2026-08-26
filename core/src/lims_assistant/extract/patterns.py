"""Regex-Muster fuer Etagen, Raeume und Objektueberschriften.

Die Muster arbeiten auf bereinigtem Kleintext MIT Umlauten (Raumnummern wie
"1.234" oder "U16" muessen Punkte/Buchstaben behalten).
"""

from __future__ import annotations

import re

from lims_assistant.textutil import sanitize_lims_value

_B = r"(?<![\wäöüß])"  # linke Wortgrenze auch vor Umlauten
_E = r"(?![\wäöüß])"


def _prep(text: str) -> str:
    return sanitize_lims_value(text).lower()


# ------------------------------------------------------------------ Etage

_ETAGE_RULES: list[tuple[re.Pattern, str]] = [
    (re.compile(_B + r"(\d{1,2})\s*\.?\s*(?:og|obergeschoss)" + _E), "{n}. OG"),
    (re.compile(_B + r"og\s*[-.]?\s*(\d{1,2})" + _E), "{n}. OG"),
    (re.compile(_B + r"(\d{1,2})\s*\.?\s*(?:ug|untergeschoss)" + _E), "{n}. UG"),
    (re.compile(_B + r"ug\s*[-.]?\s*(\d{1,2})" + _E), "{n}. UG"),
    (re.compile(_B + r"(\d{1,2})\s*\.?\s*etage" + _E), "{n}. OG"),
    (re.compile(_B + r"ebene\s*[-.]?\s*(\d{1,3})" + _E), "Ebene {n}"),
    (re.compile(_B + r"(?:eg|erdgeschoss|parterre)" + _E), "EG"),
    (re.compile(_B + r"(?:ug|untergeschoss|souterrain)" + _E), "UG"),
    (re.compile(_B + r"(?:dg|dachgeschoss)" + _E), "DG"),
    (re.compile(_B + r"(?:kg|kellergeschoss|keller)" + _E), "KG"),
]


def scan_etage(text: str) -> str:
    t = _prep(text)
    if not t:
        return ""
    for pattern, template in _ETAGE_RULES:
        m = pattern.search(t)
        if m:
            if "{n}" in template:
                return template.replace("{n}", str(int(m.group(1))))
            return template
    return ""


def normalize_etage_cell(value: str) -> str:
    """Zellwert einer Etagenspalte kanonisieren ("5", "EG", "-1", "5. OG")."""
    raw = sanitize_lims_value(value)
    if not raw:
        return ""
    found = scan_etage(raw)
    if found:
        return found
    m = re.fullmatch(r"[-+]?\d{1,2}", raw)
    if m:
        n = int(m.group(0))
        if n > 0:
            return f"{n}. OG"
        if n == 0:
            return "EG"
        return f"{abs(n)}. UG" if abs(n) > 1 else "UG"
    return raw  # unbekanntes Schema: Freitext erhalten


ETAGE_RANK_SPECIAL = {"KG": -90, "UG": -1, "EG": 0, "DG": 900, "ZG": 50}


def etage_rank(canon: str) -> tuple[int, str]:
    """Sortierschluessel fuer die optionale Sortierung Bez1 -> Etage -> Raum."""
    c = sanitize_lims_value(canon)
    if not c:
        return (10_000, "")
    if c in ETAGE_RANK_SPECIAL:
        return (ETAGE_RANK_SPECIAL[c], c)
    m = re.fullmatch(r"(\d{1,2})\. OG", c)
    if m:
        return (int(m.group(1)), c)
    m = re.fullmatch(r"(\d{1,2})\. UG", c)
    if m:
        return (-int(m.group(1)), c)
    m = re.fullmatch(r"Ebene (\d{1,3})", c)
    if m:
        return (int(m.group(1)), c)
    return (5_000, c)  # unbekannte Schemata stabil ans Ende, alphabetisch


# ------------------------------------------------------------------ Raum

_ZIMMER_RE = re.compile(
    _B + r"zi(?:mmer)?\.?\s*[-:]?\s*([a-zäöüß]{0,3}[-.]?\d[\w./-]*)", re.IGNORECASE
)
_RAUM_RE = re.compile(
    _B + r"r(?:aum)?\.?\s*[-:]?\s*([a-zäöüß]{0,3}[-.]?\d[\w./-]*)", re.IGNORECASE
)
_NR_RE = re.compile(_B + r"nr\.?\s*[-:]?\s*(\d[\w./-]*)", re.IGNORECASE)


def _clean_num(num: str) -> str:
    num = num.strip(".-/ ")
    # Buchstabenpraefixe gross (U16, A1.03)
    m = re.match(r"([a-zäöüß]{1,3})([-.]?\d.*)", num, re.IGNORECASE)
    if m:
        return m.group(1).upper() + m.group(2)
    return num


def scan_raum(text: str) -> tuple[str, str]:
    """Rueckgabe: (label, nummer); label in {"Zimmer", "Raum", ""}."""
    t = _prep(text)
    if not t:
        return "", ""
    m = _ZIMMER_RE.search(t)
    if m:
        return "Zimmer", _clean_num(m.group(1))
    m = _RAUM_RE.search(t)
    if m:
        return "Raum", _clean_num(m.group(1))
    return "", ""


def normalize_raum_cell(value: str, *, zimmer_context: bool = False) -> str:
    """Zellwert einer Raumspalte kanonisieren."""
    raw = sanitize_lims_value(value)
    if not raw:
        return ""
    label, num = scan_raum(raw)
    if label and num:
        return f"{label} {num}"
    if re.fullmatch(r"[A-Za-zÄÖÜäöüß]{0,3}[-.]?\d[\w./-]*", raw):
        label = "Zimmer" if zimmer_context else "Raum"
        return f"{label} {_clean_num(raw)}"
    return raw  # beschreibende Raumnamen unveraendert lassen


def strip_etage_mentions(text: str) -> str:
    t = _prep(text)
    for pattern, _ in _ETAGE_RULES:
        t = pattern.sub(" ", t)
    return t


_BARE_NUM_RE = re.compile(_B + r"(\d{1,4}[a-z]?)" + _E)


def scan_bare_room_number(text: str) -> str:
    """Nackte Raumnummer (nach Entfernen der Etagenangaben), z. B. '... 530 ...'."""
    t = strip_etage_mentions(text)
    m = _BARE_NUM_RE.search(t)
    return m.group(1).upper() if m else ""


_NATURAL_SPLIT = re.compile(r"(\d+)")


def natural_key(value: str) -> tuple:
    """Natuerliche Sortierung ("Zimmer 9" vor "Zimmer 10")."""
    parts = _NATURAL_SPLIT.split(sanitize_lims_value(value).lower())
    return tuple(int(p) if p.isdigit() else p for p in parts)


# ------------------------------------------------------------------ Objekt / Gebaeude

_OBJEKT_RE = re.compile(
    r"^\s*(?:objekt|geb(?:ä|ae)ude|liegenschaft|einrichtung|haus|standort|anlage)\s*[:\-–]\s*(.+)$",
    re.IGNORECASE,
)


def scan_objekt_header(line: str) -> str:
    """Erkennt explizite Objektueberschriften wie 'Objekt: Klinik Moselhoehe'."""
    m = _OBJEKT_RE.match(sanitize_lims_value(line))
    if m:
        return sanitize_lims_value(m.group(1))
    return ""


_HEADER_HINTS = (
    "seite",
    "blatt",
    "datum",
    "auftrag",
    "kunde",
    "probenehmer",
    "erstellt",
    "telefon",
    "unterschrift",
)


def looks_like_metadata(line: str) -> bool:
    t = _prep(line)
    return any(t.startswith(h) or f" {h}" in f" {t}" for h in _HEADER_HINTS)
