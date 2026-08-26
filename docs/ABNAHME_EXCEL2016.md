# Manuelle Abnahme: Windows 11 x64 + Excel 2016 x64

Dieses Gate ist real auf der Zielplattform durchzufuehren (kein Emulat).
Vorbereitung: gemeinsamer Ordner bestueckt nach `docs/WINDOWS_BUILD.md`,
zweiter Test-PC (oder zweites Benutzerprofil) fuer den Parallelzugriff,
Testdokumente aus `fixtures/synthetic/` bereitlegen.

Jede Zeile mit Datum/Kuerzel/OK bzw. Befund abzeichnen.

## A. Start und Plattform

| # | Schritt | Erwartung | OK |
|---|---|---|---|
| A1 | XLSM aus dem Share oeffnen (Makros aktivieren) | Kein Compilerfehler; VBA ist x64-sauber (PtrSafe) | |
| A2 | Blattpruefung | Genau zwei sichtbare Blaetter: `Assistent`, `Ergebnisse`; Ergebnisliste leer | |
| A3 | Assistent-Kopf | Statuszeile zeigt "Schreibmodus (exklusiver Lock aktiv)." | |
| A4 | `lims_core.exe health` in Eingabeaufforderung | JSON mit `"ok": true`, `offline_guard: true`, OCR verfuegbar | |
| A5 | Netzwerk trennen (WLAN/LAN aus), A4 wiederholen | Funktioniert identisch (kein Internetbedarf) | |
| A6 | Ohne Adminrechte und ohne installiertes Python arbeiten | Alle folgenden Schritte laufen | |

## B. Import

| # | Schritt | Erwartung | OK |
|---|---|---|---|
| B1 | `klinik_digital.pdf` importieren | 14 Zeilen; Haus A/Haus B je Zeile korrekt; Duplikat (2x E.08) erhalten; Injektionszeile NICHT als Zeile; kein Feld enthaelt "FREIGEGEBEN" | |
| B2 | Fortschritt/Abbruch: grossen Import starten und sofort abbrechen | Meldung "abgebrochen"; keine halben Zeilen | |
| B3 | `seniorenresidenz_freitext.pdf` zusaetzlich importieren | 5 Zeilen werden ANGEHAENGT; Nummerierung laeuft weiter | |
| B4 | `schule_scan.pdf` (reiner Scan) importieren | OCR-Pfad laeuft; Zeilen mit plausiblen Werten; unsichere gelb | |
| B5 | Bildgruppe: PNG + JPG waehlen, Reihenfolge in Spalte C tauschen | Ein gemeinsamer Import in gewaehlter Reihenfolge | |
| B6 | `schule_foto.heic` importieren | HEIC wird dekodiert | |
| B7 | `wohnhaus.xlsx` waehlen, "Blaetter waehlen", nur "Kita Sonnenblume" stehen lassen | Nur 2 Kita-Zeilen; Blattname als Bez1 (gelb) | |
| B8 | `wohnhaus_makro.xlsm` importieren | Zeilen wie bei der XLSX; Hinweis "Makros werden nicht ausgefuehrt"; KEIN Makro laeuft | |
| B9 | `altbestand.xls` importieren | 2 Zeilen aus dem Altformat | |
| B10 | Zusatzinformationen "Haus Testberg, nur Kaltwasser, Legionellen" + Mini-Import | Abgeleitete Felder gefuellt und GELB | |

## C. Ergebnisliste und Lernen

