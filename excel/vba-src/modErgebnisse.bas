Attribute VB_Name = "modErgebnisse"
Option Explicit

' =====================================================================
' modErgebnisse - Ergebnistabelle: genau fuenf sichtbare Fachspalten
' (Bez1, Bez2, B3, B4, Untersuchungsart) + zwei ausgeblendete
' Technikspalten (RowKey, SrcOrd). Nur unsichere Zellen sind gelb.
' =====================================================================

Public Const COL_BEZ1 As Long = 1
Public Const COL_BEZ2 As Long = 2
Public Const COL_B3 As Long = 3
Public Const COL_B4 As Long = 4
Public Const COL_UNT As Long = 5
Public Const COL_ROWKEY As Long = 6
Public Const COL_SRCORD As Long = 7

Private mEventsOff As Boolean
Private mOldValues As Object      ' Adresse -> alter Wert (fuer Revision/Undo)

Public Function FieldName(ByVal colIndex As Long) As String
    Select Case colIndex
        Case COL_BEZ1: FieldName = "Bez1"
        Case COL_BEZ2: FieldName = "Bez2"
        Case COL_B3: FieldName = "B3"
        Case COL_B4: FieldName = "B4"
        Case COL_UNT: FieldName = "Untersuchungsart"
        Case Else: FieldName = ""
    End Select
End Function

Public Function ResultSheet() As Worksheet
    Set ResultSheet = ThisWorkbook.Worksheets(RESULT_SHEET)
End Function

Public Function ResultTable() As ListObject
    Set ResultTable = ResultSheet().ListObjects(RESULT_TABLE)
End Function

Public Property Get EventsOff() As Boolean
    EventsOff = mEventsOff
End Property

Public Sub SuspendEvents()
    mEventsOff = True
End Sub

Public Sub ResumeEvents()
    mEventsOff = False
End Sub

Public Function SanitizeValue(ByVal v As Variant) As String
    Dim s As String
    s = CStr(v)
    s = Replace(s, vbCrLf, " ")
    s = Replace(s, vbCr, " ")
    s = Replace(s, vbLf, " ")
    s = Replace(s, vbTab, " ")
    Do While InStr(s, "  ") > 0
        s = Replace(s, "  ", " ")
    Loop
    SanitizeValue = Trim$(s)
End Function

' ------------------------------------------------------------ Leeren

Public Sub ClearResults()
    Dim lo As ListObject
    Set lo = ResultTable()
    SuspendEvents
    On Error GoTo done
    If Not lo.DataBodyRange Is Nothing Then
        lo.DataBodyRange.Delete
    End If
done:
    ResumeEvents
    modUndo.ClearBuffer
End Sub

' ------------------------------------------------------------ Ergebnisuebernahme

Public Sub AppendAnalyzeRows(ByVal rowsColl As Object)
    ' rowsColl: Collection von Dictionaries (row_id, source_order, fields)
    Dim lo As ListObject, lr As ListRow
    Dim rowObj As Object, fields As Object, fv As Object
    Dim c As Long, fname As String
    Set lo = ResultTable()
    SuspendEvents
    Application.ScreenUpdating = False
    On Error GoTo done
    Dim item As Variant
    For Each item In rowsColl
        Set rowObj = item
        Set fields = rowObj("fields")
        Set lr = lo.ListRows.Add
        lr.Range.NumberFormat = "@"           ' immer Text, nie Formeln
        For c = COL_BEZ1 To COL_UNT
            fname = FieldName(c)
            Set fv = fields(fname)
            lr.Range.Cells(1, c).Value = modJson.DictGetStr(fv, "value", "")
            If modJson.DictGetBool(fv, "is_uncertain", False) Then
                lr.Range.Cells(1, c).Interior.Color = COLOR_UNSICHER
            Else
                lr.Range.Cells(1, c).Interior.ColorIndex = xlColorIndexNone
            End If
        Next c
        lr.Range.Cells(1, COL_ROWKEY).Value = modJson.DictGetStr(rowObj, "row_id", "")
        lr.Range.Cells(1, COL_SRCORD).Value = CStr(rowObj("source_order"))
    Next item
