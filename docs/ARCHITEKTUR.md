# Architektur

## Ueberblick

Die Loesung ist bewusst klein und zweigeteilt. Excel mit VBA bildet die
Oberflaeche: zwei sichtbare Blaetter (`Assistent`, `Ergebnisse`), Buttons,
Zwischenablage und der Start des Rechenkerns. Der Rechenkern ist eine
portable Windows-x64-EXE (PyInstaller onedir) ohne Installation und ohne
Adminrechte; er erledigt Import, Textextraktion, OCR, Strukturierung,
Normalisierung, fallbasiertes Lernen, Confidence-Fusion, Persistenz und den
CSV-Export. Beide Seiten sprechen ausschliesslich ueber versionierte
JSON-Jobdateien miteinander; es gibt keine fragile Kommandozeilenverkettung
grosser Texte und keine COM-Kopplung zur Laufzeit.

## Jobprotokoll

Excel legt je Vorgang ein Jobverzeichnis unter
`%LOCALAPPDATA%\LIMS-Probenassistent\jobs\` an, schreibt `request.json`
(Schema `contracts/schemas/JobRequest.schema.json`) und startet
`lims_core.exe run-job --job-dir <ordner>`. Der Kern schreibt fortlaufend
atomar `progress.json` (Phase, Prozent, Meldung, abbrechbar) und zum
Schluss atomar `response.json`. Ein Abbruch erfolgt ueber die Datei
`cancel.flag`; die Analyse liefert dann eine `cancelled`-Fehlerantwort und
hinterlaesst keine halbfertigen Zeilen (eine einzige Transaktion). Lange
Jobs pollt VBA ereignisfreundlich per `Application.OnTime` (1 s); kurze
Jobs (Korrektur, Bestaetigung, Undo, Export, Blattliste) warten begrenzt
mit `DoEvents`.

Vertragsarten: `list_sheets`, `analyze`, `apply_revision`, `row_event`,
`confirm_cells`, `undo`, `rebuild_learning`, `export_csv`, `app_open`,
`app_close`, `health`. Jede Nachricht traegt `schema_version` (Major-Check),
unbekannte Felder werden abgelehnt (`extra="forbid"`), und jede
Ergebniszeile enthaelt genau fuenf Textwerte, wobei `""` gueltig und
positionshaltend ist.

## Analyse-Pipeline (deterministisch vor und nach dem Modell)

Quellparser (pdfplumber fuer Textschicht und Tabellen; pypdfium2 rendert
Bildseiten; Pillow/pillow-heif fuer Bilder; openpyxl/xlrd fuer Excel ohne
jede Makroausfuehrung) -> OCR-Adapter (RapidOCR-ONNX oder Tesseract-deu)
-> Zeilen-/Tabellensegmentierung mit zeilenbezogenem Objektkontext
(`Objekt: ...`-Ueberschriften, Objektspalten, Blattnamen) -> deterministische
Merkmalsextraktion (Etage, Raum, Raumtyp, Ort, Wasserstelle, Armatur,
Medium, Zusatz, VL/RL, PNV, Untersuchungsart; Fuzzy-Reparatur bekannter
Fachbegriffe gegen OCR-Fehler) -> Retrieval aehnlicher bestaetigter
Lernfaelle (TF-IDF, Top-k) -> lokales Sprachmodell NUR fuer verbleibende
Luecken (llama.cpp-Server auf 127.0.0.1, JSON-Schema erzwungen, Ausgabe
zusaetzlich pydantic-validiert und laengenbegrenzt) -> kanonische
Feldbildung (`Bez2 = [Etage], [Raum], [Raumtyp]` usw.) -> Fusion der
Kandidaten mit Provenienz und Teil-Scores -> `is_uncertain` (gelbe Zelle).

Gelb ist eine Zelle genau dann, wenn der Wert nicht direkt/strukturell
belegt ist (Retrieval, LLM, Zusatztext, Titelkontext), die Basissicherheit
unter dem Schwellwert (Standard 0,75) liegt, die OCR-Konfidenz schwach ist
oder Spitzenkandidaten sich widersprechen. Provenienz und Teil-Scores
werden je Feld als `field_proposal` gespeichert; sichtbar ist nur die Farbe.

## Lernkern

Jede direkte Zellkorrektur erzeugt sofort ein Lernbeispiel (Signatur der
Quellzeile + Objektkontext -> bestaetigter Zielwert) und aktualisiert den
Index. Das Loeschen einer automatisch erkannten Zeile ist ein negatives,
eine spaeter kopierte/exportierte manuelle Zeile ein positives
Zeilenbeispiel. Spalten-Button, Strg+C und CSV-Export bestaetigen exakt den
kopierten/exportierten Umfang. Alle Signale sind idempotent
(Deduplizierungsschluessel); Undo deaktiviert die aus dem Ereignis
entstandenen Beispiele und die Indizes werden aus der verbleibenden aktiven
Historie reproduzierbar neu aufgebaut (`rebuild_learning` liefert
Inhalts-Hashes als Nachweis). Index und Zeilendetektor werden bei jedem
Prozessstart vollstaendig aus SQLite abgeleitet - es gibt keinen separaten
Vektorspeicher und kein Fine-Tuning des Sprachmodells.

## Datenhaltung und gemeinsamer Ordner

Die laufende SQLite-Datenbank liegt ausschliesslich lokal
(`%LOCALAPPDATA%\LIMS-Probenassistent\work\lims.sqlite`, WAL lokal
zulaessig). Der gemeinsame Ordner enthaelt nur: die XLSM, `config.json`,
den EXE-Ordner `core\`, den exklusiven Lock (`lock\lims.lock`) und
konsistente Snapshots (`data\snapshot.sqlite` + `snapshot.meta.json` mit
SHA-256, Schemaversion, Sequenz; rollierende Backups in `data\backups\`).

Ablauf beim Oeffnen: Lock exklusiv erwerben (O_CREAT|O_EXCL; Lockdatei mit
Arbeitsplatz, PID, Zeit, Version, Nonce; Heartbeat alle 2 Minuten). Ein
veralteter Lock wird niemals automatisch uebernommen, sondern nur nach
expliziter Benutzerbestaetigung. Danach ausstehenden lokalen Pending-Stand
pushen oder kanonischen Snapshot hashgeprueft in den lokalen Cache ziehen.
Beim Schliessen: konsistente Kopie ueber die SQLite-Backup-API, Tempdatei +
atomarer Replace von Snapshot und Manifest, Backup-Rotation, Lock-Freigabe.
Bei Netzwerkfehlern bleibt der letzte gueltige zentrale Stand unangetastet
und der lokale Stand als Pending markiert; der naechste exklusive Start
synchronisiert ihn.

## Sicherheit

Dokumentinhalt und Zusatztext sind grundsaetzlich untrusted: Der
Systemprompt trennt Anweisung und Daten, das Modell erhaelt nur die
Lueckenfelder, seine Antwort wird gegen ein striktes JSON-Schema erzwungen
und zusaetzlich validiert/gekappt. Excel-Zellen werden vor der Zuweisung als
Text formatiert (keine Formelinterpretation). Quelldatei-Makros werden nie
ausgefuehrt (reine Datenparser; ein vorhandenes vbaProject wird nur
gemeldet). Prozessstarts verwenden ausschliesslich manifestierte Pfade;
Benutzerdaten reisen nur in JSON-Dateien. Ein Offline-Waechter blockiert im
Produktivmodus jeden Socket-Verbindungsaufbau ausser Loopback. Temporaere
Job-/Bilddaten werden im finally geloescht; ein Start-Sweep raeumt
verwaiste Reste ab drei Tagen.
