# Abschlussbericht MVP - LIMS-Probenassistent

Stand: 26.08.2026 · Basis: Spezifikation LIMS-PA-SPEC-001 v1.0 + Implementierungsauftrag
Entwicklungsumgebung: Cloud-Linux-Sandbox (Python 3.11.15, 2 vCPU, 7 GB RAM); macOS-Gates als identische Kommandos + CI-Job `macos-latest`.

## 1. Implementierte Funktionen und zentrale Dateien

Der MVP ist end-to-end funktionsfaehig implementiert - vom Dokument bis zu
den fuenf Excel-Spalten, inklusive Lernen, Export, Lock und Sync. Kein Teil
ist Mock-Fassade; der synthetische End-to-end-Pfad laeuft ueber die echte
CLI, das echte Dateiprotokoll, echte Parser, echte OCR und echte SQLite.

| Bereich | Umsetzung | Zentrale Dateien |
|---|---|---|
| JSON-Vertraege (11 Kinds, Envelopes, Progress) | vollstaendig, `extra=forbid`, Major-Versionscheck, 25 exportierte Schemas | `core/src/lims_assistant/contracts/`, `contracts/schemas/` |
| Datenmodell/SQLite | 15 Tabellen (Sessions, Dokumente, Fragmente, Zeilen/Felder, Proposals, Events, Lernbeispiele, Snapshots), Migrationen, Integritaetscheck | `store/db.py`, `store/repo.py` |
| Import PDF (Textschicht) | pdfplumber: Tabellen mit Kopfzuordnung (10 Kategorien, Folgeseiten ohne Kopf), Freitextzeilen, Seitenauswahl | `ingest/pdf_ingest.py`, `segment/tables.py` |
| Import Scan/Bild | pypdfium2-Rendering, OCR-Adapter RapidOCR-ONNX + Tesseract-deu, Vorverarbeitung (Spike-kalibriert), HEIC, Bildgruppen in Benutzerreihenfolge | `ocr/*`, `ingest/image_ingest.py` |
| Import Excel | XLSX/XLSM (openpyxl) und XLS (xlrd) als reine Datencontainer - Makros nachweislich nie ausgefuehrt; Blattauswahl; Blattname als schwacher Objektkontext | `ingest/excel_ingest.py` |
| Segmentierung/Objekte | zeilenbezogener Bez1-Kontext (`Objekt:`-Kopf, Objektspalte, Titel), Metadatenfilter, Injection-resistente Zeilenkandidatur | `segment/lines.py` |
| Extraktion/Normalisierung | Etage/Raum/Raumtyp/Ort/Wasserstelle/Armatur/Medium/Zusatz/VL-RL/PNV/Untersuchungsart; Fuzzy-OCR-Reparatur; kanonisches Bez2/B3(sanitaer+technisch)/B4; Duplikat-Entdopplung (Ort vs. Raumtyp) | `extract/`, `normalize/compose.py` |
| Lernkern | Ereignisse (Revision/RowEvent/Confirm, idempotent per Dedup-Schluessel), TF-IDF-Fallindex je Feld, Naive-Bayes-Zeilendetektor, Undo-Kompensation, deterministischer Rebuild mit Inhalts-Hashes | `learn/` |
| Fusion/gelbe Markierung | Kandidaten (direkt/Struktur/Retrieval/LLM/Zusatztext/Dokumentkontext) mit Teil-Scores und Provenienz; Gelb-Regel exakt nach Kap. 10.4; hochaehnlicher Lernfall ueberstimmt Dokumentwert (bleibt gelb) | `fusion/fuse.py` |
| LLM-Adapter | llama.cpp-Server (Loopback, `response_format=json_schema`), strikte Nachvalidierung + Laengenkappung, nur Lueckenfelder, Fake-Adapter fuer Tests, Benchmark-Harness | `llm/` |
| Jobprotokoll/CLI | request/progress/response atomar, cancel.flag, Fehlerantworten, `run-job/health/rebuild/heartbeat/sweep/export-schemas` | `jobs/` |
| Export | atomarer Fuenffach-CSV-Export (Temp-Satz -> Replace), UTF-8-BOM/cp1252, CRLF, Leerzeilen positionshaltend, Export-Event + Zellbestaetigungen | `export/csv_export.py` |
| Lock/Sync | exklusiver Lock (Nonce, Heartbeat, stale nur mit Benutzerentscheidung), lokaler Cache, Snapshot mit SHA-256/Sequenz/Backups, Pending bei Netzausfall | `sync/lock.py`, `sync/snapshot.py` |
| Offline-Haertung | Socket-Waechter (nur Loopback) im Produktivmodus; Temp-Cleanup + Start-Sweep | `net_guard.py`, `paths.py` |
| Excel/VBA | 14 Textmodule (~2.170 Zeilen): Assistent-UI, Ergebnistabelle (5 sichtbare + 2 versteckte Technikspalten), Korrekturerkennung, Add/Delete, Ein-Schritt-Undo, Sortierung (Kern-gespiegelt), 5 Copy-Buttons, kontrolliertes Strg+C, Win32-Clipboard (PtrSafe/LongPtr), OnTime-Polling, Lock-UI, idempotenter UI-Builder | `excel/vba-src/` |
| Packaging/CI | PyInstaller-onedir-Spec, `build.ps1` (Tests+Build+Smoke+Hash-Manifest), `build_workbook.ps1` (COM, Trust-Hinweis dokumentiert, manuelle Alternative), `provision_offline.ps1`, GitHub Actions (ubuntu+macos Tests, windows Build+Smoke+Artefakt) | `packaging/`, `.github/workflows/ci.yml` |
| Fixtures/Doku | synthetischer deutscher Korpus (2 Tabellen-/Freitext-PDF, Scan-PDF, PNG/JPG/HEIC, XLSX/XLS/XLSM mit Dummy-vbaProject, Injektionszeile, Gold-Erwartungen), 10 Dokumentationsdateien | `fixtures/synthetic/`, `docs/` |

