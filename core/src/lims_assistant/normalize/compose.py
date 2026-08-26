"""Kanonische Bildung der fuenf LIMS-Felder aus Rohmerkmalen.

Deterministisch: Das Sprachmodell darf Inhalte vorschlagen, aber niemals
Format, Reihenfolge oder Trennzeichen bestimmen.
"""

from __future__ import annotations

from dataclasses import dataclass

from lims_assistant.extract.features import SRC_FUZZY, RowFeatures
from lims_assistant.textutil import join_parts, sanitize_lims_value
from lims_assistant.version import NORMALIZER_VERSION

# Basissicherheiten je Herkunft. Werte >= Schwellwert (Standard 0.75) gelten
# als "nicht gelb"; bewusste Konventionsableitungen liegen knapp darueber,
# echte Vermutungen darunter.
SCORE_STRUCTURE = 0.95
SCORE_DIRECT = 0.92
SCORE_CONVENTION = 0.80  # fachliche Standardauslegung (z. B. RL -> Zirkulation)
SCORE_FUZZY = 0.60       # nur ueber OCR-Reparatur gefunden
SCORE_WEAK = 0.55        # schwache Kontextableitung


@dataclass
class Composed:
    value: str = ""
    score: float = 0.0
    provenance: str = "empty"  # direct | structure | empty
    detail: str = ""
    normalizer_version: str = NORMALIZER_VERSION


def _part_score(src: str) -> float:
    if src == "structure":
        return SCORE_STRUCTURE
    if src == "direct":
        return SCORE_DIRECT
    if src == SRC_FUZZY:
        return SCORE_FUZZY
    return 0.0


def _prov(srcs: list[str]) -> str:
    real = [s for s in srcs if s]
    if not real:
        return "empty"
    if all(s == "structure" for s in real):
        return "structure"
    return "direct"


def compose_bez1(f: RowFeatures) -> Composed:
    value = sanitize_lims_value(f.bez1)
    if not value:
        return Composed()
    return Composed(
        value=value,
        score=_part_score(f.bez1_src) or SCORE_WEAK,
        provenance=_prov([f.bez1_src]),
        detail=f"bez1:{f.bez1_src}",
    )


def compose_bez2(f: RowFeatures) -> Composed:
    raumtyp = f.raumtyp
    # "Zimmer 7, Zimmer" vermeiden: generischer Raumtyp traegt nichts bei.
    if raumtyp and f.raum and raumtyp.lower() in ("zimmer", "raum"):
        raumtyp = ""
    parts = [f.etage, f.raum, raumtyp]
    srcs = [f.etage_src, f.raum_src, f.raumtyp_src]
    value = join_parts(parts)
    if not value:
        return Composed()
    used = [(p, s) for p, s in zip(parts, srcs) if sanitize_lims_value(p)]
    score = min(_part_score(s) for _, s in used)
    return Composed(
        value=value,
        score=score,
        provenance=_prov([s for _, s in used]),
        detail="bez2:" + "+".join(s or "-" for _, s in used),
    )


_VL_RL_LABEL = {"vl": "Vorlauf", "rl": "Rücklauf"}


def compose_b3(f: RowFeatures) -> Composed:
    if f.technical:
        # technisch: kontextgerechte kuerzere Folge; Kuerzel wie PNV erhalten.
        element = ""
        if f.vl_rl:
            element = _VL_RL_LABEL[f.vl_rl]
        elif f.zusatz == "Zirkulation":
            element = "Zirkulation"
        elif f.zusatz == "Speicher":
            element = "Speicher"
        elif f.zusatz == "DLE":
            element = "DLE"
        valve = "PNV" if f.pnv else (f.armatur or f.wasserstelle)
        value = join_parts([element, valve])
        if not value:
            return Composed()
        score = SCORE_DIRECT if (f.pnv or f.vl_rl or f.zusatz) else SCORE_WEAK
        if "armatur" in f.fuzzy_categories or "wasserstelle" in f.fuzzy_categories:
            score = min(score, SCORE_FUZZY)
        return Composed(
            value=value,
            score=score,
            provenance="direct",
            detail="b3:technisch",
        )

    parts = [f.ort, f.wasserstelle, f.armatur]
    srcs = [f.ort_src, f.wasserstelle_src, f.armatur_src]
    value = join_parts(parts)
    if not value:
        return Composed()
    used = [(p, s) for p, s in zip(parts, srcs) if sanitize_lims_value(p)]
    score = min(_part_score(s) for _, s in used)
    return Composed(
        value=value,
        score=score,
        provenance=_prov([s for _, s in used]),
        detail="b3:sanitaer",
    )


def compose_b4(f: RowFeatures) -> Composed:
    medium = f.medium
    zusatz = f.zusatz
    score = _part_score(f.medium_src) if medium else 0.0
    detail_parts = []
    if medium:
        detail_parts.append(f"medium:{f.medium_src}")

    # Fachliche Konventionen fuer Warmwasser-Systeme:
    if not zusatz and f.vl_rl == "rl":
        zusatz = "Zirkulation"
        detail_parts.append("zusatz:konvention-rl")
    if not medium and (zusatz or f.vl_rl):
        # Zirkulation/Speicher/DLE/VL/RL implizieren Trinkwarmwasser.
        medium = "Warmwasser"
        score = SCORE_CONVENTION
        detail_parts.append("medium:konvention-tww")
    if medium == "Kaltwasser":
        zusatz = ""  # Kaltwasser ohne technischen Zusatz ausgeben

    value = join_parts([medium, zusatz])
    if not value:
        return Composed()
    if zusatz and f.zusatz_src == SRC_FUZZY:
        score = min(score or SCORE_FUZZY, SCORE_FUZZY)
    if f.medium_conflict:
        score = min(score or SCORE_WEAK, SCORE_WEAK)
        detail_parts.append("medium:konflikt")
    if not score:
        score = SCORE_CONVENTION
    return Composed(
        value=value,
        score=score,
        provenance="structure" if f.medium_src == "structure" else "direct",
        detail="b4:" + ",".join(detail_parts),
    )


def compose_untersuchungsart(f: RowFeatures) -> Composed:
    value = sanitize_lims_value(f.untersuchung)
    if not value:
        return Composed()
    return Composed(
        value=value,
        score=_part_score(f.untersuchung_src) or SCORE_WEAK,
        provenance=_prov([f.untersuchung_src]),
        detail=f"unt:{f.untersuchung_src}",
    )


def compose_all(f: RowFeatures) -> dict[str, Composed]:
    return {
        "Bez1": compose_bez1(f),
        "Bez2": compose_bez2(f),
        "B3": compose_b3(f),
        "B4": compose_b4(f),
        "Untersuchungsart": compose_untersuchungsart(f),
    }
