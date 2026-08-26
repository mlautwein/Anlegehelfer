# Ausfuehrungsnotiz (Implementierungsstart 26.08.2026)

Grundlage: Spezifikation LIMS-PA-SPEC-001 v1.0 (Ordner "Anlegehilfe") und der
Implementierungsauftrag vom 26.08.2026. Dieses Dokument haelt die zu Beginn
getroffenen Umsetzungsentscheidungen und die Umgebungsbefunde fest.

## Umgebung

- Entwicklung in einer Cloud-Linux-Sandbox (Python 3.11, 2 vCPU, 7 GB RAM).
  Die Kern-Codebasis ist plattformneutral; die macOS-Gates sind identische
  Kommandos (`pip install -e ".[dev]"`, `pytest`) und laufen zusaetzlich im
  CI-Workflow auf `macos-latest`.
- PyPI erreichbar (Abhaengigkeiten real installiert und getestet).
- huggingface.co in der Sandbox gesperrt -> keine GGUF-Modelle ladbar.
  Konsequenz: LLM-Adapter, Schema-Zwang, Prompt-Haertung und Benchmark-
  Harness sind vollstaendig implementiert und mit Fake-Adapter getestet;
  der echte Modell-Benchmark ist ein dokumentierter Provisionierungsschritt
  (packaging/windows/provision_offline.ps1 + scripts/benchmark_llm.py).
- OCR real verfuegbar: RapidOCR (rapidocr-onnxruntime 1.4.x, gebuendelte
  PP-OCR-Modelle) und Tesseract 5 mit Sprachpaket `deu`.

## Bewusste technische Entscheidungen (mit Begruendung)

1. **PDF-Stack: pdfplumber (MIT) + pypdfium2 (Apache-2.0/BSD-3) statt
   PyMuPDF (AGPL-3.0).** Funktional gedeckt (Textschicht, Wortpositionen,
   Tabellenerkennung, Seitenrendering fuer OCR); vermeidet AGPL-Pflichten im
   verteilten Windows-Paket. Von der Spezifikation ausdruecklich als
   Alternative genannt.
2. **OCR-Engine-Reihenfolge (Spike-Ergebnis, siehe docs/benchmarks):**
   Die im RapidOCR-Wheel gebuendelten ch/en-Modelle verlieren deutsche
   Umlaute ("Teekuche", "GroSe"); Tesseract-deu erkennt sie fehlerfrei.
   `auto` waehlt daher: RapidOCR MIT provisioniertem Latin-Modell >
   Tesseract(deu) > RapidOCR-Standard (dann repariert Fuzzy-Matching
   bekannte Fachbegriffe, Ergebnis wird gelb markiert).
3. **OCR-Bildgroesse:** ~1900 px Kantenlaenge ist fuer die PP-OCR-
   Mobilmodelle optimal (vollstaendige Zeilen, saubere Worttrennung);
   groessere Renderings verschlechtern die Detektion. render_dpi=170.
4. **Kein Vektorspeicher, kein Fine-Tuning:** fallbasiertes Lernen als
   TF-IDF-Index (Wort-/Zeichen-n-Gramme) + Naive-Bayes-Zeilendetektor,
   beides bei jedem Prozessstart deterministisch aus den aktiven
   Lernbeispielen aufgebaut -> Reproduzierbarkeit konstruktiv erfuellt.
5. **Einspaltige Exportdateien ohne CSV-Quoting:** Kommas sind regulaerer
   Wertbestandteil ("5. OG, Zimmer 530, ..."); Quoting wuerde die
   LIMS-Uebernahme verfaelschen. Zeilenumbrueche/Tabs werden vorher
   deterministisch zu Leerzeichen normalisiert.
6. **Retrieval-Vorrang bei nahezu identischem Fall:** Ein vom Benutzer
   bereits korrigierter, praktisch identischer Fall (Aehnlichkeit >= 0,9)
   ueberstimmt den direkten Dokumentwert - bleibt aber gelb (A-03).

## Reihenfolge der Umsetzung

Vertraege/Domain -> Import (PDF/Scan/Bild/HEIC/Excel) + OCR + Segmentierung
-> Feldnormalisierung -> Lernkern/Fusion -> Jobprotokoll/Export/Lock/Sync ->
VBA-Textmodule + Workbook-Builder -> Korpus/Tests/Benchmarks -> Windows-
Build-Workflow -> Doku/Manifeste/Abnahme -> Abschlussbericht.
