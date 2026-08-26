# Workbook-Vorlage

Die zentrale XLSM ist ein Buildartefakt - die einzige Quelle sind die
Textmodule unter `../vba-src/`. Es wird bewusst KEINE binaere .xlsm im
Repository gefuehrt (Versionierbarkeit, Diff-Faehigkeit, Review).

Erzeugung:

- automatisch: `packaging/windows/build_workbook.ps1` (Excel-COM;
  benoetigt einmalig den Trust-Center-Haken "Zugriff auf das
  VBA-Projektobjektmodell vertrauen" - dokumentiert in docs/EXCEL_SETUP.md)
- manuell: Schrittfolge in `docs/EXCEL_SETUP.md`, Weg B (ca. 5 Minuten;
  `modSetup.EnsureUi` baut Blaetter, Tabelle und alle Schaltflaechen
  idempotent auf)

Beispielkonfiguration fuer den gemeinsamen Ordner: `config.beispiel.json`
(neben die XLSM kopieren und als `config.json` anpassen).
