"""Gemeinsame Strukturen aller Importadapter."""

from __future__ import annotations

from dataclasses import dataclass, field

from lims_assistant.segment.lines import SegmentResult


@dataclass
class IngestedDocument:
    doc_type: str            # pdf | image_set | excel
    filename: str            # nur Dateiname(n), keine Originalbytes
    sha256: str
    extracted_text: str      # vollstaendig extrahierter Text (persistierbar)
    segment: SegmentResult
    page_selection: str = ""
    sheet_selection: str = ""
    ocr_pages: int = 0
    warnings: list[str] = field(default_factory=list)


def stringify_cell(value) -> str:
    """Excel-/Tabellenwert deterministisch in Text wandeln (530.0 -> '530')."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "WAHR" if value else "FALSCH"
    if isinstance(value, float):
        if value.is_integer():
            return str(int(value))
        return repr(value)
    return str(value)
