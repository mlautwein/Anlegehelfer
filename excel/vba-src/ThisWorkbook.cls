VERSION 1.0 CLASS
BEGIN
  MultiUse = -1  'True
END
Attribute VB_Name = "ThisWorkbook"
Attribute VB_GlobalNameSpace = False
Attribute VB_Creatable = False
Attribute VB_PredeclaredId = True
Attribute VB_Exposed = True
Option Explicit

' Die zentrale Arbeitsmappe startet bei jedem Oeffnen mit leerer
' Ergebnisliste und erwirbt den exklusiven Schreib-Lock (modMain).

Private Sub Workbook_Open()
    On Error GoTo fail
    modMain.AppOpen
    Exit Sub
fail:
    MsgBox "Start fehlgeschlagen: " & Err.Description, vbExclamation, "LIMS-Probenassistent"
End Sub

Private Sub Workbook_BeforeClose(Cancel As Boolean)
    On Error Resume Next
    modMain.AppClose
End Sub

Private Sub Workbook_SheetActivate(ByVal Sh As Object)
    If Sh.Name = RESULT_SHEET Then
        modCopyConfirm.HookCopyKey
    Else
        modCopyConfirm.UnhookCopyKey
    End If
End Sub

Private Sub Workbook_SheetDeactivate(ByVal Sh As Object)
    If Sh.Name = RESULT_SHEET Then
        modCopyConfirm.UnhookCopyKey   ' Strg+C garantiert zurueckgesetzt
    End If
End Sub
