"""Confidence-Fusion: Kandidaten je Feld -> finaler Wert + gelbe Markierung.

Nachvollziehbar und deterministisch:
- Kandidatenquellen: Komposition (direkt/Struktur), aehnliche Lernfaelle,
  LLM-Vorschlag, Zusatztext, Dokument-/Titelkontext.
- Gelb genau dann, wenn Provenienz nicht direkt/strukturell ist, die
  kalibrierte Basissicherheit unter dem Schwellwert liegt, OCR schwach ist
  oder Spitzenkandidaten widersprechen (Kap. 10.4 der Spezifikation).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from lims_assistant.domain.entities import FIELDS, Provenance
from lims_assistant.normalize.compose import Composed

SCORE_RETRIEVAL_FACTOR = 0.85
SCORE_LLM = 0.60
SCORE_HINT = 0.50
SCORE_DOC_CONTEXT = 0.70
SCORE_BEZ1_EXPLICIT = 0.95
SCORE_BEZ1_TITLE = 0.65
CONFLICT_MARGIN = 0.08
ALWAYS_UNCERTAIN = {
    Provenance.RETRIEVAL.value,
    Provenance.LLM.value,
    Provenance.HINT.value,
    "title",
    "doc_context",
}


@dataclass
class Candidate:
    value: str
    provenance: str
    score: float
    detail: str = ""


@dataclass
class Decision:
    value: str = ""
    is_uncertain: bool = False
    provenance: str = Provenance.EMPTY.value
    score: float = 0.0
    candidates: list[Candidate] = field(default_factory=list)


def _decide(
    candidates: list[Candidate],
    *,
    threshold: float,
    ocr_weak: bool,
) -> Decision:
    real = [c for c in candidates if c.value]
    if not real:
        return Decision(candidates=candidates)
    ranked = sorted(real, key=lambda c: (-c.score, c.provenance, c.value))
    top = ranked[0]
    uncertain = (
        top.provenance in ALWAYS_UNCERTAIN
        or top.score < threshold
        or ocr_weak
    )
    if len(ranked) > 1:
        second = ranked[1]
        if second.value != top.value and (top.score - second.score) < CONFLICT_MARGIN:
            uncertain = True  # widerspruechliche Signale
    return Decision(
        value=top.value,
        is_uncertain=uncertain,
        provenance=top.provenance,
        score=round(top.score, 4),
        candidates=candidates,
    )


def fuse_row(
    *,
    composed: dict[str, Composed],
    bez1_context_value: str = "",
    bez1_context_kind: str = "",
    retrieval: dict[str, tuple[str, float]] | None = None,
    llm_fields: dict[str, str] | None = None,
    hint_fields: dict[str, str] | None = None,
    doc_untersuchung: str = "",
    ocr_score: float | None = None,
    threshold: float = 0.75,
    ocr_min_confidence: float = 0.55,
) -> dict[str, Decision]:
    retrieval = retrieval or {}
    llm_fields = llm_fields or {}
    hint_fields = hint_fields or {}
    ocr_weak = ocr_score is not None and ocr_score < ocr_min_confidence

    decisions: dict[str, Decision] = {}
    for name in FIELDS:
        cands: list[Candidate] = []
        comp = composed.get(name) or Composed()
        if comp.value:
            cands.append(
                Candidate(comp.value, comp.provenance, comp.score, comp.detail)
            )
        if name == "Bez1" and bez1_context_value and not comp.value:
            if bez1_context_kind == "structure":
                cands.append(
                    Candidate(
                        bez1_context_value,
                        Provenance.STRUCTURE.value,
                        SCORE_BEZ1_EXPLICIT,
                        "bez1:objektkontext",
                    )
                )
            elif bez1_context_kind == "title":
                cands.append(
                    Candidate(bez1_context_value, "title", SCORE_BEZ1_TITLE, "bez1:titel")
                )
        if name == "Untersuchungsart" and doc_untersuchung and not comp.value:
            cands.append(
                Candidate(
                    doc_untersuchung, "doc_context", SCORE_DOC_CONTEXT, "unt:dokumentkontext"
                )
            )
        hit = retrieval.get(name)
        if hit and hit[0]:
            cands.append(
                Candidate(
                    hit[0],
                    Provenance.RETRIEVAL.value,
                    round(hit[1] * SCORE_RETRIEVAL_FACTOR, 4),
                    f"retrieval:sim={hit[1]:.2f}",
                )
            )
        llm_val = llm_fields.get(name, "")
        if llm_val:
            cands.append(Candidate(llm_val, Provenance.LLM.value, SCORE_LLM, "llm"))
        hint_val = hint_fields.get(name, "")
        if hint_val:
            cands.append(Candidate(hint_val, Provenance.HINT.value, SCORE_HINT, "zusatztext"))
        decisions[name] = _decide(
            cands, threshold=threshold, ocr_weak=ocr_weak
        )
    return decisions
