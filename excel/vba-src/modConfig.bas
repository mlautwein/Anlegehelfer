Attribute VB_Name = "modConfig"
Option Explicit

' =====================================================================
' modConfig - zentrale Konfiguration und Pfade
' Die Konfiguration (config.json) liegt neben der Arbeitsmappe im
' gemeinsamen Ordner. Benutzerdaten reisen NIE in Shellstrings, nur in
' JSON-Dateien; Prozesspfade stammen ausschliesslich aus der Konfiguration.
' =====================================================================

Public Const APP_SCHEMA_VERSION As String = "1.0"
Public Const META_SHEET As String = "_Meta"
Public Const RESULT_SHEET As String = "Ergebnisse"
Public Const ASSIST_SHEET As String = "Assistent"
Public Const RESULT_TABLE As String = "tblErgebnisse"
Public Const COLOR_UNSICHER As Long = 65535        ' RGB(255,255,0) gelb
Public Const MAX_DATEIEN As Long = 20

Private mCoreExe As String
Private mJobRoot As String
Private mShareDir As String
Private mLoaded As Boolean

Public Function WorkbookDir() As String
    WorkbookDir = ThisWorkbook.Path
End Function

Private Function LocalAppData() As String
    LocalAppData = Environ$("LOCALAPPDATA")
    If Len(LocalAppData) = 0 Then LocalAppData = Environ$("TEMP")
End Function

Public Sub LoadConfig()
    Dim cfgPath As String, txt As String
    Dim cfg As Object
    If mLoaded Then Exit Sub
    mShareDir = WorkbookDir()
    mCoreExe = mShareDir & "\core\lims_core.exe"
    mJobRoot = LocalAppData() & "\LIMS-Probenassistent\jobs"
    cfgPath = mShareDir & "\config.json"
    If Len(Dir$(cfgPath)) > 0 Then
        txt = modJobClient.ReadTextFile(cfgPath)
        If Len(txt) > 0 Then
            On Error Resume Next
            Set cfg = modJson.ParseJson(txt)
            On Error GoTo 0
            If Not cfg Is Nothing Then
                If cfg.Exists("core_exe") Then mCoreExe = ResolvePath(CStr(cfg("core_exe")))
                If cfg.Exists("share_dir") Then mShareDir = ResolvePath(CStr(cfg("share_dir")))
                If cfg.Exists("job_root") Then mJobRoot = ResolvePath(CStr(cfg("job_root")))
            End If
        End If
    End If
    mLoaded = True
End Sub

Private Function ResolvePath(ByVal p As String) As String
    ' relative Pfade beziehen sich auf den Arbeitsmappenordner
    If Len(p) = 0 Then
        ResolvePath = p
    ElseIf Mid$(p, 2, 1) = ":" Or Left$(p, 2) = "\\" Then
        ResolvePath = p
    Else
        ResolvePath = WorkbookDir() & "\" & p
    End If
End Function

Public Function CoreExePath() As String
    LoadConfig
    CoreExePath = mCoreExe
End Function

Public Function JobRootPath() As String
    LoadConfig
    Dim fso As Object
    Set fso = CreateObject("Scripting.FileSystemObject")
    EnsureFolder fso, LocalAppData() & "\LIMS-Probenassistent"
    EnsureFolder fso, mJobRoot
    JobRootPath = mJobRoot
End Function

Public Function ShareDirPath() As String
    LoadConfig
    ShareDirPath = mShareDir
End Function

Private Sub EnsureFolder(ByVal fso As Object, ByVal p As String)
    If Not fso.FolderExists(p) Then fso.CreateFolder p
End Sub

Public Function NewGuid() As String
    ' GUID ohne Zusatzbibliotheken (ausreichend eindeutig fuer Job-IDs)
    Dim s As String, i As Long, ch As String
    Randomize Timer + CDbl(Now) * 86400#
    Const HEXCHARS As String = "0123456789abcdef"
    s = ""
    For i = 1 To 32
        ch = Mid$(HEXCHARS, Int(Rnd * 16) + 1, 1)
        s = s & ch
        If i = 8 Or i = 12 Or i = 16 Or i = 20 Then s = s & "-"
    Next i
    NewGuid = s
End Function

Public Function MetaSheet() As Worksheet
    Set MetaSheet = ThisWorkbook.Worksheets(META_SHEET)
End Function

Public Function SessionId() As String
    SessionId = CStr(MetaSheet().Range("B1").Value)
End Function

Public Sub SetSessionId(ByVal sid As String)
    MetaSheet().Range("B1").Value = sid
End Sub

Public Function ExportBaseDir() As String
    ExportBaseDir = CStr(MetaSheet().Range("B2").Value)
End Function

Public Sub SetExportBaseDir(ByVal p As String)
    MetaSheet().Range("B2").Value = p
End Sub

Public Function IsReadOnlyMode() As Boolean
    IsReadOnlyMode = (CStr(MetaSheet().Range("B3").Value) = "1")
End Function

Public Sub SetReadOnlyMode(ByVal ro As Boolean)
    MetaSheet().Range("B3").Value = IIf(ro, "1", "0")
End Sub
