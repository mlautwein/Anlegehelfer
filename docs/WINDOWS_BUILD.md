# Windows-Build und Bereitstellung

Zielumgebung produktiv: Windows 11 x64, Excel 2016 x64, 16 GB RAM,
CPU-only, ohne Adminrechte, ohne Python-Installation auf den Zielrechnern,
vollstaendig offline zur Laufzeit.

## 1. Core-EXE bauen (Build-Rechner mit Internet)

    powershell -ExecutionPolicy Bypass -File packaging\windows\build.ps1

Das Skript erzeugt eine Build-venv, installiert die gepinnten
Abhaengigkeiten inkl. RapidOCR, fuehrt die komplette Testsuite auf Windows
aus, baut mit PyInstaller das onedir-Paket `dist\lims_core\`, fuehrt einen
`health`-Smoke-Test aus und schreibt `hashes.json` (SHA-256 aller
Paketdateien) fuer die Startpruefung.

`onedir` ist bewusst gewaehlt: Modelle und OCR-Dateien liegen ohnehin als
Begleitartefakte daneben; `onefile` wuerde bei grossen Artefakten nur
Start- und Temporaerprobleme erzeugen.

Alternativ baut der GitHub-Actions-Workflow (`.github/workflows/ci.yml`,
Job `build-windows`) dasselbe Artefakt reproduzierbar auf `windows-latest`
inklusive Analyse-Smoke-Test ueber das echte Jobprotokoll und laedt es als
CI-Artefakt hoch.

## 2. Offline-Artefakte provisionieren (einmalig, mit Internet)

    # OCR-Latin-Modell (deutsche Umlaute) fuer RapidOCR:
    powershell -File packaging\windows\provision_offline.ps1 -Step ocr `
        -OcrRecUrl "<latin_PP-OCRv3_rec_infer.onnx-URL>" -OcrDictUrl "<latin_dict.txt-URL>"

    # llama.cpp-Server (Release pinnen!):
    powershell -File packaging\windows\provision_offline.ps1 -Step llama `
        -LlamaUrl "https://github.com/ggml-org/llama.cpp/releases/download/<b-Nr>/llama-<b-Nr>-bin-win-avx2-x64.zip"

    # LLM-Kandidaten fuer den Benchmark (Qwen3-4B zuerst):
    powershell -File packaging\windows\provision_offline.ps1 -Step model -ModelUrl "<GGUF-URL>"

Alle SHA-256-Werte in `packaging/models/manifest.json` eintragen
(Felder `BEIM_PROVISIONIEREN_EINTRAGEN`). Zur Laufzeit findet kein
Download statt; `lims_core.exe health` prueft Modellpfad und -hash.

## 3. Arbeitsmappe bauen

Siehe `docs/EXCEL_SETUP.md` (automatisch per `build_workbook.ps1` oder
manuell in ca. 5 Minuten).

## 4. Gemeinsamen Ordner bestuecken

Struktur und `config.json`: siehe `docs/EXCEL_SETUP.md`. Danach auf einem
Zielrechner die Abnahme nach `docs/ABNAHME_EXCEL2016.md` durchfuehren.

## 4b. Was ueber GitHub Actions testbar ist - und was nicht

Das Repository ist gepusht (`mlautwein/Anlegehelfer`, oeffentlich), die CI
laeuft und hat damit einen grossen Teil der Gates bereits geschlossen -
Stand v0.1.0 sind alle drei Jobs gruen:

- `test` (ubuntu + macos): komplette Kern-Testsuite inkl. OCR und VBA-Lint.
- `build-windows`: komplette Testsuite AUF WINDOWS, PyInstaller-onedir-Build,
  `health`- und Analyze-Smoke ueber das echte Jobprotokoll, fertiges
  EXE-Paket als herunterladbares Artefakt (`lims_core-windows-x64`) - dieses
  Artefakt kann direkt als `core\` in den gemeinsamen Ordner uebernommen
  werden.
- `LLM-Benchmark (manuell)` (`benchmark-llm.yml`, per Knopfdruck je
  Kandidat): laedt llama.cpp + GGUF auf den Runner, misst Schema-Validitaet,
  Feldtreffer, Injektionsresistenz und legt den Bericht als Artefakt ab.
  Qualitaetsmetriken sind uebertragbar; Laufzeit/RAM des Runners sind nur
  indikativ.

NICHT ueber GitHub testbar (bleibt manuell):

- Excel-2016-x64-Abnahme: GitHub-Runner haben kein Microsoft Office
  (Lizenz/Installation), und die VBA-Oberflaeche (Buttons, Strg+C,
  Zwischenablage, OnTime, Dialoge) ist interaktiv - `docs/ABNAHME_EXCEL2016.md`
  auf einem echten Ziel-PC. (Perspektivisch waere ein self-hosted Runner mit
  Excel fuer Teilautomatisierung denkbar - V3-Thema.)
- Die 2-Minuten-/16-GB-Messung auf der realen Zielhardware (Abschnitt F).
- Alles mit echten Dokumenten: reale Arbeitslisten duerfen das Haus nicht
  verlassen und werden niemals gepusht oder in CI verarbeitet.

Hinweis zu Kosten: Fuer **oeffentliche** Repositories sind Actions-Minuten
kostenfrei - im aktuellen Zustand entstehen also keine Kosten. Wird das
Repository auf privat umgestellt, zaehlen Windows-Minuten doppelt und
macOS-Minuten zehnfach auf das Kontingent; der macOS-Job kann dann bei
Bedarf auf `workflow_dispatch` umgestellt werden.

## 5. Modell-Benchmark (Gate vor LLM-Aktivierung)

    python scripts\benchmark_llm.py --model dist\lims_core\models\llm\<kandidat>.gguf `
        --server dist\lims_core\llm\llama-server.exe --name <kandidat-id> `
        --out docs/benchmarks/llm-<kandidat-id>.md

Alle vier Familien (Qwen3-4B-Instruct-2507 Q4_K_M als Referenz, Phi-4 Mini,
Phi-3 Mini als Legacy-Baseline, kleines Gemma) mit identischem Korpus
messen, Ergebnis in `docs/MODELLVERGLEICH.md` eintragen und erst dann
`llm.enabled=true` setzen. Groessere/neuere Modelle sind zulaessig, wenn
der Benchmark besser ausfaellt - Laufzeit, Modell-ID, Hash, Lizenz und
Quantisierung dokumentieren.

## Statusstand

Der Windows-Build und die Excel-2016-Abnahme sind als separate Gates
dokumentiert und standen zum Zeitpunkt der MVP-Fertigstellung in der
Entwicklungsumgebung (Linux/macOS-CI) noch aus - siehe
`docs/ABSCHLUSSBERICHT.md`.
