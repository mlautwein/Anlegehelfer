"""Deterministische Merkmalsextraktion je Rohzeile/Tabellenzeile."""

from __future__ import annotations

from dataclasses import dataclass, field

from lims_assistant.extract import patterns, vocab
from lims_assistant.textutil import fold_for_match, sanitize_lims_value

# Herkunft eines Merkmals
SRC_NONE = ""
SRC_STRUCTURE = "structure"  # aus zugeordneter Tabellenspalte
SRC_DIRECT = "direct"        # im Zeilentext klar gefunden
SRC_FUZZY = "fuzzy"          # nur per Fuzzy-/OCR-Reparatur gefunden


@dataclass
class CellMap:
    """Zellwerte einer Tabellenzeile nach Spaltenzuordnung."""

    bez1: str = ""
    etage: str = ""
    raum: str = ""
    raumtyp: str = ""
    entnahme: str = ""   # Probenahmestelle/Wasserstelle/Armatur gemischt
    armatur: str = ""
    medium: str = ""
    untersuchung: str = ""
    bemerkung: str = ""

    def joined(self) -> str:
        parts = [
            self.bez1,
            self.etage,
            self.raum,
            self.raumtyp,
            self.entnahme,
            self.armatur,
            self.medium,
            self.untersuchung,
            self.bemerkung,
        ]
        return " | ".join(p for p in (sanitize_lims_value(x) for x in parts) if p)


@dataclass
class RowFeatures:
    source_text: str = ""
    bez1: str = ""
    bez1_src: str = SRC_NONE
    etage: str = ""
    etage_src: str = SRC_NONE
    raum: str = ""            # kanonisch, z. B. "Zimmer 530" / "Raum U16"
    raum_src: str = SRC_NONE
    raumtyp: str = ""
    raumtyp_src: str = SRC_NONE
    ort: str = ""
    ort_src: str = SRC_NONE
    wasserstelle: str = ""
    wasserstelle_src: str = SRC_NONE
    armatur: str = ""
    armatur_src: str = SRC_NONE
    medium: str = ""          # "Kaltwasser" | "Warmwasser" | ""
    medium_src: str = SRC_NONE
    zusatz: str = ""          # "Zirkulation" | "Speicher" | "DLE" | ""
    zusatz_src: str = SRC_NONE
    vl_rl: str = ""           # "vl" | "rl" | ""
    pnv: bool = False
    technical: bool = False
    untersuchung: str = ""
    untersuchung_src: str = SRC_NONE
    fuzzy_categories: set[str] = field(default_factory=set)
    medium_conflict: bool = False

    def signal_count(self) -> int:
        """Wie viele probenstellentypische Signale traegt die Zeile?"""
        n = 0
        if self.medium:
            n += 2
        if self.wasserstelle or self.armatur or self.pnv:
            n += 2
        if self.zusatz or self.vl_rl:
            n += 1
        if self.raum:
            n += 1
        if self.etage:
            n += 1
        if self.raumtyp:
            n += 1
        return n


def _scan_medium(folded: str) -> tuple[str, bool]:
    kalt = vocab.any_token(folded, vocab.MEDIUM_KALT)
    warm = vocab.any_token(folded, vocab.MEDIUM_WARM)
    if kalt and warm:
        return "", True
    if kalt:
        return "Kaltwasser", False
    if warm:
        return "Warmwasser", False
    return "", False


def _scan_zusatz(folded: str) -> str:
    if vocab.any_token(folded, vocab.ZUSATZ_ZIRK):
        return "Zirkulation"
    if vocab.any_token(folded, vocab.ZUSATZ_SPEICHER):
        return "Speicher"
    if vocab.any_token(folded, vocab.ZUSATZ_DLE):
        return "DLE"
    return ""


def _scan_vl_rl(folded: str) -> str:
    if vocab.any_token(folded, vocab.RL_TOKENS):
        return "rl"
    if vocab.any_token(folded, vocab.VL_TOKENS):
        return "vl"
    return ""