| # | Schritt | Erwartung | OK |
|---|---|---|---|
| C1 | Gelbe Zelle direkt korrigieren | Gelb verschwindet; keine Fehlermeldung | |
| C2 | Gleichartiges Dokument erneut importieren | Korrigierter Wert wird vorgeschlagen (gelb) | |
| C3 | `Probenstelle hinzufuegen`, Werte tippen | Neue Zeile am Ende; Reihenfolge fortlaufend | |
| C4 | `Probenstelle loeschen` auf erkannter Zeile | Zeile weg; Folgeimport desselben Dokuments meldet die Zeile weiterhin (einzelnes Negativbeispiel reicht nicht fuer Unterdrueckung) | |
| C5 | `Rueckgaengig (1 Schritt)` nach Zellkorrektur | Alter Wert und ggf. Gelb kehren zurueck | |
| C6 | `Rueckgaengig` nach Zeile loeschen / hinzufuegen | Zeile kehrt zurueck bzw. verschwindet | |
| C7 | Sortieren Bez1-Etage-Raum, dann Quellreihenfolge | KG/UG vor EG vor 1./2./10. OG (natuerlich sortiert); Wiederherstellung exakt | |
| C8 | Formel-Test: `=1+1` in Zelle tippen | Erscheint als TEXT `=1+1`, wird nicht gerechnet | |

## D. Copy-and-paste und Export

| # | Schritt | Erwartung | OK |
|---|---|---|---|
| D1 | `Bez2 kopieren`, in Editor einfuegen | Nur Werte, keine Ueberschrift; leere Zellen als leere Zeilen; Zeilenzahl = Tabellenzeilen | |
| D2 | Alle 5 Spalten-Buttons nacheinander, jeweils einfuegen | Alle fuenf Spalten zeilen-synchron | |
| D3 | Bereich markieren, Strg+C, woanders einfuegen | Normales Excel-Kopierverhalten unveraendert | |
| D4 | Strg+C ausserhalb der Ergebnistabelle (z. B. Blatt Assistent) | Voellig normales Verhalten | |
| D5 | `CSV-Export (5 Dateien)` | 5 Dateien im Ordner der ZUERST importierten Datei; ohne Header; CRLF; Leerzeilen an gleicher Position; erneuter Export ueberschreibt | |
| D6 | Export mit Kodierung Windows-1252 wiederholen | Umlaute korrekt einbytig (Editor/Hexdump) | |
| D7 | UTF-8-Datei im Hexeditor | Beginnt mit `EF BB BF` (BOM) | |

## E. Parallelzugriff und Robustheit

| # | Schritt | Erwartung | OK |
|---|---|---|---|
| E1 | Zweiter PC oeffnet die XLSM, waehrend PC 1 arbeitet | PC 2 startet NUR LESEND mit klarer Meldung inkl. Haltername | |
| E2 | PC 1 schliesst; PC 2 oeffnet erneut | PC 2 erhaelt Schreibmodus; Lernstand von PC 1 vorhanden | |
| E3 | Stale-Lock: PC 1 hart beenden (Taskmanager), 15 Min warten, PC 2 oeffnen | Rueckfrage zur Lock-Uebernahme; erst nach "Ja" Schreibmodus | |
| E4 | Netzwerk waehrend der Arbeit trennen, weiterarbeiten, schliessen | Kein Datenverlust; Hinweis; naechster Start mit Netz synchronisiert ("Ausstehender lokaler Stand ...") | |
| E5 | Nach Schliessen: `%LOCALAPPDATA%\LIMS-Probenassistent\tmp` und `jobs` pruefen | Keine Originaldokumente, keine verwaisten Jobreste | |
| E6 | Gemeinsamen Ordner pruefen | Keine Originaldokumente; nur XLSM, config, core\, lock\, data\ | |

## F. Leistung (Ziel-PC)

| # | Schritt | Erwartung | OK |
|---|---|---|---|
| F1 | Typische PDF (ca. 60 Probenstellen, Scan) analysieren, Zeit stoppen | <= ca. 2 Minuten; sonst messbare Abweichung dokumentieren | |
| F2 | Task-Manager waehrend Analyse | Excel + lims_core zusammen stabil deutlich unter 16 GB | |

Abnahmeprotokoll (Datum, Excel-Buildnummer 2016 x64, Windows-Build,
Tester, Befunde) unter `docs/abnahmen/` ablegen.