done:
    Application.ScreenUpdating = True
    ResumeEvents
End Sub

' ------------------------------------------------------------ Zeilen hinzufuegen/loeschen

Public Sub AddSampleRow()
    Dim lo As ListObject, lr As ListRow
    Dim rowKey As String, srcOrd As Long
    If modConfig.IsReadOnlyMode() Then
        modAssistent.ShowError "Nur-Lese-Modus: Ein anderer Arbeitsplatz haelt den Schreibzugriff."
        Exit Sub
    End If
    Set lo = ResultTable()
    rowKey = modConfig.NewGuid()
    srcOrd = NextSourceOrder()
    SuspendEvents
    Set lr = lo.ListRows.Add
    lr.Range.NumberFormat = "@"
    lr.Range.Cells(1, COL_ROWKEY).Value = rowKey
    lr.Range.Cells(1, COL_SRCORD).Value = CStr(srcOrd)
    ResumeEvents

    modUndo.RememberRowAdd rowKey
    QueueRowEvent rowKey, "add", lr, srcOrd
    lr.Range.Cells(1, COL_BEZ1).Select
End Sub

Public Sub DeleteSampleRow()
    Dim lo As ListObject, lr As ListRow
    Dim idx As Long, rowKey As String
    Dim snapshot(1 To 7) As String, c As Long
    If modConfig.IsReadOnlyMode() Then
        modAssistent.ShowError "Nur-Lese-Modus: Ein anderer Arbeitsplatz haelt den Schreibzugriff."
        Exit Sub
    End If
    Set lo = ResultTable()
    idx = SelectedDataRowIndex()
    If idx = 0 Then
        modAssistent.ShowError "Bitte zuerst eine Zeile in der Ergebnistabelle markieren."
        Exit Sub
    End If
    Set lr = lo.ListRows(idx)
    For c = 1 To 7
        snapshot(c) = CStr(lr.Range.Cells(1, c).Value)
    Next c
    rowKey = snapshot(COL_ROWKEY)

    modUndo.RememberRowDelete snapshot
    QueueRowEvent rowKey, "delete", lr, CLng(Val(snapshot(COL_SRCORD)))

    SuspendEvents
    lr.Delete
    ResumeEvents
End Sub

Private Sub QueueRowEvent(ByVal rowKey As String, ByVal action As String, _
    ByVal lr As ListRow, ByVal srcOrd As Long)
    Dim payload As String, valuesJson As String, c As Long
    valuesJson = "{"
    For c = COL_BEZ1 To COL_UNT
        If c > COL_BEZ1 Then valuesJson = valuesJson & ","
        valuesJson = valuesJson & modJson.JStr(FieldName(c)) & ":" & _
            modJson.JStr(SanitizeValue(lr.Range.Cells(1, c).Value))
    Next c
    valuesJson = valuesJson & "}"
    payload = "{""session_id"":" & modJson.JStr(modConfig.SessionId()) & _
        ",""row_id"":" & modJson.JStr(rowKey) & _
        ",""action"":" & modJson.JStr(action) & _
        ",""values"":" & valuesJson & _
        ",""source_order"":" & CStr(srcOrd) & _
        ",""client_event_id"":" & modJson.JStr(modConfig.NewGuid()) & "}"
    Dim resp As Object
    Set resp = modJobClient.RunJobAndWait("row_event", payload, 30)
    If Not modJobClient.IsOk(resp) Then
        modAssistent.ShowError "Zeilenereignis nicht gespeichert: " & modJobClient.ErrorMessage(resp)
    End If
End Sub

