# =====================================================================
# build_workbook.ps1 - erzeugt die zentrale XLSM aus den Text-VBA-Modulen
#
# WICHTIG (dokumentierte Voraussetzung): Die COM-Automation benoetigt in
# Excel einmalig "Zugriff auf das VBA-Projektobjektmodell vertrauen":
#   Datei > Optionen > Trust Center > Einstellungen > Makroeinstellungen
#   -> Haken bei "Zugriff auf das VBA-Projektobjektmodell vertrauen"
# Ohne diesen Haken bricht das Skript mit einem Hinweis ab; die kurze
# manuelle Alternative steht in docs/EXCEL_SETUP.md (ca. 5 Minuten).
#
# Aufruf: powershell -ExecutionPolicy Bypass -File packaging\windows\build_workbook.ps1
# Ergebnis: dist\LIMS-Probenassistent.xlsm
# =====================================================================

$ErrorActionPreference = "Stop"
$repo = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$vbaDir = Join-Path $repo "excel\vba-src"
$outDir = Join-Path $repo "dist"
$outFile = Join-Path $outDir "LIMS-Probenassistent.xlsm"
New-Item -ItemType Directory -Force -Path $outDir | Out-Null

$excel = New-Object -ComObject Excel.Application
$excel.Visible = $false
$excel.DisplayAlerts = $false

try {
    $wb = $excel.Workbooks.Add()

    try {
        $null = $wb.VBProject.Name
    } catch {
        throw ("Kein Zugriff auf das VBA-Projekt. Bitte in Excel aktivieren: " +
            "Trust Center -> 'Zugriff auf das VBA-Projektobjektmodell vertrauen'. " +
            "Alternative: manueller Import laut docs/EXCEL_SETUP.md")
    }

    # 1) Standardmodule importieren
    Get-ChildItem -Path $vbaDir -Filter "mod*.bas" | Sort-Object Name | ForEach-Object {
        Write-Host ("Importiere {0}" -f $_.Name)
        $null = $wb.VBProject.VBComponents.Import($_.FullName)
    }

    # 2) Blaetter anlegen/benennen und CodeNames setzen
    while ($wb.Worksheets.Count -lt 3) { $null = $wb.Worksheets.Add() }
    $wsA = $wb.Worksheets.Item(1); $wsA.Name = "Assistent"
    $wsE = $wb.Worksheets.Item(2); $wsE.Name = "Ergebnisse"
    $wsM = $wb.Worksheets.Item(3); $wsM.Name = "_Meta"

    function Set-SheetCode([object]$wb, [object]$ws, [string]$codeName, [string]$clsPath) {
        $comp = $wb.VBProject.VBComponents.Item($ws.CodeName)
        $comp.Properties.Item("_CodeName").Value = $codeName
        $lines = Get-Content -Path $clsPath -Encoding UTF8
        # Header (VERSION/BEGIN/Attribute) ueberspringen - nur Code uebernehmen
        $body = ($lines | Where-Object {
            ($_ -notmatch "^(VERSION|BEGIN|END$|\s*MultiUse|Attribute\s)")
        }) -join "`r`n"
        $cm = $comp.CodeModule
        if ($cm.CountOfLines -gt 0) { $cm.DeleteLines(1, $cm.CountOfLines) }
        $cm.AddFromString($body)
    }

    Set-SheetCode $wb $wsE "SheetErgebnisse" (Join-Path $vbaDir "SheetErgebnisse.cls")
    Set-SheetCode $wb $wsA "SheetAssistent" (Join-Path $vbaDir "SheetAssistent.cls")

    # 3) ThisWorkbook-Code einsetzen
    $twb = $wb.VBProject.VBComponents.Item("ThisWorkbook")
    $lines = Get-Content -Path (Join-Path $vbaDir "ThisWorkbook.cls") -Encoding UTF8
    $body = ($lines | Where-Object {
        ($_ -notmatch "^(VERSION|BEGIN|END$|\s*MultiUse|Attribute\s)")
    }) -join "`r`n"
    if ($twb.CodeModule.CountOfLines -gt 0) { $twb.CodeModule.DeleteLines(1, $twb.CodeModule.CountOfLines) }
    $twb.CodeModule.AddFromString($body)

    # 4) UI aufbauen und speichern (52 = xlOpenXMLWorkbookMacroEnabled)
    $excel.Run("modSetup.EnsureUi") | Out-Null
    if (Test-Path $outFile) { Remove-Item $outFile -Force }
    $wb.SaveAs($outFile, 52)
    Write-Host ("Arbeitsmappe erzeugt: {0}" -f $outFile) -ForegroundColor Green
    Write-Host "Empfehlung: Datei im gemeinsamen Ordner ablegen (neben \core\ und config.json)."
} finally {
    if ($wb) { $wb.Close($false) }
    $excel.Quit()
    [System.Runtime.InteropServices.Marshal]::ReleaseComObject($excel) | Out-Null
}
