Attribute VB_Name = "modSetup"
Option Explicit

' =====================================================================
' modSetup - baut die Oberflaeche idempotent auf (Blaetter, Tabelle,
' Buttons, Formatierung). Damit ist die XLSM reproduzierbar aus einer
' leeren Mappe + importierten Textmodulen erzeugbar (Buildartefakt).
' =====================================================================

Public Sub EnsureUi()
    EnsureSheets
    EnsureAssistentLayout
    EnsureResultTable
    EnsureButtons
End Sub

Private Sub EnsureSheets()
    Dim ws As Worksheet, names As Variant, n As Variant, found As Boolean
    names = Array(ASSIST_SHEET, RESULT_SHEET, META_SHEET)
    For Each n In names
        found = False
        For Each ws In ThisWorkbook.Worksheets
            If ws.Name = CStr(n) Then found = True
        Next ws
        If Not found Then
            Set ws = ThisWorkbook.Worksheets.Add(After:=ThisWorkbook.Worksheets(ThisWorkbook.Worksheets.Count))
            ws.Name = CStr(n)
        End If
    Next n
    ' genau zwei sichtbare Blaetter; _Meta sehr versteckt
    ThisWorkbook.Worksheets(META_SHEET).Visible = xlSheetVeryHidden
    ThisWorkbook.Worksheets(ASSIST_SHEET).Visible = xlSheetVisible
    ThisWorkbook.Worksheets(RESULT_SHEET).Visible = xlSheetVisible
    ' ggf. vorhandene Standardblaetter ausblenden statt loeschen (verlustfrei)
    For Each ws In ThisWorkbook.Worksheets
        If ws.Name <> ASSIST_SHEET And ws.Name <> RESULT_SHEET And ws.Name <> META_SHEET Then
            If ThisWorkbook.Worksheets(ASSIST_SHEET).Visible = xlSheetVisible Then
                On Error Resume Next
                ws.Visible = xlSheetVeryHidden
                On Error GoTo 0
            End If
        End If
    Next ws
    Dim meta As Worksheet
    Set meta = ThisWorkbook.Worksheets(META_SHEET)
    meta.Range("A1").Value = "session_id"
    meta.Range("A2").Value = "export_base_dir"
    meta.Range("A3").Value = "read_only"
End Sub

Private Sub EnsureAssistentLayout()
    Dim ws As Worksheet
    Set ws = ThisWorkbook.Worksheets(ASSIST_SHEET)
    With ws
        .Range("B2").Value = "LIMS-Probenassistent"
        .Range("B2").Font.Size = 16
        .Range("B2").Font.Bold = True
        .Range("B3").Value = "Komfortwerkzeug: Werte pruefen und per Copy-and-paste in das LIMS uebernehmen."
        .Range("A7").Value = "Datei"
        .Range("B7").Value = "Typ"
        .Range("C7").Value = "Bild-Reihenfolge"
        .Range("D7").Value = "Excel-Blattauswahl (Komma-Liste)"
        .Range("E7").Value = "Hinweis"
        .Range("A7:E7").Font.Bold = True
        .Range("A30").Value = "Zusatzinformationen (nur Hinweis fuer diesen Import; daraus Abgeleitetes wird gelb):"
        .Range("A30").Font.Bold = True
        .Range(modAssistent.CELL_HINT).Value = ""
        .Range("A33").Value = "Export-Kodierung:"
        With .Range(modAssistent.CELL_ENCODING).Validation
            .Delete
            .Add Type:=xlValidateList, AlertStyle:=xlValidAlertStop, _
                Formula1:="UTF-8 (mit BOM),Windows-1252"
        End With
        If Len(CStr(.Range(modAssistent.CELL_ENCODING).Value)) = 0 Then
            .Range(modAssistent.CELL_ENCODING).Value = "UTF-8 (mit BOM)"
        End If
        .Range("A35").Value = "Fortschritt:"
        .Range("A36").Value = "Meldungen:"
        .Range("A35:A36").Font.Bold = True
        .Columns("A").ColumnWidth = 52
        .Columns("B").ColumnWidth = 16
        .Columns("C").ColumnWidth = 14
        .Columns("D").ColumnWidth = 42
        .Columns("E").ColumnWidth = 46
        .Range(modAssistent.CELL_ERROR).Font.Color = RGB(180, 0, 0)
    End With
End Sub

