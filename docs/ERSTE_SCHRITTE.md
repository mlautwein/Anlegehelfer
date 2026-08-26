# Erste Schritte - von null bis zur ersten Arbeitsliste

Diese Seite fuehrt einmalig durch die Einrichtung. Fuer den taeglichen
Betrieb danach: `docs/BEDIENUNG.md`.

## Was du brauchst

- Einen **Windows-11-x64-Rechner** mit **Excel** (getestet gegen Excel 2016
  x64). Der Rechner braucht kein Python.
- Einen Ordner, in dem gearbeitet wird - lokal oder auf einer Freigabe.
  Vorschlag der Installation: `C:\LIMS-Probenassistent`.
- Einmalig Internet fuer die Installation (und fuer Schritt 3). Der spaetere Betrieb ist
  vollstaendig offline; ein Waechter blockiert zur Laufzeit jeden
  Netzwerkzugriff ausser Loopback.

> **Auf einem Mac oder unter Linux** laeuft nur der Rechenkern, nicht die
> Excel-Oberflaeche (sie benutzt Win32-Clipboard und `OnTime`). Zum
> Ausprobieren: siehe "Ohne Excel ausprobieren" ganz unten.

## Installation: zwei Klicks

1. Von der [Releases-Seite](https://github.com/mlautwein/Anlegehelfer/releases)
   das Archiv **`lims-probenassistent-<version>-einrichtung.zip`**
   herunterladen und entpacken (Rechtsklick > "Alle extrahieren").
2. Im entpackten Ordner **`Installieren.cmd`** doppelklicken.

Mehr ist nicht noetig. Windows meldet unter Umstaenden "Der Computer wurde
durch Windows geschuetzt" - dann auf *Weitere Informationen* > *Trotzdem
ausfuehren* klicken (die Datei stammt aus dem Internet und ist nicht
signiert).

Das Skript fragt nur nach dem Arbeitsordner - Eingabetaste uebernimmt den
Vorschlag `C:\LIMS-Probenassistent`. Danach laeuft alles allein:

- Rechenkern aus demselben Release laden, SHA-256 und Hash-Manifest pruefen
- nach `core\` entpacken und `config.json` schreiben
- **Arbeitsmappe mit Excel erzeugen** und in den Ordner legen
- Verknuepfung auf dem Desktop anlegen
- Selbsttest fahren

Am Ende steht entweder "einsatzbereit" oder eine kurze Liste dessen, was
noch offen ist. Zum Starten dann die Desktop-Verknuepfung - fertig.

### Sonderfaelle

**Kein Internet am Zielrechner?** Zusaetzlich
`lims_core-<version>-windows-x64.zip` samt `.sha256` vorab laden und das
Skript von Hand mit dem Paket aufrufen:

    powershell -ExecutionPolicy Bypass -File einrichten.ps1 -Ziel "C:\LIMS-Probenassistent" -Paket "D:\lims_core-0.4.0-windows-x64.zip"

**Kein Excel auf diesem Rechner?** Die Einrichtung laeuft trotzdem durch und
meldet die Mappe als offenen Punkt; erzeugen laesst sie sich dann auf einem
Rechner mit Excel (Schritt 2 unten).

**Repository ausgecheckt?** Dieselben Skripte liegen unter
`packaging\windows\`.

## Schritt 2: Arbeitsmappe nachholen

**Nur noetig, wenn `Installieren.cmd` die Mappe als offenen Punkt gemeldet
hat.** Im Normalfall ist sie bereits erzeugt.

Die XLSM ist bewusst kein fertiges Auslieferungsstueck, sondern entsteht
aus den VBA-Textmodulen unter `excel\vba-src\`. Sie laesst sich nur mit
Excel selbst bauen - deshalb kann sie nicht vorgefertigt mitgeliefert
werden.

Der haeufigste Grund fuer das Scheitern ist ein fehlender Haken in Excel:

> **Datei > Optionen > Trust Center > Einstellungen fuer das Trust Center >
> Makroeinstellungen > "Zugriff auf das VBA-Projektobjektmodell vertrauen"**

Haken setzen, `Installieren.cmd` erneut doppelklicken - danach kann der
Haken wieder weg.

Ohne Aenderung am Trust Center geht es auch von Hand in etwa fuenf Minuten:
`docs/EXCEL_SETUP.md`, **Weg B** - elf Module importieren,
`modSetup.EnsureUi` ausfuehren, fertig. Die erzeugte
`LIMS-Probenassistent.xlsm` gehoert dann in den Arbeitsordner:

    C:\LIMS-Probenassistent\
      LIMS-Probenassistent.xlsm
      config.json
      core\
        lims_core.exe
        hashes.json
        LIESMICH.txt

## Schritt 3: Deutsche Umlaute in Scans (empfohlen)

Das Paket bringt nur die RapidOCR-Standardmodelle mit (chinesisch/englisch).
Die verlieren deutsche Umlaute - aus "Teekueche" wird "Teekuche". Die
Fuzzy-Reparatur faengt das ab und markiert die Werte **gelb**, aber sauberer
ist das Latin-Modell:

    powershell -ExecutionPolicy Bypass -File provision_offline.ps1 -Step model

Danach die berechnete SHA-256 in `packaging\models\manifest.json` eintragen.

Ob es greift, verraet die Selbstauskunft - `ocr.detail` nennt das aktive
Modell:

    C:\LIMS-Probenassistent\core\lims_core.exe --config C:\LIMS-Probenassistent\config.json health

**Digitale PDFs und Excel-Dateien sind davon nicht betroffen**, nur Scans
und Fotos.

## Schritt 4: Erster Durchlauf

Die Desktop-Verknuepfung **LIMS-Probenassistent** anklicken (oder die
XLSM im Arbeitsordner). Excel fragt nach Makros - diese zulassen.

Zum Ausprobieren liegen im Repository unter `fixtures\synthetic\` fertige
Beispieldateien; `klinik_digital.pdf` ergibt 14 Zeilen.

Im Blatt `Assistent`: **Dateien waehlen** > **Analyse starten**. Die Zeilen
erscheinen im Blatt `Ergebnisse` in genau fuenf Spalten. Gelb heisst
unsicher - pruefen und ueberschreiben; jede Korrektur wird gelernt.

Dann je Spalte der **Kopieren**-Knopf und im LIMS einfuegen. Was du
kopierst, bestaetigt genau diesen Umfang als richtig.

Ab hier: `docs/BEDIENUNG.md`.

## Wenn etwas klemmt

| Symptom | Ursache und Abhilfe |
|---|---|
| Windows warnt beim Start von `Installieren.cmd` | *Weitere Informationen* > *Trotzdem ausfuehren*. Die Datei ist nicht signiert. |
| Doppelklick auf `lims_core.exe` bewirkt nichts | Richtig so - der Kern hat keine eigene Oberflaeche und wird von der Arbeitsmappe gesteuert. Er zeigt beim Start ohne Kommando einen Hinweistext. Zum Pruefen: `lims_core.exe health` in einer Eingabeaufforderung. Siehe auch `core\LIESMICH.txt`. |
| Es ist keine Excel-Mappe im Paket | Richtig - `Installieren.cmd` erzeugt sie beim Einrichten. Klappt das nicht, meldet es das als offenen Punkt (Schritt 2). |
| `einrichten.ps1` meldet "core\ existiert bereits" | Absicht, damit nichts unbemerkt ueberschrieben wird. Mit `-Ueberschreiben` erneut aufrufen. |
| "SHA-256 stimmt nicht" | Uebertragung unvollstaendig oder Paket manipuliert. Neu laden, **nicht** verwenden. |
| Selbsttest meldet "OCR steht NICHT zur Verfuegung" | Paket unvollstaendig entpackt. Schritt 1 mit `-Ueberschreiben` wiederholen. |
| Mappe startet nur lesend | Jemand anderes hat den Schreibzugriff; der Name steht oben im Blatt `Assistent`. Nach einem Absturz wird der alte Lock nach Rueckfrage uebernommen. |
| Scans liefern keine oder wirre Zeilen | Meist Aufloesung. Als PDF mit mindestens 300 dpi scannen statt abfotografieren. |
| Umlaute fehlerhaft, Zellen gelb | Latin-Modell fehlt - Schritt 3. |
| Excel meldet Makros blockiert | Rechtsklick auf die XLSM > Eigenschaften > "Zulassen" haken (Datei kam aus dem Internet). |

## Ohne Excel ausprobieren (Mac/Linux)

Der Rechenkern selbst ist plattformneutral. Damit laesst sich die
Erkennung testen, ohne Windows:

    python3 -m venv .venv && source .venv/bin/activate
    pip install -e ".[dev]" && pip install -e ".[ocr]"
    python scripts/make_fixtures.py

Ein Auftrag ist eine JSON-Datei in einem Ordner:

    mkdir -p /tmp/job
    cat > /tmp/job/request.json <<'JSON'
    {"schema_version":"1.0","job_id":"test-1","kind":"analyze",
     "created_utc":"2026-01-01T00:00:00Z",
     "payload":{"sources":[{"type":"pdf","paths":["fixtures/synthetic/klinik_digital.pdf"]}]}}
    JSON
    lims-core run-job --job-dir /tmp/job

Das Ergebnis steht in `/tmp/job/response.json`. Fuer korrekte Umlaute in
Scans hier `tesseract` mit Sprachpaket `deu` installieren
(macOS: `brew install tesseract tesseract-lang`).
