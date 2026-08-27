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

[CmdletBinding()]
param(
    # Ordner mit den VBA-Textmodulen. Ohne Angabe wird gesucht.
    [string]$VbaDir = "",
    # Zieldatei. Ohne Angabe: dist\LIMS-Probenassistent.xlsm neben dem Skript.
    [string]$Ziel = "",

    # Den Trust-Center-Schalter nicht anfassen (dann muss der Haken von Hand
    # gesetzt sein, sonst schlaegt der Bau fehl).
    [switch]$KeinTrustCenterEingriff
)

$ErrorActionPreference = "Stop"

# Das Skript wird aus zwei Layouts heraus aufgerufen: aus dem entpackten
# Einrichtungsarchiv (excel\vba-src liegt daneben) und aus dem Repository
# (packaging\windows\..). Beide Faelle abdecken, statt einen anzunehmen.
if (-not $VbaDir) {
    foreach ($kandidat in @(
        (Join-Path $PSScriptRoot "excel\vba-src"),
        (Join-Path $PSScriptRoot "..\..\excel\vba-src")
    )) {
        if (Test-Path $kandidat) { $VbaDir = (Resolve-Path $kandidat).Path; break }
    }
}
if (-not $VbaDir -or -not (Test-Path $VbaDir)) {
    throw ("VBA-Quellmodule nicht gefunden. Erwartet neben diesem Skript " +
        "unter excel\vba-src oder im Repository. Pfad per -VbaDir angeben.")
}

if ($Ziel) {
    $outFile = [System.IO.Path]::GetFullPath($Ziel)
    $outDir = Split-Path $outFile -Parent
} else {
    $outDir = Join-Path $PSScriptRoot "dist"
    $outFile = Join-Path $outDir "LIMS-Probenassistent.xlsm"
}
New-Item -ItemType Directory -Force -Path $outDir | Out-Null
Write-Host ("VBA-Quellen: {0}" -f $VbaDir)

# ---------------------------------------------------------------------
# Trust-Center-Haken vorruebergehend setzen
#
# Die COM-Automation des VBA-Projekts ist standardmaessig gesperrt; ohne
# den Haken "Zugriff auf das VBA-Projektobjektmodell vertrauen" schlaegt
# der Bau fehl. Das ist der mit Abstand haeufigste Stolperstein bei der
# Installation. Der Schalter liegt in HKCU - also KEINE Administratorrechte
# noetig - und wird unten in jedem Fall auf den vorherigen Wert
# zurueckgesetzt, auch wenn der Bau scheitert. Excel liest ihn beim Start,
# deshalb muss das vor dem Erzeugen der Excel-Instanz geschehen.
# ---------------------------------------------------------------------
$gesetzteSchluessel = @()
if (-not $KeinTrustCenterEingriff) {
    foreach ($ver in @("16.0", "15.0", "14.0")) {
        $pfad = "HKCU:\Software\Microsoft\Office\$ver\Excel\Security"
        # Nur fuer tatsaechlich installierte Excel-Versionen.
        if (-not (Test-Path "HKCU:\Software\Microsoft\Office\$ver\Excel")) { continue }
        try {
            if (-not (Test-Path $pfad)) { New-Item -Path $pfad -Force | Out-Null }
            $alt = (Get-ItemProperty -Path $pfad -Name AccessVBOM -ErrorAction SilentlyContinue).AccessVBOM
            if ($alt -ne 1) {
                Set-ItemProperty -Path $pfad -Name AccessVBOM -Value 1 -Type DWord
                $gesetzteSchluessel += [pscustomobject]@{ Pfad = $pfad; Alt = $alt }
                Write-Host ("Trust Center fuer Excel {0} voruebergehend geoeffnet" -f $ver) -ForegroundColor Yellow
            }
        } catch {
            Write-Host ("Trust-Center-Schalter fuer {0} nicht setzbar: {1}" -f $ver, $_.Exception.Message) -ForegroundColor Yellow
        }
    }
}

function Restore-TrustCenter {
    foreach ($e in $script:gesetzteSchluessel) {
        try {
            if ($null -eq $e.Alt) {
                Remove-ItemProperty -Path $e.Pfad -Name AccessVBOM -ErrorAction SilentlyContinue
            } else {
                Set-ItemProperty -Path $e.Pfad -Name AccessVBOM -Value $e.Alt -Type DWord
            }
        } catch {
            Write-Host ("Achtung: Trust-Center-Schalter unter {0} konnte nicht zurueckgesetzt werden." -f $e.Pfad) -ForegroundColor Red
        }
    }
    if ($script:gesetzteSchluessel.Count -gt 0) {
        Write-Host "Trust Center wieder auf den vorherigen Stand gesetzt." -ForegroundColor Green
        $script:gesetzteSchluessel = @()
    }
}

$excel = New-Object -ComObject Excel.Application
$excel.Visible = $false
$excel.DisplayAlerts = $false

try {
    $wb = $excel.Workbooks.Add()

    try {
        $null = $wb.VBProject.Name
    } catch {
        throw ("Kein Zugriff auf das VBA-Projekt, obwohl der Trust-Center-" +
            "Schalter gesetzt wurde. Moeglich ist eine Gruppenrichtlinie, die " +
            "ihn erzwingt. Dann hilft nur der manuelle Import laut " +
            "docs/EXCEL_SETUP.md (Weg B, ca. 5 Minuten).")
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
    # Muss auch dann laufen, wenn der Bau oben gescheitert ist.
    Restore-TrustCenter
}
