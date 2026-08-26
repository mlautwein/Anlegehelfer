VERSION 1.0 CLASS
BEGIN
  MultiUse = -1  'True
END
Attribute VB_Name = "SheetErgebnisse"
Attribute VB_GlobalNameSpace = False
Attribute VB_Creatable = False
Attribute VB_PredeclaredId = True
Attribute VB_Exposed = True
Option Explicit

' Code-Behind des Blatts "Ergebnisse" (CodeName: SheetErgebnisse).
' Direkte Zellkorrekturen werden erkannt, ohne normale Excel-Eingabe
' unbrauchbar zu machen; nur Aenderungen INNERHALB der Tabelle zaehlen.

Private Sub Worksheet_SelectionChange(ByVal Target As Range)
    modErgebnisse.CaptureOldValues Target
End Sub

Private Sub Worksheet_Change(ByVal Target As Range)
    modErgebnisse.HandleChange Target
End Sub