Public Function SelectedDataRowIndex() As Long
    Dim lo As ListObject, sel As Range, hit As Range
    Set lo = ResultTable()
    If lo.DataBodyRange Is Nothing Then Exit Function
    On Error Resume Next
    Set sel = Selection
    On Error GoTo 0
    If sel Is Nothing Then Exit Function
    Set hit = Application.Intersect(sel, lo.DataBodyRange)
    If hit Is Nothing Then Exit Function
    SelectedDataRowIndex = hit.Cells(1, 1).Row - lo.DataBodyRange.Row + 1
End Function

Public Function NextSourceOrder() As Long
    Dim lo As ListObject, r As Range, maxOrd As Long, v As Variant
    Set lo = ResultTable()
    maxOrd = 0
    If Not lo.DataBodyRange Is Nothing Then
        For Each r In lo.ListColumns(COL_SRCORD).DataBodyRange.Cells
            v = Val(CStr(r.Value))
            If v > maxOrd Then maxOrd = v
        Next r
    End If
    NextSourceOrder = maxOrd + 1
End Function

' ------------------------------------------------------------ Aenderungserkennung

Public Sub CaptureOldValues(ByVal target As Range)
    Dim lo As ListObject, hit As Range, cell As Range, n As Long
    If mEventsOff Then Exit Sub
    Set mOldValues = CreateObject("Scripting.Dictionary")
    On Error Resume Next
    Set lo = ResultTable()
    On Error GoTo 0
    If lo Is Nothing Then Exit Sub
    If lo.DataBodyRange Is Nothing Then Exit Sub
    Set hit = Application.Intersect(target, lo.DataBodyRange)
    If hit Is Nothing Then Exit Sub
    For Each cell In hit.Cells
        mOldValues(cell.Address) = CStr(cell.Value)
        n = n + 1
        If n >= 400 Then Exit For
    Next cell
End Sub

Public Sub HandleChange(ByVal target As Range)
    Dim lo As ListObject, hit As Range, cell As Range
    Dim oldVal As String, newVal As String, fname As String
    Dim rowKey As String, colIdx As Long
    If mEventsOff Then Exit Sub
    On Error Resume Next
    Set lo = ResultTable()
    On Error GoTo 0
    If lo Is Nothing Then Exit Sub
    If lo.DataBodyRange Is Nothing Then Exit Sub
    Set hit = Application.Intersect(target, lo.DataBodyRange)
    If hit Is Nothing Then Exit Sub
    If modConfig.IsReadOnlyMode() Then Exit Sub

    Dim changedCount As Long
    For Each cell In hit.Cells
        colIdx = cell.Column - lo.Range.Column + 1
        If colIdx >= COL_BEZ1 And colIdx <= COL_UNT Then
            fname = FieldName(colIdx)
            newVal = SanitizeValue(cell.Value)
            oldVal = ""
            If Not mOldValues Is Nothing Then
                If mOldValues.Exists(cell.Address) Then oldVal = CStr(mOldValues(cell.Address))
            End If
            If newVal <> CStr(cell.Value) Then
                SuspendEvents
                cell.Value = newVal          ' Umbrueche/Tabs deterministisch bereinigt
                ResumeEvents
            End If
            If newVal <> oldVal Then
                Dim wasYellow As Boolean
                wasYellow = (cell.Interior.Color = COLOR_UNSICHER)
                SuspendEvents
                cell.Interior.ColorIndex = xlColorIndexNone   ' Korrektur ist nicht mehr unsicher
                ResumeEvents
                rowKey = CStr(lo.DataBodyRange.Cells(cell.Row - lo.DataBodyRange.Row + 1, COL_ROWKEY).Value)
                modUndo.RememberCellChange cell.Address, oldVal, newVal, wasYellow
                SendRevision rowKey, fname, oldVal, newVal
                changedCount = changedCount + 1
                If changedCount >= 60 Then Exit For
            End If
        End If
    Next cell
End Sub

