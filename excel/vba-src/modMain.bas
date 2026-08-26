Attribute VB_Name = "modMain"
Option Explicit

' =====================================================================
' modMain - Lebenszyklus: Oeffnen (leere Liste, exklusiver Lock,
' Snapshot-Pull), Heartbeat, Schliessen (Snapshot-Push, Lock-Freigabe).
' =====================================================================

Private mHeartbeatAt As Date
Private mHeartbeatOn As Boolean

Public Sub AppOpen()
    Dim resp As Object, result As Object, lockInfo As Object
    Dim ws As Worksheet

    modConfig.LoadConfig
    modSetup.EnsureUi                       ' idempotent: Blaetter/Buttons/Tabelle
    modErgebnisse.ClearResults              ' F-UI-009: leere Arbeitsliste
    modConfig.SetSessionId ""
    modConfig.SetExportBaseDir ""
    modAssistent.ClearError
    modAssistent.ShowStatus "Starte ..."

    Set resp = modJobClient.RunJobAndWait("app_open", _
        "{""share_dir"":" & modJson.JStr(modConfig.ShareDirPath()) & _
        ",""workstation"":" & modJson.JStr(Environ$("COMPUTERNAME")) & _
        ",""takeover_stale"":false}", 60)

    Set ws = modAssistent.AssistSheet()
    If Not modJobClient.IsOk(resp) Then
        modConfig.SetReadOnlyMode True
        ws.Range(modAssistent.CELL_LOCKINFO).Value = _
            "Start ohne Rechenkern (" & modJobClient.ErrorMessage(resp) & ") - nur Ansicht."
        modAssistent.ShowStatus ""
        Exit Sub
    End If
    Set result = resp("result")
    If modJson.DictGetBool(result, "lock_acquired", False) Then
        modConfig.SetReadOnlyMode False
        ws.Range(modAssistent.CELL_LOCKINFO).Value = "Schreibmodus (exklusiver Lock aktiv)."
        StartHeartbeat
    Else
        modConfig.SetReadOnlyMode True
        Dim holder As String, stale As Boolean
        holder = ""
        stale = False
        If result.Exists("lock") And Not IsNull(result("lock")) Then
            Set lockInfo = result("lock")
            holder = modJson.DictGetStr(lockInfo, "holder_workstation", "?")
            stale = modJson.DictGetBool(lockInfo, "stale", False)
        End If
        If stale Then
            If MsgBox("Der Schreib-Lock von '" & holder & "' ist veraltet " & _
                "(vermutlich Absturz oder Netzwerkabbruch)." & vbCrLf & vbCrLf & _
                "Lock uebernehmen und im Schreibmodus starten?", _
                vbYesNo + vbExclamation, "Veralteter Lock") = vbYes Then
                TakeoverStaleLock
                Exit Sub
            End If
        End If
        ws.Range(modAssistent.CELL_LOCKINFO).Value = _
            "NUR LESEND - Schreibzugriff liegt bei '" & holder & "'."
    End If

    ApplyOpenWarnings result
    modAssistent.ShowStatus "Bereit."
End Sub

Private Sub TakeoverStaleLock()
    Dim resp As Object, result As Object
    Set resp = modJobClient.RunJobAndWait("app_open", _
        "{""share_dir"":" & modJson.JStr(modConfig.ShareDirPath()) & _
        ",""workstation"":" & modJson.JStr(Environ$("COMPUTERNAME")) & _
        ",""takeover_stale"":true}", 60)
    If modJobClient.IsOk(resp) Then
        Set result = resp("result")
        If modJson.DictGetBool(result, "lock_acquired", False) Then
            modConfig.SetReadOnlyMode False
            modAssistent.AssistSheet().Range(modAssistent.CELL_LOCKINFO).Value = _
                "Schreibmodus (Lock uebernommen)."
            StartHeartbeat
            ApplyOpenWarnings result
            modAssistent.ShowStatus "Bereit."
            Exit Sub
        End If
    End If
    modConfig.SetReadOnlyMode True
    modAssistent.ShowError "Lock-Uebernahme fehlgeschlagen: " & modJobClient.ErrorMessage(resp)
End Sub

Private Sub ApplyOpenWarnings(ByVal result As Object)
    Dim warn As Variant, txt As String
    For Each warn In result("warnings")
        If Len(txt) > 0 Then txt = txt & " | "
        txt = txt & CStr(warn)
    Next warn
    If Len(txt) > 0 Then modAssistent.ShowError txt
End Sub

Public Sub AppClose()
    On Error Resume Next
    modAssistent.CancelPollTimer
    modCopyConfirm.UnhookCopyKey
    StopHeartbeat
    If Not modConfig.IsReadOnlyMode() Then
        Dim resp As Object
        Set resp = modJobClient.RunJobAndWait("app_close", "{""release_lock"":true}", 90)
        ' Warnungen (z. B. Pending-Snapshot) bewusst still: Details stehen im
        ' naechsten Start ("Ausstehender lokaler Stand wurde synchronisiert").
    End If
End Sub

' ------------------------------------------------------------ Heartbeat

Private Sub StartHeartbeat()
    mHeartbeatOn = True
    ScheduleHeartbeat
End Sub

Private Sub ScheduleHeartbeat()
    mHeartbeatAt = Now + TimeSerial(0, 2, 0)
    Application.OnTime mHeartbeatAt, "HeartbeatTick"
End Sub

Public Sub HeartbeatTick()
    Dim shell As Object
    If Not mHeartbeatOn Then Exit Sub
    On Error Resume Next
    Set shell = CreateObject("WScript.Shell")
    shell.Run """" & modConfig.CoreExePath() & """ heartbeat", 0, False
    ScheduleHeartbeat
End Sub

Private Sub StopHeartbeat()
    On Error Resume Next
    If mHeartbeatOn Then Application.OnTime mHeartbeatAt, "HeartbeatTick", , False
    mHeartbeatOn = False
End Sub
