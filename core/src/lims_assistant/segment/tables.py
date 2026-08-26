"""Tabellensegmentierung: Spaltenkoepfe erkennen und Zellen zuordnen."""

from __future__ import annotations

from dataclasses import dataclass

from lims_assistant.extract.features import CellMap
from lims_assistant.textutil import fold_for_match, sanitize_lims_value

# Kategorie -> gefaltete Kopf-Synonyme
HEADER_SYNONYMS: dict[str, set[str]] = {
    "nr": {"nr", "lfd", "lfd nr", "pos", "position", "nummer", "probe nr", "proben nr"},
    "bez1": {
        "objekt",
        "gebaeude",
        "haus",
        "liegenschaft",
        "einrichtung",
        "standort",
        "objektname",
        "objekt gebaeude",
    },
    "etage": {"etage", "geschoss", "ebene", "stockwerk", "og ug", "etage geschoss"},
    "raum": {
        "raum",
        "zimmer",
        "raum nr",
        "raumnr",
        "zimmer nr",
        "zimmernr",
        "raumnummer",
        "zimmernummer",
        "raum nummer",
        "raumbezeichnung",
        "raum zimmer",
    },
    "raumtyp": {"raumart", "raumtyp", "nutzung", "nutzungsart", "raumnutzung"},
    "entnahme": {
        "probenahmestelle",
        "probennahmestelle",
        "probeentnahmestelle",
        "entnahmestelle",
        "probenstelle",
        "zapfstelle",
        "wasserstelle",
        "entnahmepunkt",
        "entnahmearmatur",
        "messstelle",
        "probenahmeort",
    },
    "armatur": {"armatur", "armaturtyp", "armaturart", "armaturen"},
    "medium": {"medium", "wasserart", "wasser", "kalt warm", "kw ww", "medium zusatz"},
    "untersuchung": {
        "untersuchung",
        "untersuchungsart",
        "parameter",
        "analyse",
        "analysen",
        "umfang",
        "pruefung",
        "untersuchungsumfang",
    },
    "bemerkung": {"bemerkung", "bemerkungen", "hinweis", "hinweise", "kommentar", "anmerkung"},
}


def classify_header_cell(text: str) -> str:
    folded = fold_for_match(text)
    if not folded:
        return ""
    best: tuple[int, str] | None = None
    for category, synonyms in HEADER_SYNONYMS.items():
        for syn in synonyms:
            if folded == syn:
                return category
            if f" {syn} " in f" {folded} ":
                if best is None or len(syn) > best[0]:
                    best = (len(syn), category)
    return best[1] if best else ""


@dataclass
class HeaderMap:
    columns: dict[int, str]  # Spaltenindex -> Kategorie
    matched: int

    def is_usable(self) -> bool:
        distinct = {c for c in self.columns.values() if c and c not in ("nr", "bemerkung")}
        return len(distinct) >= 2


def detect_header(row: list[str | None]) -> HeaderMap:
    columns: dict[int, str] = {}
    matched = 0
    for idx, cell in enumerate(row):
        cat = classify_header_cell(cell or "")
        if cat:
            matched += 1
        columns[idx] = cat
    return HeaderMap(columns=columns, matched=matched)


def find_header_row(rows: list[list[str | None]], scan_limit: int = 12) -> tuple[int, HeaderMap] | None:
    best: tuple[int, HeaderMap] | None = None
    for idx, row in enumerate(rows[:scan_limit]):
        hm = detect_header(row)
        if hm.is_usable():
            if best is None or hm.matched > best[1].matched:
                best = (idx, hm)
    return best


def row_to_cells(row: list[str | None], header: HeaderMap) -> CellMap:
    cells = CellMap()
    for idx, raw in enumerate(row):
        value = sanitize_lims_value(raw or "")
        if not value:
            continue
        cat = header.columns.get(idx, "")
        if cat == "bez1":
            cells.bez1 = (cells.bez1 + " " + value).strip()
        elif cat == "etage":
            cells.etage = (cells.etage + " " + value).strip()
        elif cat == "raum":
            cells.raum = (cells.raum + " " + value).strip()
        elif cat == "raumtyp":
            cells.raumtyp = (cells.raumtyp + " " + value).strip()
        elif cat == "entnahme":
            cells.entnahme = (cells.entnahme + " " + value).strip()
        elif cat == "armatur":
            cells.armatur = (cells.armatur + " " + value).strip()
        elif cat == "medium":
            cells.medium = (cells.medium + " " + value).strip()
        elif cat == "untersuchung":
            cells.untersuchung = (cells.untersuchung + " " + value).strip()
        elif cat == "bemerkung":
            cells.bemerkung = (cells.bemerkung + " " + value).strip()
        # "nr" und unbekannte Spalten: nur Teil des Zeilentexts
    return cells


def row_text(row: list[str | None]) -> str:
    values = [sanitize_lims_value(c or "") for c in row]
    return " | ".join(v for v in values if v)


def is_repeated_header(row: list[str | None], header: HeaderMap) -> bool:
    hm = detect_header(row)
    return hm.is_usable() and hm.columns == header.columns


def data_signal(cells: CellMap) -> bool:
    """Traegt die Zeile ausser Nr/Bemerkung irgendeinen Inhalt?"""
    return any(
        [
            cells.etage,
            cells.raum,
            cells.raumtyp,
            cells.entnahme,
            cells.armatur,
            cells.medium,
            cells.untersuchung,
        ]
    )
