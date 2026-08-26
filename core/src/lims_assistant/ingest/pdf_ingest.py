"""PDF-Import: Textschicht + Tabellen via pdfplumber, Scans via pypdfium2 + OCR.

Lizenzhinweis (bewusste Abweichung von der PyMuPDF-Empfehlung): pdfplumber
(MIT) + pypdfium2 (Apache-2.0/BSD-3) statt PyMuPDF (AGPL-3.0), damit das
verteilte Windows-Paket ohne AGPL-Verpflichtungen bleibt. Funktional gedeckt:
Textschicht, Wort-/Zeilenpositionen, Tabellenerkennung, Seitenrendering.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

import pdfplumber

from lims_assistant.config import Settings
from lims_assistant.ingest.base import IngestedDocument, stringify_cell
from lims_assistant.ocr.base import OcrEngine
from lims_assistant.segment.lines import LineSegmenter
from lims_assistant.segment.tables import (
    HeaderMap,
    data_signal,
    detect_header,
    find_header_row,
    is_repeated_header,
    row_text,
    row_to_cells,
)
from lims_assistant.textutil import sanitize_lims_value, sha256_file

MIN_TEXT_CHARS_PER_PAGE = 32


def _page_lines_outside(page, exclude_bboxes: list[tuple]) -> list[str]:
    """Textzeilen ausserhalb der Tabellenbereiche (aus Wortpositionen)."""

    def inside(word) -> bool:
        cx = (float(word["x0"]) + float(word["x1"])) / 2
        cy = (float(word["top"]) + float(word["bottom"])) / 2
        for (x0, top, x1, bottom) in exclude_bboxes:
            if x0 - 1 <= cx <= x1 + 1 and top - 1 <= cy <= bottom + 1:
                return True
        return False

    words = page.extract_words(use_text_flow=False, keep_blank_chars=False)
    rows: dict[int, list] = defaultdict(list)
    for w in words:
        if inside(w):
            continue
        key = int(round(float(w["top"]) / 3.0))
        rows[key].append(w)
    lines: list[str] = []
    for key in sorted(rows):
        ws = sorted(rows[key], key=lambda w: float(w["x0"]))
        lines.append(" ".join(w["text"] for w in ws))
    return lines


def _render_page_image(pdf_path: Path, page_index: int, dpi: int):
    import pypdfium2 as pdfium

    doc = pdfium.PdfDocument(str(pdf_path))
    try:
        page = doc[page_index]
        try:
            bitmap = page.render(scale=dpi / 72.0)
            return bitmap.to_pil()
        finally:
            page.close()
    finally:
        doc.close()


def ingest_pdf(
    path: str | Path,
    *,
    settings: Settings,
    ocr_engine: OcrEngine | None,
    pages: list[int] | None = None,
    row_probability=None,
) -> IngestedDocument:
    pdf_path = Path(path)
    warnings: list[str] = []
    segmenter = LineSegmenter(row_probability=row_probability)
    all_text: list[str] = []
    ocr_pages = 0
    last_header: HeaderMap | None = None
    last_header_cols = 0

    with pdfplumber.open(str(pdf_path)) as pdf:
        total = len(pdf.pages)
        selected = pages or list(range(1, total + 1))
        selected = [p for p in selected if 1 <= p <= total]
        for pno in selected:
            page = pdf.pages[pno - 1]
            page_label = f"Seite {pno}"
            text = page.extract_text() or ""
            has_text_layer = len(sanitize_lims_value(text)) >= MIN_TEXT_CHARS_PER_PAGE

            if has_text_layer:
                tables = page.find_tables()
                table_bboxes = [t.bbox for t in tables]
                # Kopf-/Freitextzeilen zuerst (stehen oberhalb der Tabelle)
                for line in _page_lines_outside(page, table_bboxes):
                    all_text.append(line)
                    segmenter.push_text_line(line, page_label)
                for table in tables:
                    matrix = [
                        [stringify_cell(c) for c in row] for row in table.extract()
                    ]
                    if not matrix:
                        continue
                    header_hit = find_header_row(matrix)
                    start = 0
                    header: HeaderMap | None = None
                    if header_hit is not None:
                        start = header_hit[0] + 1
                        header = header_hit[1]
                        last_header = header
                        last_header_cols = len(matrix[header_hit[0]])
                        all_text.append(row_text(matrix[header_hit[0]]))
                    elif (
                        last_header is not None
                        and matrix
                        and len(matrix[0]) == last_header_cols
                    ):
                        header = last_header  # Folgeseite ohne wiederholten Kopf
                    for raw_row in matrix[start:]:
                        text_row = row_text(raw_row)
                        if not text_row:
                            continue
                        all_text.append(text_row)
                        if header is not None:
                            if is_repeated_header(raw_row, header):
                                continue
                            cells = row_to_cells(raw_row, header)
                            if not data_signal(cells):
                                segmenter.push_text_line(text_row, page_label)
                                continue
                            segmenter.push_table_row(cells, text_row, page_label)
                        else:
                            segmenter.push_text_line(text_row, page_label)
            else:
                # Bildseite -> OCR
                if ocr_engine is None:
                    warnings.append(
                        f"{page_label}: keine Textschicht und keine OCR-Engine verfuegbar"
                    )
                    continue
                try:
                    image = _render_page_image(pdf_path, pno - 1, settings.ocr.render_dpi)
                except Exception as exc:  # noqa: BLE001
                    warnings.append(f"{page_label}: Rendern fehlgeschlagen ({exc})")
                    continue
                result = ocr_engine.recognize(image)
                ocr_pages += 1
                if not result.lines:
                    warnings.append(f"{page_label}: OCR ohne Ergebnis")
                for line in result.lines:
                    all_text.append(line.text)
                    segmenter.push_text_line(
                        line.text, page_label, ocr_score=line.confidence
                    )

    return IngestedDocument(
        doc_type="pdf",
        filename=pdf_path.name,
        sha256=sha256_file(pdf_path),
        extracted_text="\n".join(all_text),
        segment=segmenter.result,
        page_selection=",".join(str(p) for p in (pages or [])),
        ocr_pages=ocr_pages,
        warnings=warnings,
    )
