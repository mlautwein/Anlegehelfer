"""Bildimport: JPG/JPEG, PNG und HEIC; mehrere Bilder = ein Import."""

from __future__ import annotations

import hashlib
from pathlib import Path

from PIL import Image

from lims_assistant.config import Settings
from lims_assistant.ingest.base import IngestedDocument
from lims_assistant.ocr.base import OcrEngine
from lims_assistant.segment.lines import LineSegmenter
from lims_assistant.textutil import sha256_file

_HEIF_REGISTERED = False


def _ensure_heif() -> None:
    global _HEIF_REGISTERED
    if _HEIF_REGISTERED:
        return
    try:
        from pillow_heif import register_heif_opener

        register_heif_opener()
    except Exception:  # noqa: BLE001 - HEIC dann nicht unterstuetzt
        pass
    _HEIF_REGISTERED = True


def ingest_image_set(
    paths: list[str | Path],
    *,
    settings: Settings,
    ocr_engine: OcrEngine | None,
    row_probability=None,
) -> IngestedDocument:
    _ensure_heif()
    warnings: list[str] = []
    segmenter = LineSegmenter(row_probability=row_probability)
    all_text: list[str] = []
    combined_hash = hashlib.sha256()
    names: list[str] = []
    ocr_pages = 0

    for idx, p in enumerate(paths, start=1):
        img_path = Path(p)
        names.append(img_path.name)
        combined_hash.update(sha256_file(img_path).encode("ascii"))
        label = f"Bild {idx} ({img_path.name})"
        if ocr_engine is None:
            warnings.append(f"{label}: keine OCR-Engine verfuegbar")
            continue
        try:
            with Image.open(img_path) as im:
                im.load()
                result = ocr_engine.recognize(im)
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"{label}: Bild nicht lesbar ({exc})")
            continue
        ocr_pages += 1
        if not result.lines:
            warnings.append(f"{label}: OCR ohne Ergebnis")
        for line in result.lines:
            all_text.append(line.text)
            segmenter.push_text_line(line.text, label, ocr_score=line.confidence)

    return IngestedDocument(
        doc_type="image_set",
        filename="; ".join(names),
        sha256=combined_hash.hexdigest(),
        extracted_text="\n".join(all_text),
        segment=segmenter.result,
        ocr_pages=ocr_pages,
        warnings=warnings,
    )
