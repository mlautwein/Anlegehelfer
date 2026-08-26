"""Tesseract-Adapter (Subprozess, TSV-Ausgabe fuer Konfidenzwerte)."""

from __future__ import annotations

import csv
import io
import shutil
import subprocess
import tempfile
from collections import defaultdict
from pathlib import Path

from lims_assistant.config import OcrConfig
from lims_assistant.ocr.base import OcrLine, OcrPageResult
from lims_assistant.ocr.preprocess import prepare


class TesseractEngine:
    name = "tesseract"

    def __init__(self, cfg: OcrConfig) -> None:
        self.cfg = cfg
        self._binary = shutil.which("tesseract")

    def available(self) -> tuple[bool, str]:
        if not self._binary:
            return False, "tesseract-Binary nicht gefunden"
        try:
            out = subprocess.run(
                [self._binary, "--list-langs"],
                capture_output=True,
                text=True,
                timeout=20,
            )
            langs = out.stdout + out.stderr
            if "deu" not in langs:
                return False, "deutsches Sprachpaket (deu) fehlt"
            return True, f"tesseract @ {self._binary} (deu)"
        except (OSError, subprocess.SubprocessError) as exc:
            return False, f"tesseract nicht aufrufbar: {exc}"

    def recognize(self, image) -> OcrPageResult:
        img = prepare(image)
        with tempfile.TemporaryDirectory(prefix="lims-ocr-") as td:
            png = Path(td) / "page.png"
            img.save(png, format="PNG")
            proc = subprocess.run(
                [
                    self._binary,
                    str(png),
                    "stdout",
                    "-l",
                    "deu",
                    "--psm",
                    "6",
                    "tsv",
                ],
                capture_output=True,
                text=True,
                timeout=300,
            )
        lines: dict[tuple[int, int, int], list[tuple[str, float, tuple]]] = defaultdict(list)
        reader = csv.DictReader(io.StringIO(proc.stdout), delimiter="\t")
        for rec in reader:
            try:
                level = int(rec.get("level", "0"))
                conf = float(rec.get("conf", "-1"))
            except ValueError:
                continue
            word = (rec.get("text") or "").strip()
            if level != 5 or not word or conf < 0:
                continue
            key = (
                int(rec.get("block_num", "0")),
                int(rec.get("par_num", "0")),
                int(rec.get("line_num", "0")),
            )
            bbox = (
                float(rec.get("left", "0")),
                float(rec.get("top", "0")),
                float(rec.get("left", "0")) + float(rec.get("width", "0")),
                float(rec.get("top", "0")) + float(rec.get("height", "0")),
            )
            lines[key].append((word, conf / 100.0, bbox))
        out_lines: list[OcrLine] = []
        for key in sorted(lines):
            words = lines[key]
            text = " ".join(w for w, _, _ in words)
            conf = sum(c for _, c, _ in words) / len(words)
            xs0 = min(b[0] for _, _, b in words)
            ys0 = min(b[1] for _, _, b in words)
            xs1 = max(b[2] for _, _, b in words)
            ys1 = max(b[3] for _, _, b in words)
            out_lines.append(OcrLine(text=text, confidence=conf, bbox=(xs0, ys0, xs1, ys1)))
        return OcrPageResult(lines=out_lines)