def _set(features: RowFeatures, attr: str, value: str, src: str) -> None:
    if value and not getattr(features, attr):
        setattr(features, attr, value)
        setattr(features, f"{attr}_src", src)
        if src == SRC_FUZZY:
            features.fuzzy_categories.add(attr)


def extract_features(
    source_text: str,
    cells: CellMap | None = None,
    *,
    allow_fuzzy: bool = True,
) -> RowFeatures:
    """Extrahiert alle Rohmerkmale einer Zeile.

    Reihenfolge je Kategorie: zugeordnete Spalte -> direkter Text -> Fuzzy.
    """
    f = RowFeatures(source_text=sanitize_lims_value(source_text))
    text_all = f.source_text
    folded_all = fold_for_match(text_all)

    # ---------------- strukturierte Zellen zuerst
    if cells is not None:
        _set(f, "bez1", sanitize_lims_value(cells.bez1), SRC_STRUCTURE)
        _set(f, "etage", patterns.normalize_etage_cell(cells.etage), SRC_STRUCTURE)

        raumtyp_cell = vocab.match_vocab(fold_for_match(cells.raumtyp), vocab.RAUMTYP_MAP)
        if raumtyp_cell:
            _set(f, "raumtyp", raumtyp_cell, SRC_STRUCTURE)
        elif sanitize_lims_value(cells.raumtyp):
            _set(f, "raumtyp", sanitize_lims_value(cells.raumtyp), SRC_STRUCTURE)

        zimmer_ctx = f.raumtyp.endswith("zimmer") or f.raumtyp.endswith("Zimmer")
        _set(
            f,
            "raum",
            patterns.normalize_raum_cell(cells.raum, zimmer_context=zimmer_ctx),
            SRC_STRUCTURE,
        )

        entnahme_folded = fold_for_match(
            " ".join([cells.entnahme, cells.armatur])
        )
        ws = vocab.match_vocab(entnahme_folded, vocab.WASSERSTELLE_MAP)
        _set(f, "wasserstelle", ws or "", SRC_STRUCTURE)
        arm = vocab.match_vocab(entnahme_folded, vocab.ARMATUR_MAP)
        _set(f, "armatur", arm or "", SRC_STRUCTURE)
        ort = vocab.match_vocab(entnahme_folded, vocab.ORT_MAP)
        _set(f, "ort", ort or "", SRC_STRUCTURE)
        if vocab.any_token(entnahme_folded, vocab.PNV_TOKENS):
            f.pnv = True

        medium_folded = fold_for_match(cells.medium)
        med, conflict = _scan_medium(medium_folded)
        if conflict:
            f.medium_conflict = True
        _set(f, "medium", med, SRC_STRUCTURE)
        _set(f, "zusatz", _scan_zusatz(medium_folded + " " + entnahme_folded), SRC_STRUCTURE)
        if not f.vl_rl:
            f.vl_rl = _scan_vl_rl(medium_folded + " " + entnahme_folded)

        unt = vocab.match_vocab(fold_for_match(cells.untersuchung), vocab.UNTERSUCHUNG_MAP)
        if unt:
            _set(f, "untersuchung", unt, SRC_STRUCTURE)
        elif sanitize_lims_value(cells.untersuchung):
            _set(f, "untersuchung", sanitize_lims_value(cells.untersuchung), SRC_STRUCTURE)

    # ---------------- direkter Zeilentext
    _set(f, "etage", patterns.scan_etage(text_all), SRC_DIRECT)
    label, num = patterns.scan_raum(text_all)
    if label and num:
        _set(f, "raum", f"{label} {num}", SRC_DIRECT)
    _set(f, "raumtyp", vocab.match_vocab(folded_all, vocab.RAUMTYP_MAP) or "", SRC_DIRECT)
    _set(f, "ort", vocab.match_vocab(folded_all, vocab.ORT_MAP) or "", SRC_DIRECT)
    _set(
        f,
        "wasserstelle",
        vocab.match_vocab(folded_all, vocab.WASSERSTELLE_MAP) or "",
        SRC_DIRECT,
    )
    _set(f, "armatur", vocab.match_vocab(folded_all, vocab.ARMATUR_MAP) or "", SRC_DIRECT)
    if vocab.any_token(folded_all, vocab.PNV_TOKENS):
        f.pnv = True
    med, conflict = _scan_medium(folded_all)
    if conflict and not f.medium:
        f.medium_conflict = True
    _set(f, "medium", med, SRC_DIRECT)
    _set(f, "zusatz", _scan_zusatz(folded_all), SRC_DIRECT)
    if not f.vl_rl:
        f.vl_rl = _scan_vl_rl(folded_all)
    _set(
        f,
        "untersuchung",
        vocab.match_vocab(folded_all, vocab.UNTERSUCHUNG_MAP) or "",
        SRC_DIRECT,
    )

    # ---------------- Fuzzy-Reparatur (OCR) nur fuer noch leere Kategorien
    if allow_fuzzy:
        if not f.raumtyp:
            _set(
                f,
                "raumtyp",
                vocab.match_vocab_fuzzy(folded_all, vocab.RAUMTYP_MAP) or "",
                SRC_FUZZY,
            )
        if not f.wasserstelle:
            _set(
                f,
                "wasserstelle",
                vocab.match_vocab_fuzzy(folded_all, vocab.WASSERSTELLE_MAP) or "",
                SRC_FUZZY,
            )
        if not f.armatur:
            _set(
                f,
                "armatur",
                vocab.match_vocab_fuzzy(folded_all, vocab.ARMATUR_MAP) or "",
                SRC_FUZZY,
            )
        if not f.medium:
            fuzzy_med = vocab.match_vocab_fuzzy(
                folded_all,
                {"kaltwasser": "Kaltwasser", "warmwasser": "Warmwasser"},
            )
            _set(f, "medium", fuzzy_med or "", SRC_FUZZY)

    # ---------------- Nachbereinigung: Ort vs. Raumtyp nie identisch doppelt
    if f.ort and f.raumtyp == f.ort:
        if f.raumtyp_src == SRC_STRUCTURE:
            # Dedizierte Raumart-Spalte ist massgeblich; Ort waere Dopplung.
            f.ort = ""
            f.ort_src = SRC_NONE
        elif f.ort in ("Bad", "WC") and (f.wasserstelle or f.armatur):
            # Sanitaerort dominiert: "Bad, Waschbecken, Einhandmischarmatur".
            f.raumtyp = ""
            f.raumtyp_src = SRC_NONE
        else:
            # Kueche/Teekueche & Co.: Raumtyp gehoert nach Bez2, nicht in B3.
            f.ort = ""
            f.ort_src = SRC_NONE

    # "Patientenzimmer 530" (nur Freitextzeilen): nackte Nummer als Raum werten.
    # Bei Tabellenzeilen nie - dort waere es meist die laufende Nummer.
    if cells is None and not f.raum and f.raumtyp and (
        f.raumtyp.lower().endswith("zimmer") or f.raumtyp in vocab.RAUMTYP
    ):
        num = patterns.scan_bare_room_number(text_all)
        if num:
            label = "Zimmer" if f.raumtyp.lower().endswith("zimmer") else "Raum"
            _set(f, "raum", f"{label} {num}", SRC_FUZZY)

    # ---------------- technischer Kontext
    tech_tokens = vocab.any_token(folded_all, vocab.TECH_HINWEIS)
    sanitary = bool(f.wasserstelle or f.ort or (f.armatur and not f.pnv))
    f.technical = bool(
        (f.raumtyp in vocab.TECH_RAUMTYPEN and not sanitary)
        or f.pnv
        or (tech_tokens and not sanitary)
        or (f.raumtyp in vocab.TECH_RAUMTYPEN and (f.zusatz or f.vl_rl))
    )
    return f
