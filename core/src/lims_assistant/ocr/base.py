"""OCR-Adapter: einheitliche Schnittstelle, austauschbare Engines.

Primaerpfad (portabel, Windows-onedir): RapidOCR (PaddleOCR-Modelle als ONNX,
CPU). Fallback (Entwicklung/optional): Tesseract mit deutschem Sprachpaket.
Kein Engine-Aufruf laedt jemals etwas aus dem Netz.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from lims_assistant.config import OcrConfig


@dataclass
class OcrLine:
    text: str
    confidence: float  # 0..1
    bbox: tuple[float, float, float, float] | None = None  # x0, y0, x1, y1


@dataclass
class OcrPageResult:
    lines: list[OcrLine]

    @property
    def mean_confidence(self) -> float:
        vals = [l.confidence for l in self.lines if l.text.strip()]
        return sum(vals) / len(vals) if vals else 0.0

    @property
    def text(self) -> str:
        return "\n".join(l.text for l in self.lines)


class OcrEngine(Protocol):
    name: str

    def available(self) -> tuple[bool, str]: ...

    def recognize(self, image) -> OcrPageResult:  # PIL.Image.Image
        ...


def get_engine(cfg: OcrConfig) -> "OcrEngine | None":
    """Waehlt die OCR-Engine gemaess Konfiguration ('auto' probiert beide)."""
    from lims_assistant.ocr.rapid_engine import RapidOcrEngine
    from lims_assistant.ocr.tesseract_engine import TesseractEngine

    if cfg.engine == "none":
        return None

    def _ohne_zusatzmodell() -> "RapidOcrEngine":
        """RapidOCR mit den gebuendelten Standardmodellen.

        Letzte Stufe der Kette: Zeigt `rec_model_path` auf eine Datei, die
        (noch) nicht provisioniert ist, wirft RapidOCR beim Laden. Ohne
        diesen Rueckfall bliebe gar keine Engine uebrig und Scans/Fotos
        wuerden kommentarlos keine Zeilen liefern - genau das passiert mit
        der ausgelieferten config.json vor dem Provisionieren.
        """
        from dataclasses import replace

        return RapidOcrEngine(
            replace(cfg, rec_model_path="", dict_path=""),
            note="konfiguriertes Zusatzmodell nicht ladbar, Standardmodelle aktiv",
        )

    candidates: list[OcrEngine]
    if cfg.engine == "rapidocr":
        candidates = [RapidOcrEngine(cfg)]
        if cfg.rec_model_path:
            candidates.append(_ohne_zusatzmodell())
    elif cfg.engine == "tesseract":
        candidates = [TesseractEngine(cfg)]
    else:
        # auto - Dev-Spike-Ergebnis (docs/benchmarks): Die gebuendelten
        # RapidOCR-Standardmodelle (ch/en) verlieren deutsche Umlaute
        # ("Teekuche", "GroSe"); Tesseract-deu erkennt sie fehlerfrei.
        # Reihenfolge daher: RapidOCR MIT provisioniertem Latin-Modell
        # (packaging/models/manifest.json) > Tesseract(deu) > RapidOCR-
        # Standard (Umlautreparatur uebernimmt dann das Fuzzy-Matching).
        if cfg.rec_model_path:
            candidates = [
                RapidOcrEngine(cfg),
                TesseractEngine(cfg),
                _ohne_zusatzmodell(),
            ]
        else:
            candidates = [TesseractEngine(cfg), RapidOcrEngine(cfg)]
    for engine in candidates:
        ok, _ = engine.available()
        if ok:
            return engine
    return None


def engine_health(cfg: OcrConfig) -> tuple[str, bool, str]:
    engine = get_engine(cfg)
    if engine is None:
        return ("none", False, "Keine OCR-Engine verfuegbar")
    ok, detail = engine.available()
    return (engine.name, ok, detail)
