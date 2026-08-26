# Excel-Setup: Arbeitsmappe aus den Textmodulen erzeugen

Die VBA-Quellmodule unter `excel/vba-src/` sind die einzige Quelle; die
XLSM ist ein Buildartefakt. Es gibt zwei gleichwertige Wege.

## Weg A: automatisch (PowerShell + Excel-COM)

    powershell -ExecutionPolicy Bypass -File packaging\windows\build_workbook.ps1

Voraussetzung (einmalig, dokumentierte COM-Einschraenkung): Excel muss den
Zugriff auf das VBA-Projektobjektmodell erlauben:

> Datei > Optionen > Trust Center > Einstellungen fuer das Trust Center >
> Makroeinstellungen > Haken bei **"Zugriff auf das VBA-Projektobjektmodell
> vertrauen"**.

Ohne diesen Haken bricht das Skript mit einem klaren Hinweis ab. Der Haken
kann nach dem Build wieder entfernt werden. Ergebnis:
`dist\LIMS-Probenassistent.xlsm`.

## Weg B: manuell (ca. 5 Minuten, ohne Trust-Center-Aenderung)

1. Excel starten, neue leere Arbeitsmappe, speichern als
   `LIMS-Probenassistent.xlsm` (Typ: "Excel-Arbeitsmappe mit Makros").
2. Alt+F11 (VBA-Editor). Datei > Datei importieren ... und nacheinander alle
   `mod*.bas` aus `excel\vba-src\` importieren (11 Module).
3. Im Projektbaum `ThisWorkbook` doppelklicken und den CODE-Teil aus
   `ThisWorkbook.cls` hineinkopieren (alles ab `Option Explicit`; die
   Kopfzeilen `VERSION/BEGIN/Attribute` weglassen).
4. Direktfenster (Strg+G) oeffnen und ausfuehren:  `modSetup.EnsureUi`
   Damit entstehen die Blaetter `Assistent`, `Ergebnisse`, `_Meta`, die
   Ergebnistabelle und alle Schaltflaechen.
5. Im Projektbaum das Blatt `Ergebnisse` doppelklicken und den CODE-Teil aus
   `SheetErgebnisse.cls` einfuegen (ab `Option Explicit`). Fuer `Assistent`
   ist kein Blattcode noetig (`SheetAssistent.cls` ist bewusst leer).
6. Speichern, schliessen, wieder oeffnen: Die Mappe startet mit leerer
   Ergebnisliste und meldet den Lock-Status.

## Ablage im gemeinsamen Ordner

    <Gemeinsamer Ordner>\
      LIMS-Probenassistent.xlsm
      config.json                  (siehe unten)
      core\                        (onedir-Ausgabe von build.ps1)
        lims_core.exe
        hashes.json
        models\ocr\...             (provisioniert)
        llm\llama-server.exe       (optional, provisioniert)
      lock\                        (legt die Anwendung an)
      data\                        (Snapshots + Backups, legt die Anwendung an)

Beispiel `config.json` (liegt neben der XLSM; relative Pfade beziehen sich
auf den gemeinsamen Ordner):

    {
      "share_dir": ".",
      "core_exe": "core/lims_core.exe",
      "certainty_threshold": 0.75,
      "export_encoding": "utf8_bom",
      "ocr": {
        "engine": "auto",
        "rec_model_path": "core/models/ocr/latin_PP-OCRv3_rec_infer.onnx",
        "dict_path": "core/models/ocr/latin_dict.txt"
      },
      "llm": {
        "enabled": false,
        "server_binary": "core/llm/llama-server.exe",
        "model_path": "core/models/llm/<kandidat>.gguf",
        "model_sha256": "<sha256 aus manifest.json>"
      }
    }

Hinweis: `llm.enabled` bleibt `false`, bis der Modell-Benchmark
(`docs/MODELLVERGLEICH.md`) ein Produktionsmodell gepinnt hat. Die
Anwendung ist ohne LLM voll funktionsfaehig.

Empfehlung: Die XLSM im Share mit Schreibschutz-Empfehlung speichern
(Datei > Informationen) - Anwender arbeiten immer mit frisch geleerter
Liste; gespeicherte Nutzstaende sind nicht vorgesehen.