Umfang: ~6.400 Zeilen Kern-Python, ~2.000 Zeilen Tests, ~2.170 Zeilen VBA.

## 2. Ausgefuehrte Tests (exakte Ergebnisse)

**`pytest` : 120 passed in 16.47s** (Linux-Sandbox, Python 3.11.15) - 0 failed, 0 skipped.

Abgedeckt (Auszug, je mit echten lokalen Komponenten):

- Unit: Normalisierung/Formatbildung (Bez2/B3/B4, haengende Kommas, Leerwerte, OCR-Fuzzy gelb), Sortierung inkl. natuerlicher Ordnung und Wiederherstellung.
- Contract: Fuenf-Felder-Zwang, `""` positionshaltend, Umbruch->Leerzeichen, unbekannte Felder/inkompatible Versionen abgelehnt, Schema-Dateien driftfrei.
- Parser: digitale Tabellen-PDF (14/14 Zeilen, 2 Objekte zeilenbezogen, Duplikat erhalten, Seitenauswahl), Freitext-PDF, XLSX-Blattauswahl, XLS, XLSM-ohne-Makroausfuehrung (inhaltsgleich zur XLSX), Fehlerfall "keine Probenstellen" mit konkreter Meldung.
- OCR (echte Engines): Scan-PDF ohne Textschicht, PNG+JPG-Bildgruppe in Reihenfolge, HEIC, Umlaut-Kanonisierung.
- ML: Korrektur->Lernindex->aehnlicher Folgefall nutzt Korrektur (A-03), Idempotenz je client_event und je Zellwert (kein Mehrfachgewicht, gleicher Index-Hash), Loeschen=Negativbeispiel, manuelle Zeile erst nach Export positiv, Undo kompensiert + Rebuild deterministisch (Hash-Gleichheit bei gleicher aktiver Historie).
- Export: 5 headerlose zeilengleiche Dateien, BOM-Bytes, cp1252-Einbytigkeit + Transliteration, CRLF-only, Leerzeilen an Position, simulierter Teilfehler bei Datei 4 -> Ziele unveraendert + Temp bereinigt, Ueberschreiben, Leerexport.
- Lock/Sync: exklusiv, zweiter Start busy, stale ohne Auto-Uebernahme/mit expliziter Uebernahme, Heartbeat/Fremdschutz, Push/Pull mit Hashpruefung, korrupter Snapshot erkannt, Push-Fehler -> Pending -> spaeterer Push, Backup-Rotation, App-Open/Close ueber echte Jobs (2 Arbeitsplaetze).
- E2E (Subprozess, echte CLI + Dateiprotokoll): analyze->14 validierte Zeilen->Revision-Folgejob; cancel.flag -> `cancelled` ohne halbfertige Zeilen; Offline-Waechter aktiv; defekte request.json -> saubere Fehlerantwort; keine Originaldateien im Daten-/Tempverzeichnis (A-10).
- Sicherheit: Prompt-Injection-Zeile wird nicht Zeile und kein Feld enthaelt den Injektionsmarker; LLM-Schema verbietet Fremdfelder; VBA-Lint (Option Explicit, PtrSafe, verbotene Muster, OnAction-Ziele) als Test-Gate.

