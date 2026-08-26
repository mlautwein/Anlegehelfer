Attribute VB_Name = "modJobClient"
Option Explicit

' =====================================================================
' modJobClient - dateibasiertes Jobprotokoll zur portablen Core-EXE
' Excel schreibt request.json, startet die EXE, liest progress.json /
' response.json. Kurze Jobs: begrenztes Warten mit DoEvents. Analyse:
' ereignisfreundliches Polling ueber Application.OnTime (modAssistent).
' =====================================================================

Public Function ReadTextFile(ByVal path As String) As String
    Dim stream As Object
    On Error GoTo fail
    Set stream = CreateObject("ADODB.Stream")
    stream.Type = 2               ' Text
    stream.Charset = "utf-8"
    stream.Open
    stream.LoadFromFile path
    ReadTextFile = stream.ReadText(-1)
    stream.Close
    Exit Function
fail:
    ReadTextFile = ""
End Function

Public Sub WriteTextFileUtf8(ByVal path As String, ByVal content As String)
    ' UTF-8 ohne BOM schreiben (ADODB schreibt BOM -> abschneiden)
    Dim stream As Object, binStream As Object
    Set stream = CreateObject("ADODB.Stream")
    stream.Type = 2
    stream.Charset = "utf-8"
    stream.Open
    stream.WriteText content
    stream.Position = 3           ' BOM ueberspringen
    Set binStream = CreateObject("ADODB.Stream")
    binStream.Type = 1            ' Binary
    binStream.Open
    stream.CopyTo binStream
    stream.Close
    binStream.SaveToFile path, 2  ' adSaveCreateOverWrite
    binStream.Close
End Sub

Public Function NewJobDir() As String
    Dim fso As Object, p As String
    Set fso = CreateObject("Scripting.FileSystemObject")
    p = modConfig.JobRootPath() & "\job-" & modConfig.NewGuid()
    fso.CreateFolder p
    NewJobDir = p
End Function

Public Function BuildRequestJson(ByVal kind As String, ByVal payloadJson As String) As String
    BuildRequestJson = "{""schema_version"":" & modJson.JStr(APP_SCHEMA_VERSION) & _
        ",""job_id"":" & modJson.JStr(modConfig.NewGuid()) & _
        ",""kind"":" & modJson.JStr(kind) & _
        ",""created_utc"":" & modJson.JStr(Format$(Now, "yyyy-mm-dd") & "T" & Format$(Now, "hh:nn:ss") & "Z") & _
        ",""payload"":" & payloadJson & "}"
End Function

Public Function StartJob(ByVal jobDir As String) As Boolean
    Dim shell As Object, cmd As String, exePath As String
    exePath = modConfig.CoreExePath()
    If Len(Dir$(exePath)) = 0 Then
        StartJob = False
        Exit Function
    End If
    ' Nur manifestierte Pfade in der Kommandozeile - niemals Benutzerdaten.
    cmd = """" & exePath & """ run-job --job-dir """ & jobDir & """"
    Set shell = CreateObject("WScript.Shell")
    shell.Run cmd, 0, False       ' 0 = versteckt, nicht warten
    StartJob = True
End Function

Public Sub RequestCancel(ByVal jobDir As String)
    On Error Resume Next
    Dim fso As Object
    Set fso = CreateObject("Scripting.FileSystemObject")
    fso.CreateTextFile(jobDir & "\cancel.flag", True).Close
End Sub

Public Function ReadProgress(ByVal jobDir As String) As Object
    Dim txt As String
    txt = ReadTextFile(jobDir & "\progress.json")
    If Len(txt) = 0 Then
        Set ReadProgress = Nothing
    Else
        On Error Resume Next
        Set ReadProgress = modJson.ParseJson(txt)
    End If
End Function

Public Function ReadResponse(ByVal jobDir As String) As Object
    Dim txt As String
    txt = ReadTextFile(jobDir & "\response.json")
    If Len(txt) = 0 Then
        Set ReadResponse = Nothing
    Else
        On Error Resume Next
        Set ReadResponse = modJson.ParseJson(txt)
    End If
End Function

Public Function ResponseReady(ByVal jobDir As String) As Boolean
    ResponseReady = (Len(Dir$(jobDir & "\response.json")) > 0)
End Function

' Kurzen Job synchron-artig ausfuehren (begrenzt, UI bleibt reaktiv).
Public Function RunJobAndWait(ByVal kind As String, ByVal payloadJson As String, _
    Optional ByVal timeoutSeconds As Long = 45) As Object
    Dim jobDir As String, started As Single
    jobDir = NewJobDir()
    WriteTextFileUtf8 jobDir & "\request.json", BuildRequestJson(kind, payloadJson)
    If Not StartJob(jobDir) Then
        Set RunJobAndWait = ErrorResponse("core_fehlt", _
            "Rechenkern nicht gefunden: " & modConfig.CoreExePath())
        Exit Function
    End If
    started = Timer
    Do While Not ResponseReady(jobDir)
        DoEvents
        Sleep 120
        If TimerElapsed(started) > timeoutSeconds Then
            Set RunJobAndWait = ErrorResponse("timeout", _
                "Der Rechenkern hat nicht rechtzeitig geantwortet (" & kind & ").")
            Exit Function
        End If
    Loop
    Set RunJobAndWait = ReadResponse(jobDir)
    CleanupJobDir jobDir
End Function

Public Sub CleanupJobDir(ByVal jobDir As String)
    On Error Resume Next
    Dim fso As Object
    Set fso = CreateObject("Scripting.FileSystemObject")
    fso.DeleteFolder jobDir, True
End Sub

Public Function ErrorResponse(ByVal code As String, ByVal msg As String) As Object
    Set ErrorResponse = modJson.ParseJson( _
        "{""ok"":false,""error"":{""code"":" & modJson.JStr(code) & _
        ",""message"":" & modJson.JStr(msg) & ",""detail"":""""},""result"":null}")
End Function

Public Function IsOk(ByVal resp As Object) As Boolean
    If resp Is Nothing Then
        IsOk = False
    Else
        IsOk = modJson.DictGetBool(resp, "ok", False)
    End If
End Function

Public Function ErrorMessage(ByVal resp As Object) As String
    If resp Is Nothing Then
        ErrorMessage = "Keine Antwort vom Rechenkern."
    ElseIf resp.Exists("error") And Not IsNull(resp("error")) Then
        ErrorMessage = modJson.DictGetStr(resp("error"), "message", "Unbekannter Fehler.")
    Else
        ErrorMessage = ""
    End If
End Function

Private Function TimerElapsed(ByVal started As Single) As Single
    Dim t As Single
    t = Timer
    If t < started Then t = t + 86400!   ' Mitternachtsueberlauf
    TimerElapsed = t - started
End Function

#If VBA7 Then
    Public Declare PtrSafe Sub Sleep Lib "kernel32" (ByVal dwMilliseconds As Long)
#Else
    Public Declare Sub Sleep Lib "kernel32" (ByVal dwMilliseconds As Long)
#End If
