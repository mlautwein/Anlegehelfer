Attribute VB_Name = "modAssistent"
Option Explicit

' =====================================================================
' modAssistent - Blatt "Assistent": Dateiauswahl, Bildreihenfolge,
' Excel-Blattauswahl, Zusatzinformationen, Kodierung, Start/Abbruch,
' knapper Fortschritt und Fehlermeldungen.
' Analyse laeuft asynchron: Application.OnTime pollt progress.json.
' =====================================================================

Public Const FILES_FIRST_ROW As Long = 8
Public Const CELL_STATUS As String = "B5"
Public Const CELL_LOCKINFO As String = "B4"
Public Const CELL_HINT As String = "B31"
Public Const CELL_ENCODING As String = "B33"
Public Const CELL_PROGRESS As String = "B35"
Public Const CELL_ERROR As String = "B36"

Private mJobDir As String
Private mPolling As Boolean
Private mNextPoll As Date

Public Function AssistSheet() As Worksheet
    Set AssistSheet = ThisWorkbook.Worksheets(ASSIST_SHEET)
End Function

Public Sub ShowStatus(ByVal msg As String)
    On Error Resume Next
    AssistSheet().Range(CELL_PROGRESS).Value = msg
End Sub

Public Sub ShowError(ByVal msg As String)
    On Error Resume Next
    AssistSheet().Range(CELL_ERROR).Value = msg
    If Len(msg) > 0 Then Beep
End Sub

Public Sub ClearError()
    ShowError ""
End Sub

Public Function SelectedEncoding() As String
    Dim v As String
    v = CStr(AssistSheet().Range(CELL_ENCODING).Value)
    If InStr(1, v, "1252", vbTextCompare) > 0 Then
        SelectedEncoding = "cp1252"
    Else
        SelectedEncoding = "utf8_bom"
    End If
End Function

' ------------------------------------------------------------ Dateiliste

Private Function FileTypeOf(ByVal path As String) As String
    Dim ext As String
    ext = LCase$(Mid$(path, InStrRev(path, ".") + 1))
    Select Case ext
        Case "pdf": FileTypeOf = "pdf"
        Case "jpg", "jpeg", "png", "heic": FileTypeOf = "bild"
        Case "xlsx", "xls", "xlsm": FileTypeOf = "excel"
        Case Else: FileTypeOf = ""
    End Select
End Function

Public Sub BtnDateienWaehlen()
    Dim fd As FileDialog, i As Long, ws As Worksheet
    Dim r As Long, ftype As String, imgSeq As Long
    ClearError
    If modConfig.IsReadOnlyMode() Then
        ShowError "Nur-Lese-Modus: Import nicht moeglich."
        Exit Sub
    End If
    Set ws = AssistSheet()
    Set fd = Application.FileDialog(msoFileDialogFilePicker)
    With fd
        .AllowMultiSelect = True
        .Title = "Dokumente fuer den Import waehlen"
        .Filters.Clear
        .Filters.Add "Alle unterstuetzten Dateien", "*.pdf;*.jpg;*.jpeg;*.png;*.heic;*.xlsx;*.xls;*.xlsm"
        .Filters.Add "PDF", "*.pdf"
        .Filters.Add "Bilder", "*.jpg;*.jpeg;*.png;*.heic"
        .Filters.Add "Excel", "*.xlsx;*.xls;*.xlsm"
        If .Show = 0 Then Exit Sub
        imgSeq = HighestImageOrder()
        For i = 1 To .SelectedItems.Count
            ftype = FileTypeOf(.SelectedItems(i))
            If Len(ftype) = 0 Then
                ShowError "Nicht unterstuetzt: " & .SelectedItems(i)
            Else
                r = NextFreeFileRow()
                If r = 0 Then
                    ShowError "Maximal " & MAX_DATEIEN & " Eintraege je Import."
                    Exit For
                End If
                ws.Cells(r, 1).Value = .SelectedItems(i)
                ws.Cells(r, 2).Value = ftype
                If ftype = "bild" Then
                    imgSeq = imgSeq + 1
                    ws.Cells(r, 3).Value = imgSeq   ' Reihenfolge aenderbar
                End If
                If ftype = "excel" Then
                    ws.Cells(r, 5).Value = "Blaetter waehlen ->"
                End If
            End If
        Next i
    End With
End Sub

Public Sub BtnListeLeeren()
    Dim ws As Worksheet
    Set ws = AssistSheet()
    ws.Range(ws.Cells(FILES_FIRST_ROW, 1), ws.Cells(FILES_FIRST_ROW + MAX_DATEIEN - 1, 5)).ClearContents
    ClearError
    ShowStatus ""
End Sub

Private Function NextFreeFileRow() As Long
    Dim ws As Worksheet, r As Long
    Set ws = AssistSheet()
    For r = FILES_FIRST_ROW To FILES_FIRST_ROW + MAX_DATEIEN - 1
        If Len(CStr(ws.Cells(r, 1).Value)) = 0 Then
            NextFreeFileRow = r
            Exit Function
        End If
    Next r
    NextFreeFileRow = 0
