# Erste Schritte - von null bis zur ersten Arbeitsliste

Diese Seite fuehrt einmalig durch die Einrichtung. Fuer den taeglichen
Betrieb danach: `docs/BEDIENUNG.md`.

## Was du brauchst

- Einen **Windows-11-x64-Rechner** mit **Excel** (getestet gegen Excel 2016
  x64). Der Rechner braucht kein Python.
- Einen Ordner, in dem gearbeitet wird - lokal oder auf einer Freigabe.
  In dieser Anleitung: `C:\LIMS-PA`.
- Fuer Schritt 1 und 3 einmalig Internet. Der spaetere Betrieb ist
  vollstaendig offline; ein Waechter blockiert zur Laufzeit jeden
  Netzwerkzugriff ausser Loopback.

> **Auf einem Mac oder unter Linux** laeuft nur der Rechenkern, nicht die
> Excel-Oberflaeche (sie benutzt Win32-Clipboard und `OnTime`). Zum
> Ausprobieren: siehe "Ohne Excel ausprobieren" ganz unten.

## Schritt 1: Paket einrichten

Repository holen (oder als ZIP herunterladen und entpacken), dann:

    powershell -ExecutionPolicy Bypass -File packaging\windows\einrichten.ps1 -Ziel "C:\LIMS-PA"

Das Skript laedt das aktuelle Release, prueft die SHA-256-Pruefsumme,
entpackt nach `C:\LIMS-PA\core\`, gleicht jede Datei gegen das mitgelieferte
Hash-Manifest ab, schreibt eine passende `config.json` und faehrt einen
Selbsttest. Am Ende steht, was noch fehlt.

Kein Internet am Zielrechner? Das ZIP samt `.sha256` vorab von der
[Releases-Seite](https://github.com/mlautwein/Anlegehelfer/releases) laden
und mitgeben:

    powershell -ExecutionPolicy Bypass -File packaging\windows\einrichten.ps1 -Ziel "C:\LIMS-PA" -Paket "D:\lims_core-0.2.0-windows-x64.zip"

## Schritt 2: Excel-Mappe erzeugen

Die XLSM ist bewusst kein Repository-Inhalt, sondern entsteht aus den
VBA-Textmodulen unter `excel\vba-src\`. Sie laesst sich nur mit Excel selbst
bauen - dieser Schritt ist deshalb nicht automatisierbar.

    powershell -ExecutionPolicy Bypass -File packaging\windows\build_workbook.ps1

Dafuer muss einmalig **Datei > Optionen > Trust Center > Einstellungen fuer
das Trust Center > Makroeinstellungen > "Zugriff auf das
VBA-Projektobjektmodell vertrauen"** gesetzt sein; der Haken kann danach
wieder weg. Ohne ihn bricht das Skript mit klarem Hinweis ab.

Alternative ohne Trust-Center-Aenderung: `docs/EXCEL_SETUP.md`, **Weg B** -
elf Module importieren, `modSetup.EnsureUi` ausfuehren, fertig (ca. 5 min).

Die erzeugte `LIMS-Probenassistent.xlsm` nach `C:\LIMS-PA\` legen. Der
Ordner sieht dann so aus:

    C:\LIMS-PA\
      LIMS-Probenassistent.xlsm
      config.json
      core\
        lims_core.exe
        hashes.json

## Schritt 3: Deutsche Umlaute in Scans (empfohlen)

Das Paket bringt nur die RapidOCR-Standardmodelle mit (chinesisch/englisch).
Die verlieren deutsche Umlaute - aus "Teekueche" wird "Teekuche". Die
Fuzzy-Reparatur faengt das ab und markiert die Werte **gelb**, aber sauberer
ist das Latin-Modell:

    powershell -ExecutionPolicy Bypass -File packaging\windows\provision_offline.ps1 -Step model

Danach die berechnete SHA-256 in `packaging\models\manifest.json` eintragen.

Ob es greift, verraet die Selbstauskunft - `ocr.detail` nennt das aktive
Modell:

    C:\LIMS-PA\core\lims_core.exe --config C:\LIMS-PA\config.json health

**Digitale PDFs und Excel-Dateien sind davon nicht betroffen**, nur Scans
und Fotos.

## Schritt 4: Erster Durchlauf

`LIMS-Probenassistent.xlsm` oeffnen (Makros zulassen). Zum Ausprobieren
liegen im Repository unter `fixtures\synthetic\` fertige Beispieldateien -
`klinik_digital.pdf` ergibt 14 Zeilen.

Im Blatt `Assistent`: **Dateien waehlen** > **Analyse starten**. Die Zeilen
erscheinen im Blatt `Ergebnisse` in genau fuenf Spalten. Gelb heisst
unsicher - pruefen und ueberschreiben; jede Korrektur wird gelernt.

Dann je Spalte der **Kopieren**-Knopf und im LIMS einfuegen. Was du
kopierst, bestaetigt genau diesen Umfang als richtig.

Ab hier: `docs/BEDIENUNG.md`.

## Wenn etwas klemmt

| Symptom | Ursache und Abhilfe |
|---|---|
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
