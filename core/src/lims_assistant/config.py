"""Konfiguration des Rechenkerns.

Suchreihenfolge fuer config.json:
1. Umgebungsvariable LIMS_CONFIG (Datei)
2. Verzeichnis der EXE (portable Bereitstellung im gemeinsamen Ordner)
3. Datenverzeichnis (lokale Entwicklerkonfiguration)
Fehlende Datei => Standardwerte (vollstaendig offlinefaehig).
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

from lims_assistant import paths


@dataclass
class LlmConfig:
    enabled: bool = False
    # GGUF-Modellpfad; leer => LLM-Stufe wird uebersprungen.
    model_path: str = ""
    model_sha256: str = ""
    # llama.cpp llama-server Binary (portable, liegt im Paket).
    server_binary: str = ""
    port: int = 18081
    ctx_size: int = 4096
    threads: int = 0  # 0 = auto
    timeout_s: int = 120
    max_rows_per_call: int = 12


@dataclass
class OcrConfig:
    engine: str = "auto"  # auto | rapidocr | tesseract | none
    # Optionale Modellpfade fuer RapidOCR (deutsches/lateinisches Rec-Modell).
    rec_model_path: str = ""
    dict_path: str = ""
    render_dpi: int = 170  # A4 -> ~2000 px Kantenlaenge (OCR-Spike: optimal)
    min_confidence: float = 0.55


@dataclass
class Settings:
    share_dir: str = ""  # gemeinsamer Begleitordner (Snapshot + Lock); leer = rein lokal
    certainty_threshold: float = 0.75
    retrieval_min_similarity: float = 0.42
    retrieval_top_k: int = 5
    offline_strict: bool = True
    default_untersuchungsart: str = ""  # bewusst leer: nie unmarkiert raten
    export_encoding: str = "utf8_bom"  # utf8_bom | cp1252
    stale_lock_minutes: int = 12
    llm: LlmConfig = field(default_factory=LlmConfig)
    ocr: OcrConfig = field(default_factory=OcrConfig)

    @property
    def data_dir(self) -> Path:
        return paths.data_root()


def _exe_dir() -> Path:
    if getattr(sys, "frozen", False):  # PyInstaller
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def _candidates() -> list[Path]:
    out: list[Path] = []
    env = os.environ.get("LIMS_CONFIG")
    if env:
        out.append(Path(env))
    out.append(_exe_dir() / "config.json")
    out.append(paths.data_root() / "config.json")
    return out


def _apply(obj: dict, target) -> None:
    for key, value in obj.items():
        if not hasattr(target, key):
            continue
        current = getattr(target, key)
        if isinstance(current, (LlmConfig, OcrConfig)) and isinstance(value, dict):
            _apply(value, current)
        elif isinstance(value, type(current)) or current is None or isinstance(current, (int, float, bool, str)):
            setattr(target, key, value)


def load_settings(path: str | os.PathLike | None = None) -> Settings:
    settings = Settings()
    chosen: Path | None = Path(path) if path else None
    if chosen is None:
        for cand in _candidates():
            if cand.is_file():
                chosen = cand
                break
    if chosen and chosen.is_file():
        try:
            data = json.loads(chosen.read_text(encoding="utf-8-sig"))
            if isinstance(data, dict):
                _apply(data, settings)
        except (OSError, json.JSONDecodeError):
            # Defekte Konfiguration darf den Kern nicht verhindern; Defaults gelten.
            pass
    return settings
