Attribute VB_Name = "modUndo"
Option Explicit

' =====================================================================
' modUndo - genau EINE eigene reversible Aktion (Zelle oder Zeile).
' VBA-Aktionen loeschen die normale Excel-Undo-Historie; deshalb pflegt
' die Anwendung diesen einen Schritt selbst und kompensiert ihn auch
' lernseitig ueber den Undo-Vertrag des Rechenkerns.
' =====================================================================

Private Const KIND_NONE As Long = 0
Private Const KIND_CELL As Long = 1
Private Const KIND_ROW_ADD As Long = 2
Private Const KIND_ROW_DEL As Long = 3

Private mKind As Long
Private mCellAddress As String
Private mOldValue As String
Private mNewValue As String
Private mWasYellow As Boolean
Private mRowKey As String
Private mRowSnapshot(1 To 7) As String

Public Sub ClearBuffer()
    mKind = KIND_NONE
End Sub

Public Sub RememberCellChange(ByVal address As String, ByVal oldVal As String, _
    ByVal newVal As String, ByVal wasYellow As Boolean)
    mKind = KIND_CELL
    mCellAddress = address
    mOldValue = oldVal
    mNewValue = newVal
    mWasYellow = wasYellow
End Sub

Public Sub RememberRowAdd(ByVal rowKey As String)
    mKind = KIND_ROW_ADD
    mRowKey = rowKey
End Sub

Public Sub RememberRowDelete(ByRef snapshot() As String)
    Dim c As Long
    mKind = KIND_ROW_DEL
    For c = 1 To 7
        mRowSnapshot(c) = snapshot(c)
    Next c
    mRowKey = snapshot(modErgebnisse.COL_ROWKEY)
End Sub

Public Sub UndoLast()
    If modConfig.IsReadOnlyMode() Then
        modAssistent.ShowError "Nur-Lese-Modus: Rueckgaengig nicht moeglich."
        Exit Sub
    End If
    Select Case mKind
        Case KIND_CELL
            UndoCell
        Case KIND_ROW_ADD
            UndoRowAdd
        Case KIND_ROW_DEL
            UndoRowDelete
        Case Else
            modAssistent.ShowStatus "Nichts rueckgaengig zu machen."
            Exit Sub
    End Select
    SendUndoToCore
    ClearBuffer
End Sub

Private Sub UndoCell()
    Dim ws As Worksheet, cell As Range
    Set ws = modErgebnisse.ResultSheet()
    Set cell = ws.Range(mCellAddress)
    modErgebnisse.SuspendEvents
    cell.NumberFormat = "@"
    cell.Value = mOldValue
    If mWasYellow Then
        cell.Interior.Color = COLOR_UNSICHER
    Else
        cell.Interior.ColorIndex = xlColorIndexNone
    End If
    modErgebnisse.ResumeEvents
    modAssistent.ShowStatus "Zellaenderung rueckgaengig gemacht."
End Sub

Private Sub UndoRowAdd()
    Dim lo As ListObject, i As Long
    Set lo = modErgebnisse.ResultTable()
    If lo.DataBodyRange Is Nothing Then Exit Sub
    modErgebnisse.SuspendEvents
    For i = lo.ListRows.Count To 1 Step -1
        If CStr(lo.DataBodyRange.Cells(i, modErgebnisse.COL_ROWKEY).Value) = mRowKey Then
            lo.ListRows(i).Delete
            Exit For
        End If
    Next i
    modErgebnisse.ResumeEvents
    modAssistent.ShowStatus "Hinzugefuegte Zeile entfernt."
End Sub

Private Sub UndoRowDelete()
    Dim lo As ListObject, lr As ListRow, c As Long
    Set lo = modErgebnisse.ResultTable()
    modErgebnisse.SuspendEvents
    Set lr = lo.ListRows.Add
    lr.Range.NumberFormat = "@"
    For c = 1 To 7
        lr.Range.Cells(1, c).Value = mRowSnapshot(c)
    Next c
    modErgebnisse.ResumeEvents
    modAssistent.ShowStatus "Geloeschte Zeile wiederhergestellt."
End Sub

Private Sub SendUndoToCore()
    Dim payload As String, resp As Object
    If Len(modConfig.SessionId()) = 0 Then Exit Sub
    payload = "{""session_id"":" & modJson.JStr(modConfig.SessionId()) & _
        ",""client_event_id"":" & modJson.JStr(modConfig.NewGuid()) & "}"
    Set resp = modJobClient.RunJobAndWait("undo", payload, 30)
    If Not modJobClient.IsOk(resp) Then
        modAssistent.ShowError "Undo im Lernspeicher fehlgeschlagen: " & _
            modJobClient.ErrorMessage(resp)
    End If
End Sub
