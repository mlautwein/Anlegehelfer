"""Zeilensegmentierung und Objektkontext ueber alle Quelltypen.

Alle Quellen (PDF-Text, OCR, Excel) muenden in dieselbe Struktur
`SegmentedRow`; Objekt-/Gebaeudekontext wird zeilenbezogen mitgefuehrt
(mehrere Objekte je Dokument, Kontext ueberdauert Seitenwechsel).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from lims_assistant.extract import vocab
from lims_assistant.extract.features import CellMap, RowFeatures, extract_features
from lims_assistant.extract.patterns import looks_like_metadata, scan_objekt_header
from lims_assistant.textutil import fold_for_match, sanitize_lims_value

# Herkunftsgueten fuer Bez1-Kontext
BEZ1_EXPLICIT = "structure"  # 'Objekt: X' / Objektspalte
BEZ1_TITLE = "title"         # Dokument-/Blatttitel (immer unsicher)
BEZ1_NONE = ""


@dataclass
class Bez1Context:
    value: str = ""
    kind: str = BEZ1_NONE


@dataclass
class DocContext:
    """Dokumentweiter Kontext (Titelzeile, Untersuchungsart aus Kopfbereich)."""

    title: str = ""
    untersuchung: str = ""


@dataclass
class SegmentedRow:
    source_text: str
    page_or_sheet: str
    frag_order: int
    cells: CellMap | None = None
    structural: bool = False           # aus erkannter Tabelle mit Kopfzeile
    ocr_score: float | None = None
    bez1_context: Bez1Context = field(default_factory=Bez1Context)
    features: RowFeatures | None = None


@dataclass
class RejectedLine:
    """Nicht als Probenstelle uebernommene Zeile (fuer Detektor-Merkmale)."""

    source_text: str
    page_or_sheet: str
    frag_order: int


@dataclass
class SegmentResult:
    rows: list[SegmentedRow] = field(default_factory=list)
    rejected: list[RejectedLine] = field(default_factory=list)
    doc_context: DocContext = field(default_factory=DocContext)


MIN_SIGNALS_TEXTLINE = 3


def _doc_untersuchung(text: str) -> str:
    return vocab.match_vocab(fold_for_match(text), vocab.UNTERSUCHUNG_MAP) or ""


class LineSegmenter:
    """Verarbeitet Fragmente in Quellreihenfolge und fuehrt Kontext mit."""

    def __init__(self, row_probability=None) -> None:
        # row_probability: optionaler Callable(text) -> float | None (Zeilendetektor)
        self.row_probability = row_probability
        self.context = Bez1Context()
        self.result = SegmentResult()
        self._order = 0
        self._title_seen = False

    def _next_order(self) -> int:
        self._order += 1
        return self._order

    def push_context_candidate(self, line: str, page_or_sheet: str) -> bool:
        """Prueft eine Zeile auf Objektueberschrift; aktualisiert Kontext."""
        explicit = scan_objekt_header(line)
        if explicit:
            self.context = Bez1Context(value=explicit, kind=BEZ1_EXPLICIT)
            return True
        return False

    def push_title_candidate(self, line: str) -> None:
        """Erste inhaltliche Nicht-Probenzeile als Dokumenttitel vormerken."""
        clean = sanitize_lims_value(line)
        if not clean or self._title_seen:
            return
        if looks_like_metadata(clean):
            return
        f = extract_features(clean, allow_fuzzy=False)
        if f.signal_count() >= MIN_SIGNALS_TEXTLINE:
            return
        if len(clean) < 3 or len(clean) > 90:
            return
        self._title_seen = True
        self.result.doc_context.title = clean
        if not self.context.value:
            self.context = Bez1Context(value=clean, kind=BEZ1_TITLE)
        unt = _doc_untersuchung(clean)
        if unt and not self.result.doc_context.untersuchung:
            self.result.doc_context.untersuchung = unt

    def push_text_line(
        self, line: str, page_or_sheet: str, *, ocr_score: float | None = None
    ) -> None:
        clean = sanitize_lims_value(line)
        if not clean:
            return
        order = self._next_order()
        if self.push_context_candidate(clean, page_or_sheet):
            return
        if looks_like_metadata(clean):
            unt = _doc_untersuchung(clean)
            if unt and not self.result.doc_context.untersuchung:
                self.result.doc_context.untersuchung = unt
            self.result.rejected.append(RejectedLine(clean, page_or_sheet, order))
            return
        features = extract_features(clean)
        signals = features.signal_count()
        accept = signals >= MIN_SIGNALS_TEXTLINE
        if not accept and signals >= 1 and self.row_probability is not None:
            p = self.row_probability(clean)
            if p is not None and p >= 0.6:
                accept = True
        if not accept and signals >= 1 and self.row_probability is not None:
            p = self.row_probability(clean)
            if p is not None and p <= 0.25:
                accept = False
        if accept and self.row_probability is not None:
            # Negativlernen: sehr sichere Negative unterdruecken auch 3+-Signale nicht
            # (False Negatives vermeiden) - Detektor senkt nur die Schwelle.
            pass
        if accept:
            self.result.rows.append(
                SegmentedRow(
                    source_text=clean,
                    page_or_sheet=page_or_sheet,
                    frag_order=order,
                    cells=None,
                    structural=False,
                    ocr_score=ocr_score,
                    bez1_context=Bez1Context(self.context.value, self.context.kind),
                    features=features,
                )
            )
        else:
            self.push_title_candidate(clean)
            unt = _doc_untersuchung(clean)
            if unt and not self.result.doc_context.untersuchung:
                self.result.doc_context.untersuchung = unt
            self.result.rejected.append(RejectedLine(clean, page_or_sheet, order))

    def push_table_row(
        self,
        cells: CellMap,
        text: str,
        page_or_sheet: str,
        *,
        ocr_score: float | None = None,
    ) -> None:
        order = self._next_order()
        if cells.bez1:
            # Objektspalte gefunden: zeilenbezogener expliziter Kontext.
            self.context = Bez1Context(value=cells.bez1, kind=BEZ1_EXPLICIT)
        features = extract_features(text, cells)
        self.result.rows.append(
            SegmentedRow(
                source_text=text,
                page_or_sheet=page_or_sheet,
                frag_order=order,
                cells=cells,
                structural=True,
                ocr_score=ocr_score,
                bez1_context=Bez1Context(self.context.value, self.context.kind),
                features=features,
            )
        )