## 3. Gemessene Laufzeit und RAM (Entwicklungsmaschine)

`scripts/benchmark_pipeline.py --runs 3` (frischer Prozess je Lauf; Peak-RSS des Kindprozesses; Bericht: `docs/benchmarks/dev-linux-2026-08-26.md`):

| Fall | Zeilen (erkannt/gold) | P/R/F1 | Exact | Edit Ø | Gelb-Quote | p50 | p95 | Peak-RAM |
|---|---|---|---|---|---|---|---|---|
| klinik_digital.pdf (2 Seiten, 2 Objekte, Injektion) | 14/14 | 1.0/1.0/1.0 | 100 % (70/70 Felder) | 0 | 2,9 % | 0,46 s | 0,47 s | 57 MB |
| seniorenresidenz_freitext.pdf | 5/5 | 1.0/1.0/1.0 | 100 % | 0 | 0 % | 0,36 s | 0,39 s | 57 MB |
| schule_scan.pdf (nur Bild, OCR) | 5/5 | 1.0/1.0/1.0 | 100 % | 0 | 24 % | 2,36 s | 2,38 s | 113 MB |
| wohnhaus.xlsx (Blattauswahl) | 6/6 | 1.0/1.0/1.0 | 100 % | 0 | 20 % | 0,54 s | 0,55 s | 113 MB |

Das 2-Minuten-Ziel wird auf der (schwaecheren) Dev-Maschine ohne LLM um
Groessenordnungen unterschritten. **Ehrliche Einordnung:** Der Korpus ist
synthetisch und wurde zusammen mit dem Extraktor entwickelt; 100 % Exact
sagt aus, dass die Regelstrecke den eigenen Referenzkorpus vollstaendig
beherrscht - reale Pilotgenauigkeit kann erst mit anonymisierten
Originaldokumenten gemessen werden (Spezifikation D-15). Es werden keine
realen Genauigkeitswerte behauptet.

## 4. Status Windows-Build und Excel-2016-Abnahme

- **Windows-x64-Build: ausgefuehrt und gruen** (Nachtrag 26.08.2026). Der
  CI-Job `build-windows` ist auf `windows-latest` erstmals vollstaendig
  durchgelaufen: 120 Tests, PyInstaller-onedir, `--version`- und
  `health`-Smoke sowie ein Analyze-Smoke ueber das echte Jobprotokoll, der
  aus `klinik_digital.pdf` **14 Zeilen** erzeugt hat - exakt die
  Gold-Erwartung. Das Paket liegt als Artefakt `lims_core-windows-x64` vor.
  Lokal reproduzierbar bleibt der Weg ueber `packaging/windows/build.ps1`
  (Tests -> PyInstaller onedir -> health-Smoke -> SHA-256-Manifest); dieser
  Skriptpfad ist weiterhin nicht auf einer echten Zielmaschine gelaufen.
- **Excel-2016-x64-Abnahme: offen als dokumentiertes Gate.** Vollstaendige
  manuelle Checkliste mit 30 Einzelpruefungen: `docs/ABNAHME_EXCEL2016.md`.
  VBA ist statisch geprueft (Lint als Test-Gate: Option Explicit ueberall,
  PtrSafe/LongPtr, keine verbotenen Muster, alle Button-/OnKey-/OnTime-
  Ziele vorhanden), aber nicht in echtem Excel ausgefuehrt.
- Workbook-Erzeugung: COM-Weg dokumentiert inkl. Trust-Center-Voraussetzung;
  kurze manuelle Alternative (ca. 5 Minuten) in `docs/EXCEL_SETUP.md`.

## 5. OCR- und Sprachmodell-Status

- **OCR (implementiert und real getestet):** RapidOCR `rapidocr-onnxruntime`
  1.4.4 (PaddleOCR-ONNX, Modelle im Wheel) und Tesseract 5.x `deu`.
  Spike-Ergebnis (docs/AUSFUEHRUNGSNOTIZ.md): Die gebuendelten ch/en-Modelle
  verlieren deutsche Umlaute; Tesseract-deu ist fehlerfrei. `auto`-Wahl:
  RapidOCR mit provisioniertem Latin-Modell > Tesseract-deu > RapidOCR-
  Standard (+Fuzzy-Reparatur, gelb). Das Latin-Modell (Apache-2.0) ist im
  Manifest beschrieben; Download war in der Sandbox nicht moeglich
  (Modell-Hosts gesperrt) und ist Provisionierungsschritt Nr. 1 auf Windows.
