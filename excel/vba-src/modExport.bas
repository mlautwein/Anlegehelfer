Attribute VB_Name = "modExport"
Option Explicit

' =====================================================================
' modExport - atomarer Fuenffach-CSV-Export ueber den Rechenkern.
' Ziel: Ordner der zuerst importierten Datei. Kodierung waehlbar
' (UTF-8 mit BOM Standard, Windows-1252 Alternative). Der Export
' bestaetigt alle exportierten Zellen als Lernsignal (im Kern).
' =====================================================================

Public Sub ExportCsvFiles()
    Dim lo As ListObject, n As Long, i As Long, c As Long
    Dim rowsJson As String, enc As String, targetDir As String
    Dim resp As Object, result As Object

    If modConfig.IsReadOnlyMode() Then
        modAssistent.ShowError "Nur-Lese-Modus: Export nicht moeglich."
        Exit Sub
    End If
    Set lo = modErgebnisse.ResultTable()
    If lo.DataBodyRange Is Nothing Then
        modAssistent.ShowError "Keine Zeilen zum Exportieren."
        Exit Sub
    End If
    n = lo.ListRows.Count
    targetDir = modConfig.ExportBaseDir()
    If Len(targetDir) = 0 Then
        modAssistent.ShowError "Kein Exportziel bekannt - bitte zuerst ein Dokument importieren."
        Exit Sub
    End If

    enc = modAssistent.SelectedEncoding()

    rowsJson = "["
    For i = 1 To n
        If i > 1 Then rowsJson = rowsJson & ","
        rowsJson = rowsJson & "{""row_id"":" & _
            modJson.JStr(CStr(lo.DataBodyRange.Cells(i, modErgebnisse.COL_ROWKEY).Value)) & _
            ",""values"":{"
        For c = modErgebnisse.COL_BEZ1 To modErgebnisse.COL_UNT
            If c > modErgebnisse.COL_BEZ1 Then rowsJson = rowsJson & ","
            rowsJson = rowsJson & modJson.JStr(modErgebnisse.FieldName(c)) & ":" & _
                modJson.JStr(modErgebnisse.SanitizeValue(lo.DataBodyRange.Cells(i, c).Value))
        Next c
        rowsJson = rowsJson & "}}"
    Next i
    rowsJson = rowsJson & "]"

    Dim payload As String
    payload = "{""session_id"":" & JNullable(modConfig.SessionId()) & _
        ",""rows"":" & rowsJson & _
        ",""encoding"":" & modJson.JStr(enc) & _
        ",""target_dir"":" & modJson.JStr(targetDir) & _
        ",""client_event_id"":" & modJson.JStr(modConfig.NewGuid()) & "}"

    modAssistent.ShowStatus "Export laeuft ..."
    Set resp = modJobClient.RunJobAndWait("export_csv", payload, 90)
    If Not modJobClient.IsOk(resp) Then
        modAssistent.ShowError "Export fehlgeschlagen: " & modJobClient.ErrorMessage(resp)
        Exit Sub
    End If
    Set result = resp("result")
    modAssistent.ShowStatus "Export abgeschlossen: " & CStr(result("row_count")) & _
        " Zeilen in 5 Dateien (" & modJson.DictGetStr(result, "target_dir", targetDir) & ")."
End Sub

Private Function JNullable(ByVal s As String) As String
    If Len(s) = 0 Then
        JNullable = "null"
    Else
        JNullable = modJson.JStr(s)
    End If
End Function
