# Lizenzen und Drittanbieter-Manifest

Eigener Code: proprietaer, interne Nutzung (siehe `LICENSE`). Reale
Dokumente, extrahierte Texte, Lerndaten, Modelle und Geheimnisse werden
niemals eingecheckt.

## Python-Laufzeitabhaengigkeiten (in der EXE verteilt)

| Paket | Zweck | Lizenz |
|---|---|---|
| pydantic (>=2.7) | Vertraege/Validierung | MIT |
| pdfplumber (>=0.11) | PDF-Textschicht, Tabellen | MIT |
| pdfminer.six (via pdfplumber) | PDF-Parsing | MIT |
| pypdfium2 (>=4.30) | PDF-Rendering fuer OCR | Apache-2.0 / BSD-3 (PDFium) |
| openpyxl (>=3.1) | XLSX/XLSM lesen (ohne Makroausfuehrung) | MIT |
| xlrd (>=2.0.1) | XLS-Altformat lesen | BSD |
| Pillow (>=10.3) | Bilddekodierung/-vorverarbeitung | MIT-CMU (HPND) |
| pillow-heif (>=0.16) | HEIC-Dekodierung (libheif) | Apache-2.0 (bindet LGPL-Komponenten dynamisch: libheif/libde265) |
| rapidocr-onnxruntime (>=1.3.24, optional) | OCR (PaddleOCR-ONNX) | Apache-2.0 |
| onnxruntime (via rapidocr) | CPU-Inferenz | MIT |
| numpy (via rapidocr) | Arrays | BSD-3 |
| opencv-python (via rapidocr) | Bildoperationen der OCR | Apache-2.0 |

Bewusste Abweichung: PyMuPDF (AGPL-3.0) wird NICHT verwendet, damit das
verteilte Paket frei von AGPL-Pflichten bleibt (`docs/AUSFUEHRUNGSNOTIZ.md`).

## Externe Artefakte (provisioniert, nie im Repository)

| Artefakt | Lizenz | Hash-Pflege |
|---|---|---|
| PP-OCR-Modelle (ch/en, im RapidOCR-Wheel) | Apache-2.0 | im Wheel enthalten |
| PP-OCR latin Rec-Modell + Woerterbuch | Apache-2.0 | `packaging/models/manifest.json` |
| Tesseract 5 + deu-Sprachdaten (optionaler Fallback) | Apache-2.0 | `packaging/models/manifest.json` |
| llama.cpp `llama-server` (gepinntes Release) | MIT | `packaging/models/manifest.json` |
| Qwen3-4B-Instruct-2507 GGUF | Apache-2.0 | `packaging/models/manifest.json` |
| Phi-4 Mini / Phi-3 Mini GGUF | MIT | `packaging/models/manifest.json` |
| Gemma 3 4B GGUF | Gemma Terms of Use (vor Einsatz pruefen!) | `packaging/models/manifest.json` |

## Entwicklungs-/Testabhaengigkeiten (nicht verteilt)

| Paket | Zweck | Lizenz |
|---|---|---|
| pytest | Tests | MIT |
| reportlab | synthetische PDF-Fixtures | BSD-3 |
| xlwt | synthetische XLS-Fixtures | BSD |
| psutil | Benchmark-Hilfen | BSD-3 |
| PyInstaller | Windows-Paketierung (Build-Rechner) | GPL-2.0 mit Bootloader-Ausnahme (erzeugte Programme unterliegen NICHT der GPL) |

Versionen werden ueber `pyproject.toml` gepinnt; der Windows-Build friert
die exakten Staende in der Build-venv ein und `hashes.json` manifestiert
jede verteilte Datei mit SHA-256.