Private Sub EnsureResultTable()
    Dim ws As Worksheet, lo As ListObject
    Set ws = ThisWorkbook.Worksheets(RESULT_SHEET)
    On Error Resume Next
    Set lo = ws.ListObjects(RESULT_TABLE)
    On Error GoTo 0
    If lo Is Nothing Then
        ws.Range("A1:G1").Value = Array("Bez1", "Bez2", "B3", "B4", "Untersuchungsart", "RowKey", "SrcOrd")
        Set lo = ws.ListObjects.Add(xlSrcRange, ws.Range("A1:G2"), , xlYes)
        lo.Name = RESULT_TABLE
        If Not lo.DataBodyRange Is Nothing Then lo.DataBodyRange.Delete
    End If
    ws.Columns("A:E").NumberFormat = "@"     ' Text erzwingen, keine Formeln
    ws.Columns("F:G").Hidden = True          ' Technikspalten unsichtbar
    ws.Columns("A").ColumnWidth = 30
    ws.Columns("B").ColumnWidth = 36
    ws.Columns("C").ColumnWidth = 38
    ws.Columns("D").ColumnWidth = 24
    ws.Columns("E").ColumnWidth = 26
End Sub

Private Sub EnsureButtons()
    AddButton ASSIST_SHEET, "btnDateien", "Dateien waehlen", "BtnDateienWaehlen", 380, 8, 120, 24
    AddButton ASSIST_SHEET, "btnLeeren", "Liste leeren", "BtnListeLeeren", 505, 8, 100, 24
    AddButton ASSIST_SHEET, "btnBlaetter", "Blaetter waehlen", "BtnBlaetterWaehlen", 610, 8, 120, 24
    AddButton ASSIST_SHEET, "btnStart", "Analyse starten", "BtnAnalyseStarten", 380, 40, 120, 28
    AddButton ASSIST_SHEET, "btnCancel", "Abbrechen", "BtnAbbrechen", 505, 40, 100, 28

    AddButton RESULT_SHEET, "btnAdd", "Probenstelle hinzufuegen", "AddSampleRow", 620, 8, 150, 24
    AddButton RESULT_SHEET, "btnDel", "Probenstelle loeschen", "DeleteSampleRow", 775, 8, 140, 24
    AddButton RESULT_SHEET, "btnUndo", "Rueckgaengig (1 Schritt)", "UndoLastAction", 920, 8, 140, 24
    AddButton RESULT_SHEET, "btnSort", "Sortieren Bez1-Etage-Raum", "SortByBez1EtageRaum", 620, 36, 170, 22
    AddButton RESULT_SHEET, "btnRestore", "Quellreihenfolge", "RestoreSourceOrder", 795, 36, 120, 22
    AddButton RESULT_SHEET, "btnCop1", "Bez1 kopieren", "CopyColBez1", 620, 64, 100, 22
    AddButton RESULT_SHEET, "btnCop2", "Bez2 kopieren", "CopyColBez2", 722, 64, 100, 22
    AddButton RESULT_SHEET, "btnCop3", "B3 kopieren", "CopyColB3", 824, 64, 90, 22
    AddButton RESULT_SHEET, "btnCop4", "B4 kopieren", "CopyColB4", 916, 64, 90, 22
    AddButton RESULT_SHEET, "btnCop5", "Untersuchungsart kopieren", "CopyColUntersuchungsart", 620, 90, 170, 22
    AddButton RESULT_SHEET, "btnExport", "CSV-Export (5 Dateien)", "ExportCsvFiles", 795, 90, 150, 22
End Sub

Private Sub AddButton(ByVal sheetName As String, ByVal btnName As String, _
    ByVal caption As String, ByVal onAction As String, _
    ByVal leftPt As Double, ByVal topPt As Double, _
    ByVal widthPt As Double, ByVal heightPt As Double)
    Dim ws As Worksheet, b As Button
    Set ws = ThisWorkbook.Worksheets(sheetName)
    On Error Resume Next
    ws.Buttons(btnName).Delete
    On Error GoTo 0
    Set b = ws.Buttons.Add(leftPt, topPt, widthPt, heightPt)
    b.Name = btnName
    b.caption = caption
    b.OnAction = onAction
End Sub

' oeffentliche Wrapper fuer Button-OnAction (eindeutige Prozedurnamen)
Public Sub UndoLastAction()
    modUndo.UndoLast
End Sub