End Function

Private Function HighestImageOrder() As Long
    Dim ws As Worksheet, r As Long, v As Long
    Set ws = AssistSheet()
    For r = FILES_FIRST_ROW To FILES_FIRST_ROW + MAX_DATEIEN - 1
        If CStr(ws.Cells(r, 2).Value) = "bild" Then
            v = CLng(Val(CStr(ws.Cells(r, 3).Value)))
            If v > HighestImageOrder Then HighestImageOrder = v
        End If
    Next r
End Function

Public Sub BtnBlaetterWaehlen()
    ' Fuer die aktive Excel-Dateizeile die Blattliste vom Kern holen.
    Dim ws As Worksheet, r As Long, path As String
    Dim resp As Object, result As Object, sheetInfo As Object
    Dim names As String, item As Variant
    ClearError
    Set ws = AssistSheet()
    r = ActiveCell.Row
    If r < FILES_FIRST_ROW Or r >= FILES_FIRST_ROW + MAX_DATEIEN Then
        ShowError "Bitte zuerst die Zeile der Excel-Datei anklicken."
        Exit Sub
    End If
    path = CStr(ws.Cells(r, 1).Value)
    If CStr(ws.Cells(r, 2).Value) <> "excel" Or Len(path) = 0 Then
        ShowError "Die markierte Zeile enthaelt keine Excel-Datei."
        Exit Sub
    End If
    ShowStatus "Blaetter werden gelesen ..."
    Set resp = modJobClient.RunJobAndWait("list_sheets", _
        "{""source_path"":" & modJson.JStr(path) & "}", 45)
    If Not modJobClient.IsOk(resp) Then
        ShowError "Blattliste fehlgeschlagen: " & modJobClient.ErrorMessage(resp)
        Exit Sub
    End If
    Set result = resp("result")
    names = ""
    For Each item In result("sheets")
        Set sheetInfo = item
        If modJson.DictGetBool(sheetInfo, "visible", True) Then
            If Len(names) > 0 Then names = names & ", "
            names = names & modJson.DictGetStr(sheetInfo, "name", "")
        End If
    Next item
    ws.Cells(r, 4).Value = names
    If modJson.DictGetBool(result, "has_macros", False) Then
        ws.Cells(r, 5).Value = "Blaetter in Spalte D anpassen (Makros werden NICHT ausgefuehrt)"
    Else
        ws.Cells(r, 5).Value = "Blaetter in Spalte D anpassen (unerwuenschte loeschen)"
    End If
    ShowStatus "Blattliste eingetragen - Auswahl in Spalte D anpassen."
End Sub

' ------------------------------------------------------------ Analyse

Public Sub BtnAnalyseStarten()
    Dim ws As Worksheet, r As Long
    Dim sourcesJson As String, imagesJson As String
    Dim ftype As String, path As String, sheetsCell As String
    Dim imgPaths() As String, imgOrder() As Long, imgCount As Long

    ClearError
    If modConfig.IsReadOnlyMode() Then
        ShowError "Nur-Lese-Modus: Ein anderer Arbeitsplatz haelt den Schreibzugriff."
        Exit Sub
    End If
    If mPolling Then
        ShowError "Es laeuft bereits eine Analyse."
        Exit Sub
    End If
    Set ws = AssistSheet()

    ReDim imgPaths(1 To MAX_DATEIEN)
    ReDim imgOrder(1 To MAX_DATEIEN)
    sourcesJson = ""
    For r = FILES_FIRST_ROW To FILES_FIRST_ROW + MAX_DATEIEN - 1
        path = CStr(ws.Cells(r, 1).Value)
        If Len(path) > 0 Then
            ftype = CStr(ws.Cells(r, 2).Value)
            If Len(Dir$(path)) = 0 Then
                ShowError "Datei nicht gefunden: " & path
                Exit Sub
            End If
            Select Case ftype
                Case "pdf"
                    If Len(sourcesJson) > 0 Then sourcesJson = sourcesJson & ","
                    sourcesJson = sourcesJson & "{""type"":""pdf"",""paths"":[" & modJson.JStr(path) & "]}"
                Case "excel"
                    sheetsCell = Trim$(CStr(ws.Cells(r, 4).Value))
                    If Len(sourcesJson) > 0 Then sourcesJson = sourcesJson & ","
                    sourcesJson = sourcesJson & "{""type"":""excel"",""paths"":[" & modJson.JStr(path) & "]"
                    If Len(sheetsCell) > 0 Then
                        sourcesJson = sourcesJson & ",""sheets"":[" & SheetListJson(sheetsCell) & "]"
                    End If
                    sourcesJson = sourcesJson & "}"
                Case "bild"
                    imgCount = imgCount + 1
                    imgPaths(imgCount) = path
                    imgOrder(imgCount) = CLng(Val(CStr(ws.Cells(r, 3).Value)))
                    If imgOrder(imgCount) = 0 Then imgOrder(imgCount) = 1000 + imgCount
            End Select
        End If
    Next r

    If imgCount > 0 Then
        imagesJson = BuildImageSetJson(imgPaths, imgOrder, imgCount)
        If Len(sourcesJson) > 0 Then sourcesJson = sourcesJson & ","
        sourcesJson = sourcesJson & imagesJson
    End If
    If Len(sourcesJson) = 0 Then
        ShowError "Bitte mindestens eine Datei auswaehlen."
        Exit Sub
    End If

    Dim payload As String, hintText As String
    hintText = CStr(ws.Range(CELL_HINT).Value)
    payload = "{""session_id"":" & SessionIdJson() & _
        ",""sources"":[" & sourcesJson & "]" & _
        ",""hint_text"":" & modJson.JStr(hintText) & "}"

    mJobDir = modJobClient.NewJobDir()
    modJobClient.WriteTextFileUtf8 mJobDir & "\request.json", _
        modJobClient.BuildRequestJson("analyze", payload)
    If Not modJobClient.StartJob(mJobDir) Then
        ShowError "Rechenkern nicht gefunden: " & modConfig.CoreExePath()
        mJobDir = ""
        Exit Sub
    End If
    mPolling = True
    ShowStatus "Analyse gestartet ..."
    SchedulePoll
