# Excel-/VBA-Tests

Automatisiert (laufen in `core/tests`, plattformneutral):

- `test_vba_lint.py` - statischer Lint aller Textmodule: Option Explicit,
  PtrSafe im VBA7-Zweig, verbotene Muster (Kill/DeleteFile/
  ExecuteExcel4Macro/zweite Excel-Instanz), Existenz aller
  OnAction-/OnKey-/OnTime-Ziele als Public Subs.
- Sortier- und Kopierlogik der VBA-Seite ist 1:1 aus dem Kern gespiegelt
  und dort getestet (`normalize/order.py` <-> `modErgebnisse.SortKeyText`,
  `export/clipboard_text.py` <-> `modCopyConfirm`).

Manuell (Zielplattform, echtes Excel 2016 x64):

- vollstaendige Checkliste in `docs/ABNAHME_EXCEL2016.md` - inklusive
  VBA-Compile, Buttons, Strg+C, Undo, Lock/Parallelstart, Export und
  Leistungsmessung. VBA laesst sich ohne Excel nicht ausfuehren; dieses
  Gate ist bewusst als realer Windows-Lauf dokumentiert.
