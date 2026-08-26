Attribute VB_Name = "modCopyConfirm"
Option Explicit

' =====================================================================
' modCopyConfirm - Spalten-Kopieren-Buttons und kontrolliertes Strg+C.
' Kopieren liefert Werte zeilenweise ohne Ueberschrift; leere Zellen
' bleiben leere Zeilen an identischer Position. Nur der tatsaechlich
' kopierte Umfang wird als Bestaetigung gelernt.
' =====================================================================

Public Sub CopyColBez1()
    CopyColumnAndConfirm modErgebnisse.COL_BEZ1
End Sub

Public Sub CopyColBez2()
    CopyColumnAndConfirm modErgebnisse.COL_BEZ2
End Sub

Public Sub CopyColB3()
    CopyColumnAndConfirm modErgebnisse.COL_B3
End Sub

Public Sub CopyColB4()
    CopyColumnAndConfirm modErgebnisse.COL_B4
End Sub

Public Sub CopyColUntersuchungsart()
    CopyColumnAndConfirm modErgebnisse.COL_UNT
End Sub

Private Sub CopyColumnAndConfirm(ByVal colIdx As Long)
    Dim vals() As String, rowKeys() As String
    Dim text As String, i As Long
    vals = modErgebnisse.ColumnValues(colIdx, rowKeys)
    On Error Resume Next
    If UBound(vals) < 1 Then
        modAssistent.ShowStatus "Keine Zeilen zum Kopieren."
        Exit Sub
    End If
    On Error GoTo 0
    text = ""
    For i = LBound(vals) To UBound(vals)
        If i > LBound(vals) Then text = text & vbCrLf
        text = text & vals(i)      ' leere Werte = leere Zeile (Position erhalten)
    Next i
    If Not modClipboard.SetClipboardText(text) Then
        modAssistent.ShowError "Zwischenablage konnte nicht beschrieben werden."
        Exit Sub
    End If
    modAssistent.ShowStatus "Spalte '" & modErgebnisse.FieldName(colIdx) & _
        "' kopiert (" & CStr(UBound(vals)) & " Zeilen)."
    ConfirmColumn colIdx, vals, rowKeys, "copy_column"
End Sub

Private Sub ConfirmColumn(ByVal colIdx As Long, ByRef vals() As String, _
    ByRef rowKeys() As String, ByVal confirmType As String)
    Dim cellsJson As String, i As Long, fname As String
    If Len(modConfig.SessionId()) = 0 Then Exit Sub
    fname = modErgebnisse.FieldName(colIdx)
    cellsJson = "["
    For i = LBound(vals) To UBound(vals)
        If Len(rowKeys(i)) = 0 Then GoTo nextItem
        If Len(cellsJson) > 1 Then cellsJson = cellsJson & ","
        cellsJson = cellsJson & "{""row_id"":" & modJson.JStr(rowKeys(i)) & _
            ",""field"":" & modJson.JStr(fname) & _
            ",""value"":" & modJson.JStr(vals(i)) & "}"
nextItem:
    Next i
    cellsJson = cellsJson & "]"
    If cellsJson = "[]" Then Exit Sub
    SendConfirm confirmType, cellsJson
End Sub

Private Sub SendConfirm(ByVal confirmType As String, ByVal cellsJson As String)
    Dim payload As String, resp As Object
    payload = "{""session_id"":" & modJson.JStr(modConfig.SessionId()) & _
        ",""confirmation_type"":" & modJson.JStr(confirmType) & _
        ",""cells"":" & cellsJson & _
        ",""client_event_id"":" & modJson.JStr(modConfig.NewGuid()) & "}"
    Set resp = modJobClient.RunJobAndWait("confirm_cells", payload, 30)
    ' Bestaetigungen sind Komfortsignale: Fehler nur leise in Statuszeile
    If Not modJobClient.IsOk(resp) Then
        modAssistent.ShowStatus "Hinweis: Bestaetigung nicht gespeichert."
    End If
End Sub

' ------------------------------------------------------------ Strg+C

Public Sub HookCopyKey()
    Application.OnKey "^c", "CopySelectionConfirm"
End Sub

Public Sub UnhookCopyKey()
    Application.OnKey "^c"     ' Standardverhalten garantiert zuruecksetzen
End Sub

Public Sub CopySelectionConfirm()
    ' Nur bei aktiver Ergebnisliste umgebogen; sonst normales Kopieren.
    Dim lo As ListObject, sel As Range, hit As Range, cell As Range
    Dim cellsJson As String, colIdx As Long, rowIdx As Long
    Dim rowKey As String, fname As String

    On Error GoTo fallback
    If ActiveSheet.Name <> RESULT_SHEET Then GoTo fallback
    Set sel = Selection
    Set lo = modErgebnisse.ResultTable()
    If lo.DataBodyRange Is Nothing Then GoTo fallback
    Set hit = Application.Intersect(sel, lo.DataBodyRange)
    If hit Is Nothing Then GoTo fallback

    sel.Copy      ' normales Excel-Kopieren bleibt vollstaendig erhalten

    cellsJson = "["
    Dim n As Long
    For Each cell In hit.Cells
        colIdx = cell.Column - lo.Range.Column + 1
        If colIdx >= modErgebnisse.COL_BEZ1 And colIdx <= modErgebnisse.COL_UNT Then
            rowIdx = cell.Row - lo.DataBodyRange.Row + 1
            rowKey = CStr(lo.DataBodyRange.Cells(rowIdx, modErgebnisse.COL_ROWKEY).Value)
            fname = modErgebnisse.FieldName(colIdx)
            If Len(rowKey) > 0 Then
                If Len(cellsJson) > 1 Then cellsJson = cellsJson & ","
                cellsJson = cellsJson & "{""row_id"":" & modJson.JStr(rowKey) & _
                    ",""field"":" & modJson.JStr(fname) & _
                    ",""value"":" & modJson.JStr(modErgebnisse.SanitizeValue(cell.Value)) & "}"
                n = n + 1
                If n >= 400 Then Exit For
            End If
        End If
    Next cell
    cellsJson = cellsJson & "]"
    If cellsJson <> "[]" And Len(modConfig.SessionId()) > 0 Then
        SendConfirm "copy_selection", cellsJson
    End If
    Exit Sub

fallback:
    On Error Resume Next
    Selection.Copy
End Sub