Private Sub SendRevision(ByVal rowKey As String, ByVal fname As String, _
    ByVal oldVal As String, ByVal newVal As String)
    If Len(rowKey) = 0 Then Exit Sub
    Dim payload As String, resp As Object
    payload = "{""session_id"":" & modJson.JStr(modConfig.SessionId()) & _
        ",""row_id"":" & modJson.JStr(rowKey) & _
        ",""field"":" & modJson.JStr(fname) & _
        ",""old_value"":" & modJson.JStr(oldVal) & _
        ",""new_value"":" & modJson.JStr(newVal) & _
        ",""client_event_id"":" & modJson.JStr(modConfig.NewGuid()) & "}"
    Set resp = modJobClient.RunJobAndWait("apply_revision", payload, 30)
    If Not modJobClient.IsOk(resp) Then
        modAssistent.ShowError "Korrektur nicht gespeichert: " & modJobClient.ErrorMessage(resp)
    End If
End Sub

' ------------------------------------------------------------ Sortierung
' Spiegelt exakt core/src/lims_assistant/normalize/order.py

Public Sub SortByBez1EtageRaum()
    ApplySort False
End Sub

Public Sub RestoreSourceOrder()
    ApplySort True
End Sub

Private Sub ApplySort(ByVal bySourceOrder As Boolean)
    Dim lo As ListObject, n As Long, i As Long, j As Long, c As Long
    Set lo = ResultTable()
    If lo.DataBodyRange Is Nothing Then Exit Sub
    n = lo.ListRows.Count
    If n < 2 Then Exit Sub

    Dim vals() As String, fills() As Long, keys() As String
    ReDim vals(1 To n, 1 To 7)
    ReDim fills(1 To n, 1 To 5)
    ReDim keys(1 To n)
    For i = 1 To n
        For c = 1 To 7
            vals(i, c) = CStr(lo.DataBodyRange.Cells(i, c).Value)
        Next c
        For c = 1 To 5
            If lo.DataBodyRange.Cells(i, c).Interior.Color = COLOR_UNSICHER And _
               lo.DataBodyRange.Cells(i, c).Interior.ColorIndex <> xlColorIndexNone Then
                fills(i, c) = 1
            Else
                fills(i, c) = 0
            End If
        Next c
        If bySourceOrder Then
            keys(i) = Right$("000000000" & CStr(CLng(Val(vals(i, COL_SRCORD)))), 9)
        Else
            keys(i) = SortKeyText(vals(i, COL_BEZ1), vals(i, COL_BEZ2))
        End If
    Next i

    ' stabile Sortierung (Insertion Sort ueber Indizes)
    Dim order() As Long
    ReDim order(1 To n)
    For i = 1 To n
        order(i) = i
    Next i
    Dim tmp As Long
    For i = 2 To n
        tmp = order(i)
        j = i - 1
        Do While j >= 1
            If keys(order(j)) > keys(tmp) Then
                order(j + 1) = order(j)
                j = j - 1
            Else
                Exit Do
            End If
        Loop
        order(j + 1) = tmp
    Next i

    SuspendEvents
    Application.ScreenUpdating = False
    For i = 1 To n
        For c = 1 To 7
            lo.DataBodyRange.Cells(i, c).Value = vals(order(i), c)
        Next c
        For c = 1 To 5
            If fills(order(i), c) = 1 Then
                lo.DataBodyRange.Cells(i, c).Interior.Color = COLOR_UNSICHER
            Else
                lo.DataBodyRange.Cells(i, c).Interior.ColorIndex = xlColorIndexNone
            End If
        Next c
    Next i
    Application.ScreenUpdating = True
    ResumeEvents
    modUndo.ClearBuffer   ' Sortierung ist nicht Teil des Ein-Schritt-Undo
End Sub

