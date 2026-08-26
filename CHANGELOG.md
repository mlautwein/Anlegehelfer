# Changelog

Alle nennenswerten Aenderungen an diesem Projekt werden hier dokumentiert.
Format angelehnt an [Keep a Changelog](https://keepachangelog.com/de/1.1.0/),
Versionierung nach [Semantic Versioning](https://semver.org/lang/de/).

Getrennt versioniert und daher hier nur bei Aenderung erwaehnt:
Jobvertrag (`SCHEMA_VERSION`), SQLite-Schema (`DB_SCHEMA_VERSION`),
Normalisierung (`NORMALIZER_VERSION`), Lernkern (`LEARNER_VERSION`).

## [Unveroeffentlicht]

## [0.1.0] - 2026-08-26

Erste Vorabversion (MVP). Der Rechenkern ist end-to-end funktionsfaehig und
automatisiert getestet; die Windows-/Excel-Gates sind noch offen (siehe
"Bekannte Einschraenkungen"). Jobvertrag `1.0`, DB-Schema `1`,
Normalisierung `norm-1.0`, Lernkern `learn-1.0`.

### Hinzugefuegt

- **Jobvertraege**: 11 Job-Kinds mit Request-/Progress-/Response-Envelopes,
  `extra=forbid`, Major-Versionscheck; 25 exportierte JSON-Schemas unter
  `contracts/schemas/` (driftfrei per Test abgesichert).
- **Datenhaltung**: SQLite mit 15 Tabellen, Migrationen und Integritaetscheck.
- **Import PDF**: Textschicht ueber pdfplumber, Tabellen mit Kopfzuordnung
  (10 Kategorien, Folgeseiten ohne Kopf), Freitextzeilen, Seitenauswahl.
- **Import Scan/Bild**: Rendering ueber pypdfium2, OCR-Adapter fuer
  RapidOCR-ONNX und Tesseract-`deu`, Vorverarbeitung, HEIC, Bildgruppen in
  Benutzerreihenfolge.
- **Import Excel**: XLSX/XLSM (openpyxl) und XLS (xlrd) als reine
  Datencontainer - Makros werden nachweislich nie ausgefuehrt; Blattauswahl.
- **Extraktion/Normalisierung**: Etage, Raum, Raumtyp, Ort, Wasserstelle,
  Armatur, Medium, Zusatz, VL/RL, PNV, Untersuchungsart; Fuzzy-Reparatur von
  OCR-Fehlern; kanonisches `Bez2`/`B3`/`B4`; Duplikat-Entdopplung.
- **Lernkern**: idempotente Ereignisse (Revision, RowEvent, Confirm),
  TF-IDF-Fallindex je Feld, Naive-Bayes-Zeilendetektor, Undo-Kompensation,
  deterministischer Rebuild mit Inhalts-Hashes.
- **Fusion/gelbe Markierung**: Kandidaten mit Teil-Scores und Provenienz;
  Gelb-Regel nach Spezifikation Kap. 10.4; hochaehnlicher Lernfall
  ueberstimmt den Dokumentwert und bleibt gelb.
- **LLM-Adapter**: llama.cpp-Server ueber Loopback mit
  `response_format=json_schema`, strikter Nachvalidierung, Laengenkappung und
  Batch-Luecken-Strategie; Fake-Adapter fuer Tests. Auslieferungszustand ist
  `llm.enabled=false`.
- **Export**: atomarer Fuenffach-CSV-Export (Temp-Satz dann Replace),
  UTF-8-BOM/cp1252, CRLF, positionshaltende Leerzeilen, Export-Event.
- **Lock/Sync**: exklusiver Lock mit Nonce und Heartbeat (stale nur nach
  Benutzerentscheidung), lokaler Arbeitscache, Snapshots mit SHA-256 und
  Sequenz, Backup-Rotation, Pending-Push bei Netzausfall.
- **Offline-Haertung**: Socket-Waechter, der im Produktivmodus jeden
  Netzwerkzugriff ausser Loopback blockiert; Temp-Cleanup und Start-Sweep.
- **Excel/VBA**: 14 Textmodule (~2.170 Zeilen) fuer Assistent-UI,
  Ergebnistabelle, Korrekturerkennung, Ein-Schritt-Undo, Sortierung,
  Copy-Buttons, Win32-Clipboard (PtrSafe/LongPtr), OnTime-Polling, Lock-UI.
- **CLI**: `run-job`, `health`, `rebuild`, `heartbeat`, `sweep`,
  `export-schemas` sowie `--version` (Kern- und Jobvertragsversion).
- **Packaging**: PyInstaller-onedir-Spec, `build.ps1` (Tests, Build, Smoke,
  SHA-256-Manifest), `build_workbook.ps1`, `provision_offline.ps1`.
- **CI/Release**: GitHub Actions mit Kern-Tests auf Ubuntu und macOS,
  Windows-Build inklusive Analyse-Smoke ueber das echte Jobprotokoll sowie
  Release-Workflow, der bei einem Versionstag das portable Windows-x64-Paket
  mit SHA-256-Pruefsumme veroeffentlicht.
- **Fixtures/Doku**: synthetischer deutscher Referenzkorpus mit
  Gold-Erwartungen; elf Dokumentationsdateien unter `docs/`.

### Behoben

- Die Erzeugung der Scan-Fixtures kannte nur Linux-Schriftpfade und fiel auf
  anderen Systemen stillschweigend auf den nicht skalierbaren
  Bitmap-Default von Pillow zurueck. Ergebnis waren unlesbare Scan-Bilder und
  damit vier fehlschlagende OCR-Tests auf macOS. Die Schriftsuche deckt jetzt
  Linux, macOS und Windows ab und bricht mit klarer Meldung ab, statt einen
  unbrauchbaren Korpus zu erzeugen (`scripts/make_fixtures.py`).
- Der Fixture-Generator sagte Reproduzierbarkeit zu, schrieb aber die
  aktuelle Uhrzeit in PDF-Metadaten (reportlab, Pillow) sowie in
  `docProps/core.xml` und die ZIP-Eintraege der Excel-Container (openpyxl).
  Zwei Laeufe erzeugten dadurch unterschiedliche Bytes. Alle Zeitstempel
  liegen jetzt fest; CI prueft die Byte-Gleichheit zweier Laeufe.
- `test_export_csv.py` zerlegte Exportpfade mit `split("/")` und schlug
  dadurch auf Windows fehl, wo der Trenner `\` ist. Der Test benutzt jetzt
  `Path.name`. Betroffen war nur der Test, nicht der Exportcode - gefunden
  vom erstmals durchgelaufenen Windows-CI-Job.

### Geaendert

- `LICENSE` praezisiert, dass der oeffentlich einsehbare Quelltext
  ausdruecklich keine Rechteeinraeumung darstellt ("source available", alle
  Rechte vorbehalten).

### Bekannte Einschraenkungen

- **Windows-x64-Build und Excel-2016-Abnahme sind offen.** Der Build ist
  ueber `packaging/windows/build.ps1` und den CI-Job reproduzierbar, wurde
  aber noch nicht auf einer echten Zielmaschine abgenommen; die manuelle
  Checkliste mit 30 Pruefungen steht in `docs/ABNAHME_EXCEL2016.md`.
- **Kein Produktionsmodell gepinnt.** Latin-OCR-Modell und LLM-Artefakte sind
  in `packaging/models/manifest.json` beschrieben, aber ohne Hashes; die
  Downloads waren in der Entwicklungsumgebung gesperrt
  (`docs/MODELLVERGLEICH.md`).
- **Genauigkeitswerte gelten nur fuer den synthetischen Korpus.** Dieser
  wurde zusammen mit dem Extraktor entwickelt; reale Pilotgenauigkeit ist
  erst mit anonymisierten Originaldokumenten messbar.
- Die Scan-Fixtures werden je nach Betriebssystem mit unterschiedlichen
  Schriften gerendert (Linux DejaVu, macOS Arial, Windows Arial). Die Tests
  sind dagegen unempfindlich; die dokumentierten Benchmarkzahlen beziehen
  sich auf den unter Linux erzeugten Korpus.

[Unveroeffentlicht]: https://github.com/mlautwein/Anlegehelfer/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/mlautwein/Anlegehelfer/releases/tag/v0.1.0