- **LLM (Adapter fertig, Modell-Benchmark offen):** llama.cpp-Server-Adapter
  mit Schema-Zwang, Prompt-Haertung, Batch-Luecken-Strategie und Fake-
  Adapter-Tests. Referenzkandidat Qwen3-4B-Instruct-2507 Q4_K_M
  (Apache-2.0) plus Phi-4 Mini/Phi-3 Mini/Gemma-Kandidaten sind im Manifest
  gepinnt beschrieben (`packaging/models/manifest.json`); huggingface.co war
  in der Sandbox gesperrt, daher **keine Modell-Hashes und keine Benchmark-
  Zahlen - Produktionsmodell bewusst ungepinnt** (`docs/MODELLVERGLEICH.md`,
  Harness verifiziert per Trockenlauf). Die Anwendung ist ohne LLM voll
  funktionsfaehig; `llm.enabled=false` ist Auslieferungszustand.

## 6. Verbleibende Blocker und exakt naechster Schritt

Blocker (alle extern begruendet, keiner code-seitig offen):

1. Kein Windows/Excel in der Entwicklungsumgebung -> Build + Abnahme offen.
2. Modell-/Latin-OCR-Downloads in der Sandbox gesperrt -> Benchmark offen.
3. Keine realen anonymisierten Dokumente -> Pilotqualitaet nicht messbar.

**Exakt naechster Schritt:** Auf einem Windows-11-x64-Rechner
`powershell -ExecutionPolicy Bypass -File packaging\windows\build.ps1`
ausfuehren (erzeugt und smoke-testet `dist\lims_core\`), danach
`build_workbook.ps1`, dann die Abnahme-Checkliste `docs/ABNAHME_EXCEL2016.md`
Punkt A1-A6 beginnen. Parallel `provision_offline.ps1 -Step ocr/llama/model`
fuer Latin-OCR-Modell und Qwen3-4B, gefolgt von `scripts/benchmark_llm.py`.

## 7. Git-Status

- Lokales Repository, Branch `main`, Arbeitsbaum sauber.
- GitHub: **`mlautwein/Anlegehelfer`, Sichtbarkeit `public`** (Stand
  26.08.2026 gepusht). Damit weicht das Projekt bewusst von der urspruenglich
  vorgesehenen rein internen Ablage ab: Der Quelltext ist einsehbar
  ("source available"), die Rechte bleiben laut `LICENSE` vollstaendig
  vorbehalten, und Schreibzugriff hat weiterhin nur der Rechteinhaber.
  Ausschlaggebend war, dass GitHub Actions fuer oeffentliche Repositories
  kostenfrei laeuft. Vor der Umstellung wurde die **vollstaendige Historie**
  (284 Objekte, 8 Commits) auf Schluessel, Zugangsdaten und geloeschte
  Dateien geprueft - ohne Befund; die `.gitignore` haelt reale Daten,
  Lerndaten und Modelle fern. Oeffentlich sichtbar wird auch die
  Autor-E-Mail in den Commit-Metadaten.
- Versionierung/Release: `CHANGELOG.md` nach Keep-a-Changelog,
  Release ueber Versionstag `v<version>`. Der Workflow
  `.github/workflows/release.yml` gleicht Tag, `APP_VERSION`,
  `pyproject.toml` und Changelog-Abschnitt ab, faehrt danach das komplette
  CI-Gate und veroeffentlicht erst dann das Windows-x64-Paket mit
  SHA-256-Pruefsumme. `0.y.z` gilt automatisch als Vorabversion.

### Nachtrag zur CI (26.08.2026)

Der erste CI-Lauf auf GitHub war auf `macos-latest` rot: vier OCR-Tests
schlugen fehl. Ursache war nicht die OCR, sondern die Fixture-Erzeugung -
`scripts/make_fixtures.py` kannte nur Linux-Schriftpfade und fiel sonst
stillschweigend auf den nicht skalierbaren Bitmap-Default von Pillow zurueck,
wodurch die Scan-Bilder unlesbar wurden. Die Schriftsuche deckt jetzt Linux,
macOS und Windows ab und bricht mit klarer Meldung ab, statt einen
unbrauchbaren Korpus zu erzeugen. Gegenprobe auf macOS 26 (Python 3.12.13,
RapidOCR): **120 passed** - identisch zur Linux-Zahl aus Abschnitt 2.
