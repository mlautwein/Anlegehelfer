# LIMS-Probenassistent

[![CI](https://github.com/mlautwein/Anlegehelfer/actions/workflows/ci.yml/badge.svg)](https://github.com/mlautwein/Anlegehelfer/actions/workflows/ci.yml)

**Version 0.6.0** (Vorabversion - die manuelle Excel-2016-Abnahme ist noch
offen) · Jobvertrag `1.0` · [Erste Schritte](docs/ERSTE_SCHRITTE.md) ·
[Changelog](CHANGELOG.md) ·
[Releases](https://github.com/mlautwein/Anlegehelfer/releases)

> **Source available, nicht Open Source.** Der Quelltext ist oeffentlich
> einsehbar, alle Rechte bleiben vorbehalten - Nutzung, Bearbeitung und
> Weitergabe nur mit schriftlicher Zustimmung (siehe [LICENSE](LICENSE)).
> Schreibzugriff hat ausschliesslich der Rechteinhaber. Reale Dokumente,
> Lerndaten, Modelle und Geheimnisse gehoeren nicht in dieses Repository.

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
    lims-core --version              # Kern- und Jobvertragsversion

Fuer die Dev-OCR mit korrekten deutschen Umlauten: `tesseract` mit Sprachpaket
`deu` installieren (macOS: `brew install tesseract tesseract-lang`).

Die Scan-Fixtures werden mit einer Systemschrift gerendert (Linux DejaVu,
macOS/Windows Arial). Findet `scripts/make_fixtures.py` keine skalierbare
Schrift, bricht es mit einer Meldung ab, statt einen unlesbaren Korpus zu
erzeugen.

## Loslegen

Auf einem Windows-Rechner mit Excel sind es zwei Klicks:

1. `LIMS-Probenassistent-<version>-Setup-Windows.zip` von der
   [Releases-Seite](https://github.com/mlautwein/Anlegehelfer/releases) laden
   und entpacken.
2. `Installieren.cmd` doppelklicken.

Ein einziges Archiv, der Rechenkern liegt darin - die Installation laedt
nichts nach und braucht kein Internet. Sie fragt nichts, kopiert den Kern,
prueft ihn gegen das Hash-Manifest, schreibt `config.json`, erzeugt die
Arbeitsmappe mit Excel, legt eine Desktop-Verknuepfung an und faehrt einen
Selbsttest. Ausfuehrlich: `docs/ERSTE_SCHRITTE.md`.

## Windows-Bereitstellung im Detail

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

## Release erstellen

Releases entstehen ausschliesslich ueber einen Versionstag; der Workflow
`.github/workflows/release.yml` prueft zuerst, ob Tag, `APP_VERSION`,
`pyproject.toml` und der Changelog-Abschnitt zusammenpassen, faehrt dann das
komplette CI-Gate und baut erst danach das Paket.

1. `CHANGELOG.md`: Abschnitt `## [<version>] - <datum>` fuellen.
2. Version in `core/src/lims_assistant/version.py` (`APP_VERSION`) und
   `pyproject.toml` gleichziehen.
3. `git tag -a v<version> -m "..." && git push origin v<version>`.

Der Auslieferungsbuild loest gegen
`packaging/windows/constraints-windows-x64.txt` auf (exakte Versionen aller
43 Pakete), damit zwei Builds zeitversetzt dieselbe EXE ergeben. Die
Testmatrix nutzt bewusst die Bereiche aus `pyproject.toml`, um Regressionen
in neuen Bibliotheksversionen zu finden. Weichen die installierten Versionen
von der Datei ab, schlaegt der CI-Schritt "Versionsbindung pruefen" fehl -
dann das Artefakt `constraints-windows-x64` herunterladen und die Datei
aktualisieren.

Ergebnis des Workflows: ein GitHub-Release mit genau einem Archiv,
`LIMS-Probenassistent-<version>-Setup-Windows.zip` (Rechenkern inklusive
`hashes.json`, Installer, VBA-Quellen, Anleitungen, Beispieldatei) und
zugehoeriger `.sha256`-Pruefsumme. Versionen `0.y.z` und Tags mit Suffix
werden automatisch als Vorabversion markiert.

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
| **Einrichtung von null an** | **`docs/ERSTE_SCHRITTE.md`** |
| Aenderungen je Version | `CHANGELOG.md` |
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
