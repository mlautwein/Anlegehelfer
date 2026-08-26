# =====================================================================
# einrichten.ps1 - richtet den gemeinsamen Ordner fuer den taeglichen
# Betrieb ein: Paket entpacken, Hashes pruefen, config.json schreiben,
# Selbsttest fahren. Nimmt alles ab ausser der Excel-Mappe (die braucht
# Excel selbst - siehe Hinweis am Ende der Ausgabe).
#
# Voraussetzungen: Windows 11 x64. Python wird NICHT gebraucht.
#
# Aufruf (neueste Vorabversion aus GitHub laden):
#   powershell -ExecutionPolicy Bypass -File einrichten.ps1 -Ziel "C:\LIMS-PA"
#
# Aufruf mit bereits heruntergeladenem ZIP (z. B. ohne Internet am Zielrechner):
#   powershell -ExecutionPolicy Bypass -File einrichten.ps1 -Ziel "C:\LIMS-PA" -Paket "D:\lims_core-0.1.0-windows-x64.zip"
# =====================================================================

[CmdletBinding()]
param(
    # Gemeinsamer Ordner, in dem gearbeitet wird (wird angelegt, falls noetig).
    [Parameter(Mandatory = $true)]
    [string]$Ziel,

    # Bereits vorliegendes Release-ZIP. Ohne Angabe wird heruntergeladen.
    [string]$Paket = "",

    # Releasetag, falls nicht die neueste Version gewuenscht ist.
    [string]$Version = "",

    # Vorhandenes core\ und config.json ueberschreiben.
    [switch]$Ueberschreiben
)

$ErrorActionPreference = "Stop"
$repoSlug = "mlautwein/Anlegehelfer"

function Schritt([string]$Text) { Write-Host "== $Text" -ForegroundColor Cyan }
function Gut([string]$Text) { Write-Host "   $Text" -ForegroundColor Green }
function Warnung([string]$Text) { Write-Host "   $Text" -ForegroundColor Yellow }

# ---------------------------------------------------------------------
Schritt "1/6 Zielordner"
$Ziel = [System.IO.Path]::GetFullPath($Ziel)
if (-not (Test-Path $Ziel)) {
    New-Item -ItemType Directory -Path $Ziel -Force | Out-Null
    Gut "angelegt: $Ziel"
} else {
    Gut "vorhanden: $Ziel"
}
$coreDir = Join-Path $Ziel "core"
if ((Test-Path $coreDir) -and -not $Ueberschreiben) {
    throw "core\ existiert bereits in '$Ziel'. Mit -Ueberschreiben erneut einrichten."
}

