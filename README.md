# LIMS-Probenassistent

Lokaler, vollstaendig offline arbeitender Assistent zur Aufbereitung von
Trinkwasser-Arbeitslisten. Das Werkzeug liest PDF-Dokumente (mit Textschicht
oder gescannt), Fotos/Bilder (JPG, PNG, HEIC) und Excel-Dateien (XLSX, XLS,
XLSM) ein und erzeugt fuenf frei editierbare Textspalten - `Bez1`, `Bez2`,
`B3`, `B4`, `Untersuchungsart` - fuer die Uebernahme per Copy-and-paste in das
bestehende LIMS.

**Produktrolle:** Reines Komfortwerkzeug. Der verbindliche Datensatz entsteht
erst durch die kontrollierte Uebernahme in das LIMS. Es gibt bewusst keinen
Freigabe-/Signaturworkflow und keine ISO/IEC-17025-Konformitaetsbehauptung.

## Aufbau

    excel/vba-src/          VBA-Quellmodule (Text; XLSM ist Buildartefakt)
    core/src/lims_assistant Portabler Offline-Rechenkern (Python)
    core/tests/             Automatisierte Tests (Unit/Contract/Parser/ML/E2E)
    contracts/schemas/      Versionierte JSON-Schemas der Jobvertraege
    fixtures/synthetic/     Synthetischer deutscher Referenzkorpus + Gold
    packaging/windows/      Windows-x64-Build (PyInstaller onedir, PowerShell)
    packaging/models/       Manifest fuer OCR-/LLM-Artefakte (nie im Repo!)
    scripts/                Fixtures, Lint, Benchmarks, Provisionierung
    docs/                   Architektur, Bedienung, Abnahme, Lizenzen

Excel/VBA ist ausschliesslich Oberflaeche, Tabellenadapter, Clipboard-/CSV-
Bedienung und Prozessstarter. Die portable EXE (`lims_core.exe`) erledigt
Import, Textextraktion, OCR, Strukturierung, fallbasiertes Lernen,
Confidence-Fusion und den atomaren Fuenffach-CSV-Export. Kommunikation laeuft
ueber versionierte JSON-Jobdateien (`contracts/schemas/`).

## Schnellstart Entwicklung (macOS/Linux)

    python3 -m venv .venv && source .venv/bin/activate
    pip install -e ".[dev]"          # Kern + Testwerkzeuge
    pip install -e ".[ocr]"          # optional: RapidOCR (ONNX)
    python scripts/make_fixtures.py  # synthetischen Korpus erzeugen
    pytest                           # komplette Testsuite
    python scripts/benchmark_pipeline.py --runs 3

Fuer die Dev-OCR mit korrekten deutschen Umlauten: `tesseract` mit Sprachpaket
`deu` installieren (macOS: `brew install tesseract tesseract-lang`).

## Windows-Bereitstellung (Kurzfassung)

1. `packaging/windows/build.ps1` auf einem Windows-11-x64-Rechner ausfuehren
   -> `dist/lims_core/` (portable onedir-EXE inkl. Hash-Manifest).
2. `packaging/windows/build_workbook.ps1` erzeugt die zentrale XLSM aus den
   Text-VBA-Modulen (benoetigt einmalig "Zugriff auf das VBA-Projektobjekt-
   modell vertrauen"; manuelle Alternative: `docs/EXCEL_SETUP.md`).
3. `packaging/windows/provision_offline.ps1` laedt OCR-Latin-Modell und
   LLM-Artefakte VOR der Offline-Bereitstellung (SHA-256 in
   `packaging/models/manifest.json` eintragen).
4. Gemeinsamen Ordner bestuecken: `LIMS-Probenassistent.xlsm`, `config.json`,
   `core\` (EXE-Ordner). Details: `docs/WINDOWS_BUILD.md`.
5. Abnahme auf Windows 11 x64 + Excel 2016 x64: `docs/ABNAHME_EXCEL2016.md`.

## Wichtige Grundsaetze

- Vollstaendig lokal/offline; ein Offline-Waechter blockiert zur Laufzeit
  jeden Netzwerkzugriff ausser Loopback (llama.cpp-Server).
- Originaldokumente werden niemals dauerhaft kopiert; extrahierter Text und
  Lernereignisse bleiben bis zur manuellen Loeschung in der lokalen SQLite.
- SQLite laeuft nie direkt auf der Netzwerkfreigabe: exklusiver Lock,
  lokaler Arbeitscache, atomare Snapshots mit Hash und Backups.
- Unsichere oder abgeleitete Werte werden ausschliesslich gelb markiert;
  Kopieren/Export bestaetigt exakt den kopierten Umfang als Lernsignal.
- Reale Dokumente, extrahierte Texte, Lerndaten, Modelle und Geheimnisse
  gehoeren niemals in dieses Repository (.gitignore erzwingt das Grobe).

## Dokumentation

| Thema | Datei |
|---|---|
| Ausfuehrungsnotiz/Ist-Stand | `docs/AUSFUEHRUNGSNOTIZ.md` |
| Architektur | `docs/ARCHITEKTUR.md` |
| Bedienung (Anwender) | `docs/BEDIENUNG.md` |
| Excel-Setup/Workbook-Build | `docs/EXCEL_SETUP.md` |
| Windows-Build & Bereitstellung | `docs/WINDOWS_BUILD.md` |
| Manuelle Excel-2016-Abnahme | `docs/ABNAHME_EXCEL2016.md` |
| Modellvergleich (Gate) | `docs/MODELLVERGLEICH.md` |
| Sicherheit & Datenschutz | `docs/SICHERHEIT_DATENSCHUTZ.md` |
| Lizenzen/Drittanbieter | `docs/LIZENZEN.md` |
| Abschlussbericht MVP | `docs/ABSCHLUSSBERICHT.md` |
