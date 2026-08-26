# Bedienung (Anwenderleitfaden)

## Start

Die zentrale Arbeitsmappe `LIMS-Probenassistent.xlsm` aus dem gemeinsamen
Ordner oeffnen. Beim Oeffnen wird die Ergebnisliste geleert und der
exklusive Schreibzugriff geholt. Arbeitet gerade jemand anderes mit der
Anwendung, startet die Mappe nur lesend und zeigt oben im Blatt
`Assistent` an, welcher Arbeitsplatz den Schreibzugriff haelt. Ein
veralteter Lock (z. B. nach Absturz) wird nur nach Rueckfrage uebernommen.

## Import

Im Blatt `Assistent`:

1. **Dateien waehlen** - PDF, Bilder (JPG/PNG/HEIC) und Excel-Dateien in
   beliebiger Mischung. Mehrere Bilder bilden zusammen EINEN Import; ihre
   Reihenfolge steht in Spalte "Bild-Reihenfolge" und kann durch Aendern
   der Nummern angepasst werden.
2. Bei Excel-Dateien: Zeile der Datei anklicken und **Blaetter waehlen**
   druecken. Die sichtbaren Blattnamen erscheinen als Komma-Liste in
   Spalte D - unerwuenschte Blaetter einfach aus der Liste loeschen.
   Makros aus Quelldateien werden grundsaetzlich nicht ausgefuehrt.
3. Optional **Zusatzinformationen** eintragen (z. B. "Haus B, nur
   Kaltwasser, Legionellen"). Der Text gilt nur fuer diesen Import und ist
   ein Hinweis, keine Wahrheit: daraus abgeleitete Werte sind gelb.
4. **Analyse starten**. Der Fortschritt erscheint unten; **Abbrechen** ist
   jederzeit moeglich und laesst keine halben Zeilen zurueck. Weitere
   Importe werden an dieselbe Liste angehaengt; doppelte Probenstellen
   bleiben absichtlich erhalten.

## Ergebnisse pruefen und korrigieren

Im Blatt `Ergebnisse` stehen genau fuenf Spalten: `Bez1`, `Bez2`, `B3`,
`B4`, `Untersuchungsart`. Gelbe Zellen bedeuten: unsicher oder nur
abgeleitet - bitte fachlich lesen. Werte werden direkt in den Zellen
korrigiert; mit der Korrektur verschwindet die gelbe Markierung und das
System lernt sofort daraus. Ein korrekter gelber Wert muss nicht extra
bestaetigt werden - Kopieren oder Export gilt als Bestaetigung.

Schaltflaechen: **Probenstelle hinzufuegen** (neue leere Zeile am Ende),
**Probenstelle loeschen** (markierte Zeile; bei automatisch erkannten
Zeilen lernt das System daraus, aehnliche Zeilen kuenftig nicht mehr zu
melden), **Rueckgaengig (1 Schritt)** fuer die letzte Zell- oder
Zeilenaenderung, **Sortieren Bez1-Etage-Raum** und **Quellreihenfolge**
zum Wiederherstellen der Dokumentreihenfolge.

## Uebernahme ins LIMS

Je LIMS-Feld gibt es einen Kopier-Button (`Bez1 kopieren` ... `Untersuchungsart
kopieren`). Kopiert wird die ganze Spalte zeilenweise ohne Ueberschrift;
leere Zellen bleiben leere Zeilen, damit die Zeilen aller fuenf Felder im
LIMS exakt untereinander bleiben. Normales Markieren und Strg+C innerhalb
der Tabelle funktioniert weiterhin wie gewohnt - bestaetigt werden dabei
nur die tatsaechlich markierten Zellen.

**CSV-Export (5 Dateien)** erzeugt `Bez1.csv`, `Bez2.csv`, `B3.csv`,
`B4.csv`, `Untersuchungsart.csv` im Ordner der zuerst importierten Datei -
eine Probe je Zeile, ohne Ueberschrift, alle fuenf Dateien zeilengleich.
Vorhandene Dateien werden automatisch ersetzt (erst nach vollstaendig
erfolgreichem Schreiben aller fuenf). Kodierung: UTF-8 mit BOM (Standard)
oder Windows-1252, umschaltbar im Blatt `Assistent`.

## Hinweise

- Die Arbeitsmappe startet immer mit leerer Liste; die Lerninhalte bleiben
  zentral erhalten und wachsen mit jeder Korrektur.
- Beim Schliessen synchronisiert die Anwendung den Datenstand in den
  gemeinsamen Ordner und gibt den Schreibzugriff frei. Bei Netzwerkproblemen
  bleibt der Stand lokal erhalten und wird beim naechsten Start nachgezogen.
- Original-PDFs und Bilder werden nicht dauerhaft kopiert.