# ---------------------------------------------------------------------
Schritt "2/6 Paket bereitstellen"
$tempDir = Join-Path ([System.IO.Path]::GetTempPath()) ("lims-setup-" + [guid]::NewGuid())
New-Item -ItemType Directory -Path $tempDir -Force | Out-Null
try {
    if ($Paket) {
        if (-not (Test-Path $Paket)) { throw "Paket nicht gefunden: $Paket" }
        $zip = (Resolve-Path $Paket).Path
        Gut "lokales Paket: $zip"
        $pruefsummenDatei = "$zip.sha256"
    } else {
        # Ohne gh-CLI auskommen: Release-Metadaten ueber die oeffentliche API.
        $api = if ($Version) {
            "https://api.github.com/repos/$repoSlug/releases/tags/$Version"
        } else {
            "https://api.github.com/repos/$repoSlug/releases"
        }
        Gut "frage GitHub nach dem Release ..."
        $meta = Invoke-RestMethod -Uri $api -Headers @{ "User-Agent" = "lims-einrichten" }
        if (-not $Version) { $meta = @($meta)[0] }   # neueste, inkl. Vorabversionen
        if (-not $meta) { throw "Kein Release gefunden (Repository privat oder Tag falsch?)." }
        Gut "Release: $($meta.tag_name)"

        $asset = $meta.assets | Where-Object { $_.name -like "lims_core-*-windows-x64.zip" } | Select-Object -First 1
        $assetHash = $meta.assets | Where-Object { $_.name -like "*.zip.sha256" } | Select-Object -First 1
        if (-not $asset) { throw "Im Release $($meta.tag_name) liegt kein Windows-Paket." }

        $zip = Join-Path $tempDir $asset.name
        Gut "lade $($asset.name) ($([math]::Round($asset.size / 1MB)) MB) ..."
        Invoke-WebRequest -Uri $asset.browser_download_url -OutFile $zip
        $pruefsummenDatei = ""
        if ($assetHash) {
            $pruefsummenDatei = Join-Path $tempDir $assetHash.name
            Invoke-WebRequest -Uri $assetHash.browser_download_url -OutFile $pruefsummenDatei
        }
    }

    # -----------------------------------------------------------------
    Schritt "3/6 Pruefsumme"
    if ($pruefsummenDatei -and (Test-Path $pruefsummenDatei)) {
        $soll = ((Get-Content $pruefsummenDatei -Raw).Trim() -split '\s+')[0].ToLower()
        $ist = (Get-FileHash -Algorithm SHA256 -Path $zip).Hash.ToLower()
        if ($soll -ne $ist) {
            throw "SHA-256 stimmt nicht. Erwartet $soll, berechnet $ist. Paket NICHT verwenden."
        }
        Gut "SHA-256 geprueft: $ist"
    } else {
        Warnung "Keine .sha256-Datei vorhanden - Pruefsumme uebersprungen."
    }

    # -----------------------------------------------------------------
    Schritt "4/6 Entpacken"
    if (Test-Path $coreDir) { Remove-Item $coreDir -Recurse -Force }
    Expand-Archive -Path $zip -DestinationPath $coreDir -Force
    $exe = Join-Path $coreDir "lims_core.exe"
    if (-not (Test-Path $exe)) { throw "lims_core.exe fehlt im Paket - Paket beschaedigt?" }
    Gut "entpackt nach: $coreDir"

    # Mitgeliefertes Hash-Manifest gegenpruefen (erkennt Uebertragungsfehler).
    $manifestPfad = Join-Path $coreDir "hashes.json"
    if (Test-Path $manifestPfad) {
        $manifest = Get-Content $manifestPfad -Raw | ConvertFrom-Json
        $abweichungen = 0
        foreach ($eintrag in $manifest.PSObject.Properties) {
            if ($eintrag.Name -eq "hashes.json") { continue }
            $datei = Join-Path $coreDir ($eintrag.Name -replace "/", "\")
            if (-not (Test-Path $datei)) { $abweichungen++; continue }
            if ((Get-FileHash -Algorithm SHA256 -Path $datei).Hash.ToLower() -ne $eintrag.Value) {
                $abweichungen++
            }
        }
        if ($abweichungen -gt 0) { throw "$abweichungen Dateien weichen vom Hash-Manifest ab." }
        Gut "Hash-Manifest: alle Dateien unveraendert"
    }
} finally {
    if (Test-Path $tempDir) { Remove-Item $tempDir -Recurse -Force -ErrorAction SilentlyContinue }
}

# ---------------------------------------------------------------------
Schritt "5/6 config.json"
$configPfad = Join-Path $Ziel "config.json"
if ((Test-Path $configPfad) -and -not $Ueberschreiben) {
    Gut "vorhanden, bleibt unveraendert: $configPfad"
} else {
    $config = [ordered]@{
        '$comment'              = "Erzeugt von einrichten.ps1. ocr.rec_model_path zeigt auf das Latin-Modell; solange es fehlt, arbeitet die OCR mit den gebuendelten Standardmodellen (deutsche Umlaute werden dann per Fuzzy repariert und gelb markiert). Nachruesten: provision_offline.ps1 -Step model"
        share_dir               = $Ziel
        core_exe                = "core/lims_core.exe"
        job_root                = ""
        certainty_threshold     = 0.75
        retrieval_min_similarity = 0.42
        retrieval_top_k         = 5
        offline_strict          = $true
        export_encoding         = "utf8_bom"
        stale_lock_minutes      = 12
        ocr                     = [ordered]@{
            engine         = "auto"
            rec_model_path = "core/models/ocr/latin_PP-OCRv3_rec_infer.onnx"
            dict_path      = "core/models/ocr/latin_dict.txt"
            render_dpi     = 170
            min_confidence = 0.55
        }
        llm                     = [ordered]@{
            enabled          = $false
            model_path       = ""
            model_sha256     = ""
            server_binary    = ""
            port             = 18081
            ctx_size         = 4096
            threads          = 0
            timeout_s        = 120
            max_rows_per_call = 12
        }
    }
    $config | ConvertTo-Json -Depth 5 | Set-Content -Encoding UTF8 $configPfad
    Gut "geschrieben: $configPfad"
}

# ---------------------------------------------------------------------
Schritt "6/6 Selbsttest"
$exe = Join-Path $coreDir "lims_core.exe"
& $exe --version
if ($LASTEXITCODE -ne 0) { throw "lims_core.exe --version fehlgeschlagen." }

$roh = & $exe --config $configPfad health | Out-String
if ($LASTEXITCODE -ne 0) { throw "Selbstauskunft (health) fehlgeschlagen." }
$health = $roh | ConvertFrom-Json
if (-not $health.ok) { throw "Selbstauskunft meldet einen Fehler." }
Gut "Kern antwortet, Version $($health.result.app_version)"
Gut "OCR: $($health.result.ocr.engine) - $($health.result.ocr.detail)"
if (-not $health.result.ocr.available) {
    Warnung "OCR steht NICHT zur Verfuegung - gescannte PDFs und Fotos liefern keine Zeilen."
}

Write-Host ""
Write-Host "Einrichtung fertig." -ForegroundColor Green
Write-Host "Ordner: $Ziel"
Write-Host ""
Write-Host "Es fehlt noch die Excel-Mappe - dafuer wird Excel selbst gebraucht:" -ForegroundColor Yellow
Write-Host "  powershell -ExecutionPolicy Bypass -File packaging\windows\build_workbook.ps1"
Write-Host "  (oder in 5 Minuten von Hand: docs\EXCEL_SETUP.md, Weg B)"
Write-Host "Die fertige LIMS-Probenassistent.xlsm gehoert direkt nach $Ziel."
Write-Host ""
Write-Host "Optional fuer bessere deutsche Umlaute in Scans:" -ForegroundColor Yellow
Write-Host "  powershell -ExecutionPolicy Bypass -File packaging\windows\provision_offline.ps1 -Step model"
Write-Host ""
Write-Host "Danach: docs\ERSTE_SCHRITTE.md ab Schritt 4."
