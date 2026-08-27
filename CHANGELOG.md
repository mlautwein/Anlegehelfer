# Changelog

Alle nennenswerten Aenderungen an diesem Projekt werden hier dokumentiert.
Format angelehnt an [Keep a Changelog](https://keepachangelog.com/de/1.1.0/),
Versionierung nach [Semantic Versioning](https://semver.org/lang/de/).

Getrennt versioniert und daher hier nur bei Aenderung erwaehnt:
Jobvertrag (`SCHEMA_VERSION`), SQLite-Schema (`DB_SCHEMA_VERSION`),
Normalisierung (`NORMALIZER_VERSION`), Lernkern (`LEARNER_VERSION`).

## [Unveroeffentlicht]

## [0.5.0] - 2026-08-26

Auslieferung fuer Laien: ein Archiv, ein Doppelklick, keine Rueckfrage,
kein Internet.

### Geaendert

- **Nur noch EIN Release-Archiv**: `LIMS-Probenassistent-<version>-Setup-Windows.zip`.
  Bisher musste man zwischen Einrichtungs- und Kernarchiv waehlen - eine
  Entscheidung, die niemand treffen koennen muss.
- **Der Rechenkern liegt im Archiv.** Die Installation laedt nichts mehr
  nach und funktioniert damit ohne Internet und in abgeschotteten Netzen.
  Statt Download und Entpacken wird der beiliegende Ordner kopiert und
  gegen das Hash-Manifest geprueft; die separate ZIP-Pruefsumme entfaellt
  dadurch.
- **Keine Rueckfrage mehr nach dem Zielordner.** Installiert wird nach
  `C:\LIMS-Probenassistent`; scheitert das an fehlenden Rechten, weicht die
  Installation selbsttaetig in `%LOCALAPPDATA%` aus. Ein gemeinsamer Ordner
  laesst sich weiterhin mit `-Ziel` waehlen.

### Hinzugefuegt

- `ANLEITUNG.txt` im Archiv - Kurzfassung in Alltagssprache: installieren,
  starten, die vier haeufigsten Stolpersteine. Ohne Fachbegriffe.
- `Beispiel-Arbeitsliste.pdf` liegt bei, damit der erste Durchlauf ohne
  eigene Dokumente moeglich ist (ergibt 14 Zeilen).
- Der Windows-CI-Job stellt den Setup-Ordner wie im Release zusammen und
  faehrt genau den Aufruf, den `Installieren.cmd` ausloest - der
  Anwenderweg wird also bei jedem Push getestet, nicht nur der
  Entwicklerweg.

## [0.4.0] - 2026-08-26

Installation auf zwei Klicks verkuerzt: Archiv entpacken,
`Installieren.cmd` doppelklicken. Kommandozeile ist nicht mehr noetig.

### Hinzugefuegt

- `Installieren.cmd` im Einrichtungsarchiv - doppelklickbar, weil Windows
  `.ps1`-Dateien per Doppelklick im Editor oeffnet statt auszufuehren.
  Ruft `einrichten.ps1 -Interaktiv` auf und haelt das Fenster offen.
- `einrichten.ps1` erledigt jetzt den ganzen Weg: Es schlaegt einen
  Arbeitsordner vor (`C:\LIMS-Probenassistent`, per Eingabetaste zu
  uebernehmen), **erzeugt die Excel-Arbeitsmappe automatisch** und legt eine
  Verknuepfung auf dem Desktop an. Fehlt Excel oder blockiert das Trust
  Center die Automation, laeuft der Rest trotzdem durch und die Mappe
  erscheint als benannter offener Punkt statt als Abbruch.
- Neue Schalter: `-Interaktiv` (Nachfragen statt Abbrechen), `-OhneMappe`.
  `-Ziel` ist optional geworden.

### Behoben

- `build_workbook.ps1` suchte die VBA-Quellen fest ueber
  `$PSScriptRoot\..\..` und haette im entpackten Einrichtungsarchiv, wo
  `excel\vba-src` direkt daneben liegt, gar nicht funktioniert. Es probiert
  jetzt beide Layouts und nimmt `-VbaDir` sowie `-Ziel` entgegen, damit die
  Mappe direkt im Arbeitsordner entsteht statt in `dist\`.

## [0.3.0] - 2026-08-26

Behebt zwei Dinge, die beim ersten Auspacken sofort aufgefallen sind: Die
EXE wirkte beim Doppelklick tot, und die Excel-Arbeitsmappe war weder im
Paket noch waren die Mittel dabei, sie zu bauen.

### Hinzugefuegt

- Das Release enthaelt ein zweites Archiv
  `lims-probenassistent-<version>-einrichtung.zip` mit `einrichten.ps1`,
  `build_workbook.ps1`, `provision_offline.ps1`, den VBA-Quellen der
  Arbeitsmappe, der Beispielkonfiguration und den Anleitungen. Vorher kam
  nur ans Ziel, wer zusaetzlich das Repository ausgecheckt hat - das
  Release allein reichte nicht.
- `LIESMICH.txt` liegt jetzt direkt neben `lims_core.exe` und erklaert dort,
  warum ein Doppelklick nichts bewirkt, wo die Arbeitsmappe hingehoert und
  wie sich der Kern per `health` pruefen laesst.

### Behoben

- **`lims_core.exe` schien beim Doppelklick nichts zu tun.** Ohne Kommando
  brach argparse mit einer knappen Fehlerzeile ab; das von Windows
  geoeffnete Konsolenfenster schloss sich sofort wieder. Der Kern erklaert
  jetzt in klaren Worten, dass er keine eigene Oberflaeche hat, von der
  Arbeitsmappe gesteuert wird und wie der Selbsttest geht - und haelt das
  Fenster offen, wenn es ihm allein gehoert (Doppelklick). Aus einer
  bereits offenen Eingabeaufforderung wird nicht gewartet.

## [0.2.0] - 2026-08-26

Macht die Auslieferung tatsaechlich benutzbar: eine Einrichtung in einem
Durchgang und die Reparatur eines Fehlers, der die OCR im ausgelieferten
Paket komplett abgeschaltet haette. 122 Tests gruen auf Linux, macOS und
Windows. Jobvertrag `1.0` unveraendert - bestehende Jobdateien bleiben
gueltig.

### Hinzugefuegt

- `packaging/windows/einrichten.ps1` richtet den gemeinsamen Ordner in einem
  Durchgang ein: Release laden (oder lokales ZIP verwenden), SHA-256 und
  mitgeliefertes Hash-Manifest pruefen, nach `core\` entpacken, passende
  `config.json` schreiben, Selbsttest fahren und benennen, was noch fehlt.
  Ein CI-Schritt fuehrt das Skript auf `windows-latest` gegen das frisch
  gebaute Paket aus, damit die Anleitung nicht ungeprueft bleibt.
- `docs/ERSTE_SCHRITTE.md` fuehrt linear von null bis zur ersten
  Arbeitsliste, inklusive Fehlertabelle und einem Abschnitt zum
  Ausprobieren ohne Excel auf Mac/Linux.
- `packaging/windows/constraints-windows-x64.txt` pinnt die 43 Pakete des
  Auslieferungsbuilds auf exakte Versionen. `build.ps1`, der Windows-CI-Job
  und der Release-Workflow loesen dagegen auf, ein CI-Schritt laesst den
  Build fehlschlagen, sobald die installierten Versionen abweichen.
  `pyproject.toml` behaelt bewusst Bereiche, damit die Testmatrix
  Regressionen in neuen Bibliotheksversionen weiterhin findet.

### Behoben

- **OCR fiel komplett aus, wenn ein konfiguriertes Zusatzmodell fehlte.**
  Die ausgelieferte `config.json` verweist auf das Latin-Rec-Modell, das erst
  per `provision_offline.ps1` daneben gelegt wird. Vorher warf RapidOCR beim
  Laden, und da im Windows-Paket kein Tesseract liegt, blieb gar keine Engine
  uebrig: Scans und Fotos lieferten kommentarlos null Zeilen. Die
  Auswahlkette faellt jetzt wie dokumentiert auf die gebuendelten
  Standardmodelle zurueck und weist in der Selbstauskunft darauf hin. Zwei
  Regressionstests sichern das ab.
- Der Changelog-Abschnitt zu 0.1.0 behauptete einleitend noch offene
  Windows-Gates, obwohl die Aufzaehlung darunter den gruenen CI-Build bereits
  festhielt. Ausserdem fehlte der Hinweis, dass das ausgelieferte Paket nur
  die RapidOCR-Standardmodelle enthaelt (siehe dort). `docs/LIZENZEN.md` und
  `docs/WINDOWS_BUILD.md` gingen weiterhin von einem privaten, noch nicht
  gepushten Repository aus.

## [0.1.0] - 2026-08-26

Erste Vorabversion (MVP). Der Rechenkern ist end-to-end funktionsfaehig und
automatisiert getestet - 120 Tests gruen auf Linux, macOS und Windows, das
Windows-x64-Paket wird in CI gebaut und smoke-getestet. Offen bleiben die
manuelle Excel-2016-Abnahme und die Provisionierung der OCR-/LLM-Modelle
(siehe "Bekannte Einschraenkungen"). Jobvertrag `1.0`, DB-Schema `1`,
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

- **Excel-2016-Abnahme ist offen.** Das VBA ist statisch geprueft (Lint als
  Test-Gate), aber nie in echtem Excel ausgefuehrt worden; die manuelle
  Checkliste mit 30 Pruefungen steht in `docs/ABNAHME_EXCEL2016.md`.
- **Der Windows-Build laeuft nur in CI.** `windows-latest` baut die
  onedir-EXE und besteht den Analyse-Smoke ueber das echte Jobprotokoll
  (14 Zeilen aus `klinik_digital.pdf`). Auf einer echten Zielmaschine mit
  `packaging/windows/build.ps1` wurde er noch nicht abgenommen.
- **Kein Produktionsmodell gepinnt.** Latin-OCR-Modell und LLM-Artefakte sind
  in `packaging/models/manifest.json` beschrieben, aber ohne Hashes; die
  Downloads waren in der Entwicklungsumgebung gesperrt
  (`docs/MODELLVERGLEICH.md`).
- **Das ausgelieferte Paket enthaelt nur die RapidOCR-Standardmodelle**
  (`ch_PP-OCRv4_*`, chinesisch/englisch). Diese verlieren deutsche Umlaute
  ("Teekuche" statt "Teekueche"); die Fuzzy-Reparatur faengt das ab, markiert
  die Werte aber gelb. Fuer saubere deutsche OCR muss vor dem Offline-Einsatz
  das Latin-Modell provisioniert werden:
  `packaging/windows/provision_offline.ps1 -Step model`
  (Details in `docs/WINDOWS_BUILD.md`). Tesseract ist bewusst nicht im Paket -
  es ist der Entwicklungspfad, nicht der Auslieferungspfad.
- **Genauigkeitswerte gelten nur fuer den synthetischen Korpus.** Dieser
  wurde zusammen mit dem Extraktor entwickelt; reale Pilotgenauigkeit ist
  erst mit anonymisierten Originaldokumenten messbar.
- Die Scan-Fixtures werden je nach Betriebssystem mit unterschiedlichen
  Schriften gerendert (Linux DejaVu, macOS Arial, Windows Arial). Die Tests
  sind dagegen unempfindlich; die dokumentierten Benchmarkzahlen beziehen
  sich auf den unter Linux erzeugten Korpus.

[Unveroeffentlicht]: https://github.com/mlautwein/Anlegehelfer/compare/v0.5.0...HEAD
[0.5.0]: https://github.com/mlautwein/Anlegehelfer/releases/tag/v0.5.0
[0.4.0]: https://github.com/mlautwein/Anlegehelfer/releases/tag/v0.4.0
[0.3.0]: https://github.com/mlautwein/Anlegehelfer/releases/tag/v0.3.0
[0.2.0]: https://github.com/mlautwein/Anlegehelfer/releases/tag/v0.2.0
[0.1.0]: https://github.com/mlautwein/Anlegehelfer/releases/tag/v0.1.0