Public Function SortKeyText(ByVal bez1 As String, ByVal bez2 As String) As String
    Dim etage As String, rest As String
    SplitBez2 bez2, etage, rest
    SortKeyText = NaturalKey(bez1) & "|" & EtageRankText(etage) & "|" & NaturalKey(rest)
End Function

Public Sub SplitBez2(ByVal bez2 As String, ByRef etage As String, ByRef rest As String)
    Dim p As Long, head As String
    etage = ""
    rest = Trim$(bez2)
    p = InStr(rest, ",")
    If p > 0 Then
        head = Trim$(Left$(rest, p - 1))
    Else
        head = rest
    End If
    If IsEtageToken(head) Then
        etage = head
        If p > 0 Then
            rest = Trim$(Mid$(rest, p + 1))
        Else
            rest = ""
        End If
    End If
End Sub

Private Function IsEtageToken(ByVal s As String) As Boolean
    Dim u As String
    u = UCase$(Trim$(s))
    If u = "EG" Or u = "UG" Or u = "KG" Or u = "DG" Or u = "ZG" Then
        IsEtageToken = True
    ElseIf u Like "#. OG" Or u Like "##. OG" Or u Like "#. UG" Or u Like "##. UG" Then
        IsEtageToken = True
    ElseIf u Like "EBENE #" Or u Like "EBENE ##" Or u Like "EBENE ###" Then
        IsEtageToken = True
    End If
End Function

Public Function EtageRankText(ByVal etage As String) As String
    ' vergleichbarer Text: 5-stellig mit Offset 10000 (KG=-90 ... DG=900)
    Dim u As String, rank As Long
    u = UCase$(Trim$(etage))
    If Len(u) = 0 Then
        rank = 10000
    ElseIf u = "KG" Then
        rank = -90
    ElseIf u = "UG" Then
        rank = -1
    ElseIf u = "EG" Then
        rank = 0
    ElseIf u = "DG" Then
        rank = 900
    ElseIf u = "ZG" Then
        rank = 50
    ElseIf u Like "*. OG" Then
        rank = CLng(Val(u))
    ElseIf u Like "*. UG" Then
        rank = -CLng(Val(u))
    ElseIf u Like "EBENE *" Then
        rank = CLng(Val(Mid$(u, 7)))
    Else
        rank = 5000
    End If
    EtageRankText = Right$("00000" & CStr(rank + 10000), 5) & "_" & u
End Function

Public Function NaturalKey(ByVal s As String) As String
    ' Zahlenlaeufe auf 9 Stellen auffuellen -> Textvergleich = natuerliche Ordnung
    Dim out As String, i As Long, ch As String, numBuf As String
    s = LCase$(Trim$(s))
    For i = 1 To Len(s)
        ch = Mid$(s, i, 1)
        If ch >= "0" And ch <= "9" Then
            numBuf = numBuf & ch
        Else
            If Len(numBuf) > 0 Then
                out = out & Right$("000000000" & numBuf, 9)
                numBuf = ""
            End If
            out = out & ch
        End If
    Next i
    If Len(numBuf) > 0 Then out = out & Right$("000000000" & numBuf, 9)
    NaturalKey = out
End Function

' ------------------------------------------------------------ Datenzugriff fuer Copy/Export

Public Function ColumnValues(ByVal colIdx As Long, ByRef rowKeys() As String) As String()
    Dim lo As ListObject, n As Long, i As Long
    Dim vals() As String
    Set lo = ResultTable()
    If lo.DataBodyRange Is Nothing Then
        ReDim vals(0 To -1)
        ColumnValues = vals
        Exit Function
    End If
    n = lo.ListRows.Count
    ReDim vals(1 To n)
    ReDim rowKeys(1 To n)
    For i = 1 To n
        vals(i) = SanitizeValue(lo.DataBodyRange.Cells(i, colIdx).Value)
        rowKeys(i) = CStr(lo.DataBodyRange.Cells(i, COL_ROWKEY).Value)
    Next i
    ColumnValues = vals
End Function
