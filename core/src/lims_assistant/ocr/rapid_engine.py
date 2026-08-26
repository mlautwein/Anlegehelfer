"""RapidOCR-Adapter (PaddleOCR-Modelle, ONNX-Runtime, CPU, offline).

rapidocr-onnxruntime 1.x buendelt die Erkennungsmodelle im Paket - kein
Laufzeit-Download. Fuer bestmoegliche deutsche Umlauterkennung kann per
Konfiguration ein lateinisches Rec-Modell (PP-OCR latin) samt Woerterbuch
eingebunden werden (packaging/models/manifest.json, Provisionierung vorab).
"""

from __future__ import annotations

from lims_assistant.config import OcrConfig
from lims_assistant.ocr.base import OcrLine, OcrPageResult
from lims_assistant.ocr.preprocess import prepare


class RapidOcrEngine:
    name = "rapidocr"

    def __init__(self, cfg: OcrConfig) -> None:
        self.cfg = cfg
        self._ocr = None
        self._err = ""

    def _ensure(self) -> bool:
        if self._ocr is not None:
            return True
        try:
            from rapidocr_onnxruntime import RapidOCR  # type: ignore

            kwargs = {}
            if self.cfg.rec_model_path:
                kwargs["rec_model_path"] = self.cfg.rec_model_path
            if self.cfg.dict_path:
                kwargs["rec_keys_path"] = self.cfg.dict_path
            self._ocr = RapidOCR(**kwargs)
            return True
        except Exception as exc:  # noqa: BLE001 - Verfuegbarkeitspruefung
            self._err = f"rapidocr nicht verfuegbar: {exc}"
            return False

    def available(self) -> tuple[bool, str]:
        if self._ensure():
            extra = " (latin-Modell)" if self.cfg.rec_model_path else " (Standardmodelle)"
            return True, "rapidocr-onnxruntime" + extra
        return False, self._err

    def recognize(self, image) -> OcrPageResult:
        if not self._ensure():
            return OcrPageResult(lines=[])
        import numpy as np

        img = prepare(image).convert("RGB")
        arr = np.asarray(img)
        result, _ = self._ocr(arr)
        lines: list[OcrLine] = []
        if result:
            for item in result:
                # item: [box(4x2), text, score]
                box, text, score = item[0], str(item[1]), float(item[2])
                xs = [p[0] for p in box]
                ys = [p[1] for p in box]
                lines.append(
                    OcrLine(
                        text=text,
                        confidence=score,
                        bbox=(min(xs), min(ys), max(xs), max(ys)),
                    )
                )
        # RapidOCR liefert Boxen; in Leserichtung sortieren (oben->unten, links->rechts)
        lines.sort(key=lambda l: (round((l.bbox[1] if l.bbox else 0) / 12), l.bbox[0] if l.bbox else 0))
        merged = _merge_same_line(lines)
        return OcrPageResult(lines=merged)


def _merge_same_line(lines: list[OcrLine], y_tol: float = 14.0) -> list[OcrLine]:
    """Fasst Boxen gleicher Zeile zu einer Textzeile zusammen."""
    out: list[OcrLine] = []
    current: list[OcrLine] = []

    def flush() -> None:
        if not current:
            return
        current.sort(key=lambda l: l.bbox[0] if l.bbox else 0)
        text = " ".join(l.text for l in current)
        conf = sum(l.confidence for l in current) / len(current)
        xs0 = min(l.bbox[0] for l in current if l.bbox)
        ys0 = min(l.bbox[1] for l in current if l.bbox)
        xs1 = max(l.bbox[2] for l in current if l.bbox)
        ys1 = max(l.bbox[3] for l in current if l.bbox)
        out.append(OcrLine(text=text, confidence=conf, bbox=(xs0, ys0, xs1, ys1)))
        current.clear()

    last_y: float | None = None
    for line in lines:
        y = (line.bbox[1] + line.bbox[3]) / 2 if line.bbox else 0.0
        if last_y is None or abs(y - last_y) <= y_tol:
            current.append(line)
        else:
            flush()
            current.append(line)
        last_y = y
    flush()
    return out