End Sub

Private Function SessionIdJson() As String
    If Len(modConfig.SessionId()) = 0 Then
        SessionIdJson = "null"
    Else
        SessionIdJson = modJson.JStr(modConfig.SessionId())
    End If
End Function

Private Function SheetListJson(ByVal csvList As String) As String
    Dim parts() As String, i As Long, out As String
    parts = Split(csvList, ",")
    For i = LBound(parts) To UBound(parts)
        If Len(Trim$(parts(i))) > 0 Then
            If Len(out) > 0 Then out = out & ","
            out = out & modJson.JStr(Trim$(parts(i)))
        End If
    Next i
    SheetListJson = out
End Function

Private Function BuildImageSetJson(ByRef paths() As String, ByRef order() As Long, _
    ByVal count As Long) As String
    ' Bilder nach benutzerdefinierter Reihenfolge sortieren (stabil)
    Dim i As Long, j As Long, tmpP As String, tmpO As Long, out As String
    For i = 2 To count
        For j = i To 2 Step -1
            If order(j) < order(j - 1) Then
                tmpO = order(j): order(j) = order(j - 1): order(j - 1) = tmpO
                tmpP = paths(j): paths(j) = paths(j - 1): paths(j - 1) = tmpP
            End If
        Next j
    Next i
    out = "{""type"":""image_set"",""paths"":["
    For i = 1 To count
        If i > 1 Then out = out & ","
        out = out & modJson.JStr(paths(i))
    Next i
    BuildImageSetJson = out & "]}"
End Function

Public Sub BtnAbbrechen()
    If Len(mJobDir) > 0 And mPolling Then
        modJobClient.RequestCancel mJobDir
        ShowStatus "Abbruch angefordert ..."
    End If
End Sub

Private Sub SchedulePoll()
    mNextPoll = Now + TimeSerial(0, 0, 1)
    Application.OnTime mNextPoll, "PollAnalyse"
End Sub

Public Sub CancelPollTimer()
    On Error Resume Next
    If mPolling Then Application.OnTime mNextPoll, "PollAnalyse", , False
    mPolling = False
End Sub

Public Sub PollAnalyse()
    Dim prog As Object, resp As Object
    If Not mPolling Then Exit Sub
    If modJobClient.ResponseReady(mJobDir) Then
        mPolling = False
        Set resp = modJobClient.ReadResponse(mJobDir)
        ApplyAnalyzeResponse resp
        modJobClient.CleanupJobDir mJobDir
        mJobDir = ""
        Exit Sub
    End If
    Set prog = modJobClient.ReadProgress(mJobDir)
    If Not prog Is Nothing Then
        ShowStatus modJson.DictGetStr(prog, "phase", "") & " " & _
            CStr(prog("percent")) & "% - " & modJson.DictGetStr(prog, "message", "")
    End If
    SchedulePoll
End Sub

Private Sub ApplyAnalyzeResponse(ByVal resp As Object)
    Dim result As Object, warn As Variant, warnText As String
    If Not modJobClient.IsOk(resp) Then
        ShowError "Analyse fehlgeschlagen: " & modJobClient.ErrorMessage(resp)
        ShowStatus ""
        Exit Sub
    End If
    Set result = resp("result")
    modConfig.SetSessionId modJson.DictGetStr(result, "session_id", "")
    If Len(modJson.DictGetStr(result, "export_base_dir", "")) > 0 Then
        modConfig.SetExportBaseDir modJson.DictGetStr(result, "export_base_dir", "")
    End If
    modErgebnisse.AppendAnalyzeRows result("rows")

    warnText = ""
    For Each warn In result("warnings")
        If Len(warnText) > 0 Then warnText = warnText & " | "
        warnText = warnText & CStr(warn)
    Next warn
    ShowError warnText
    ShowStatus "Fertig: " & CStr(result("rows").Count) & " Probenstellen uebernommen."
End Sub
