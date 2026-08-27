# =====================================================================
# einrichten.ps1 - richtet den Arbeitsordner in einem Durchgang ein:
# Paket holen und pruefen, entpacken, config.json schreiben, Arbeitsmappe
# bauen, Verknuepfung anlegen, Selbsttest fahren.
#
# Einfachster Weg: Installieren.cmd doppelklicken. Dann sind keine
# Kommandozeilenkenntnisse noetig.
#
# Voraussetzungen: Windows 11 x64. Python wird NICHT gebraucht. Excel nur
# fuer die Arbeitsmappe - fehlt es, laeuft alles andere trotzdem durch.
#
# Aufrufbeispiele:
#   powershell -ExecutionPolicy Bypass -File einrichten.ps1 -Interaktiv
#   powershell -ExecutionPolicy Bypass -File einrichten.ps1 -Ziel "S:\Freigabe\LIMS"
#
# Liegt ein Ordner core\ neben diesem Skript (Normalfall im Setup-Archiv),
# wird dieser benutzt - die Installation braucht dann kein Internet.
# =====================================================================

[CmdletBinding()]
param(
    # Arbeitsordner. Ohne Angabe: C:\LIMS-Probenassistent.
    [string]$Ziel = "",

    # Release-ZIP. Ohne Angabe: mitgeliefertes core\, sonst Download.
    [string]$Paket = "",

    # Releasetag, falls nicht die neueste Version gewuenscht ist.
    [string]$Version = "",

    # Nachfragen statt Abbrechen (setzt Installieren.cmd).
    [switch]$Interaktiv,

    # Vorhandenes core\ und config.json ueberschreiben.
    [switch]$Ueberschreiben,

    # Arbeitsmappe nicht bauen (z. B. auf Rechnern ohne Excel).
    [switch]$OhneMappe,

    # Vorhandene config.json verwerfen und neu schreiben.
    [switch]$ConfigNeuSchreiben
)

$ErrorActionPreference = "Stop"
$repoSlug = "mlautwein/Anlegehelfer"
$standardZiel = "C:\LIMS-Probenassistent"

function Schritt([string]$Text) { Write-Host "== $Text" -ForegroundColor Cyan }
function Gut([string]$Text) { Write-Host "   $Text" -ForegroundColor Green }
function Warnung([string]$Text) { Write-Host "   $Text" -ForegroundColor Yellow }

$offenePunkte = New-Object System.Collections.Generic.List[string]

if ($Interaktiv) {
    Write-Host ""
    Write-Host "  LIMS-Probenassistent einrichten" -ForegroundColor White
    Write-Host "  -------------------------------"
    Write-Host "  Es wird nichts ausserhalb des gewaehlten Ordners veraendert."
    Write-Host ""
}

# ---------------------------------------------------------------------
Schritt "1/7 Arbeitsordner"
# Bewusst ohne Rueckfrage: Der Normalfall soll ohne jede Eingabe
# durchlaufen. Wer einen gemeinsamen Ordner braucht, gibt -Ziel an.
if (-not $Ziel) { $Ziel = $standardZiel }
$Ziel = [System.IO.Path]::GetFullPath($Ziel)
if (-not (Test-Path $Ziel)) {
    try {
        New-Item -ItemType Directory -Path $Ziel -Force -ErrorAction Stop | Out-Null
        Gut "angelegt: $Ziel"
    } catch {
        # Ohne Administratorrechte ist C:\ oft gesperrt - dann ins Profil.
        $Ziel = Join-Path $env:LOCALAPPDATA "LIMS-Probenassistent"
        New-Item -ItemType Directory -Path $Ziel -Force | Out-Null
        Warnung "C:\ war nicht beschreibbar, nehme stattdessen:"
        Gut "angelegt: $Ziel"
    }
} else {
    Gut "vorhanden: $Ziel"
}

$coreDir = Join-Path $Ziel "core"
if ((Test-Path $coreDir) -and -not $Ueberschreiben) {
    if ($Interaktiv) {
        # Aktualisieren ist der Normalfall - config.json und die gelernten
        # Daten bleiben dabei ohnehin erhalten, erneuert wird nur core\.
        Gut "bereits eingerichtet - Rechenkern wird aktualisiert"
        $Ueberschreiben = $true
    } else {
        throw "core\ existiert bereits in '$Ziel'. Mit -Ueberschreiben erneut einrichten."
    }
}

# ---------------------------------------------------------------------
Schritt "2/7 Paket bereitstellen"
$tempDir = Join-Path ([System.IO.Path]::GetTempPath()) ("lims-setup-" + [guid]::NewGuid())
New-Item -ItemType Directory -Path $tempDir -Force | Out-Null
$pruefsummenDatei = ""
$nachPruefung = $false
try {
    $mitgeliefert = Join-Path $PSScriptRoot "core\lims_core.exe"
    if (-not $Paket -and (Test-Path $mitgeliefert)) {
        # Normalfall: Der Rechenkern liegt im entpackten Setup-Ordner.
        # Dann wird nichts heruntergeladen - die Installation braucht kein
        # Internet und funktioniert auch in abgeschotteten Netzen.
        $zip = ""
        $quellOrdner = Split-Path $mitgeliefert -Parent
        Gut "Rechenkern liegt bei, kein Download noetig"
    } elseif ($Paket) {
        if (-not (Test-Path $Paket)) { throw "Paket nicht gefunden: $Paket" }
        $zip = (Resolve-Path $Paket).Path
        $quellOrdner = ""
        Gut "lokales Paket: $zip"
        $pruefsummenDatei = "$zip.sha256"
    } else {
        $quellOrdner = ""
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

        $asset = $meta.assets | Where-Object { $_.name -like "*Setup-Windows.zip" } | Select-Object -First 1
        $assetHash = $meta.assets | Where-Object { $_.name -like "*Setup-Windows.zip.sha256" } | Select-Object -First 1
        if (-not $asset) { throw "Im Release $($meta.tag_name) liegt kein Setup-Archiv." }

        $zip = Join-Path $tempDir $asset.name
        Gut "lade $($asset.name) ($([math]::Round($asset.size / 1MB)) MB) ..."
        Invoke-WebRequest -Uri $asset.browser_download_url -OutFile $zip
        if ($assetHash) {
            $pruefsummenDatei = Join-Path $tempDir $assetHash.name
            Invoke-WebRequest -Uri $assetHash.browser_download_url -OutFile $pruefsummenDatei
        }
        # Im Setup-Archiv steckt der Rechenkern in core\ - nach der
        # Pruefsummenkontrolle weiter unten wird daraus $quellOrdner.
        $entpackt = Join-Path $tempDir "entpackt"
        $nachPruefung = $true
    }

    # -----------------------------------------------------------------
    Schritt "3/7 Pruefsumme"
    if ($quellOrdner) {
        Gut "entfaellt - Integritaet wird unten am Hash-Manifest geprueft"
    } elseif ($pruefsummenDatei -and (Test-Path $pruefsummenDatei)) {
        $soll = ((Get-Content $pruefsummenDatei -Raw).Trim() -split '\s+')[0].ToLower()
        $ist = (Get-FileHash -Algorithm SHA256 -Path $zip).Hash.ToLower()
        if ($soll -ne $ist) {
            throw "SHA-256 stimmt nicht. Erwartet $soll, berechnet $ist. Paket NICHT verwenden."
        }
        Gut "SHA-256 geprueft"
    } else {
        Warnung "Keine .sha256-Datei vorhanden - Pruefsumme uebersprungen."
    }

    # -----------------------------------------------------------------
    Schritt "4/7 Rechenkern bereitstellen"
    if ($nachPruefung) {
        Expand-Archive -Path $zip -DestinationPath $entpackt -Force
        $quellOrdner = Join-Path $entpackt "core"
        if (-not (Test-Path (Join-Path $quellOrdner "lims_core.exe"))) {
            throw "Im Setup-Archiv fehlt core\lims_core.exe."
        }
    }
    if (Test-Path $coreDir) { Remove-Item $coreDir -Recurse -Force }
    if ($quellOrdner) {
        Copy-Item -Path $quellOrdner -Destination $coreDir -Recurse -Force
        Gut "kopiert nach: $coreDir"
    } else {
        Expand-Archive -Path $zip -DestinationPath $coreDir -Force
        Gut "entpackt nach: $coreDir"
    }
    $exe = Join-Path $coreDir "lims_core.exe"
    if (-not (Test-Path $exe)) { throw "lims_core.exe fehlt - Paket unvollstaendig?" }

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
Schritt "5/7 config.json"
$configPfad = Join-Path $Ziel "config.json"
# Bewusst auch bei -Ueberschreiben stehenlassen: Bei einer Aktualisierung
# soll eine angepasste Konfiguration (z. B. ein gemeinsamer Ordner) nicht
# stillschweigend verlorengehen. Erzwingen laesst sich das mit
# -ConfigNeuSchreiben.
if ((Test-Path $configPfad) -and -not $ConfigNeuSchreiben) {
    Gut "vorhanden, bleibt unveraendert (mit -ConfigNeuSchreiben erneuern)"
} else {
    $config = [ordered]@{
        '$comment'               = "Erzeugt von einrichten.ps1. ocr.rec_model_path zeigt auf das Latin-Modell; solange es fehlt, arbeitet die OCR mit den gebuendelten Standardmodellen (deutsche Umlaute werden dann per Fuzzy repariert und gelb markiert). Nachruesten: provision_offline.ps1 -Step model"
        share_dir                = $Ziel
        core_exe                 = "core/lims_core.exe"
        job_root                 = ""
        certainty_threshold      = 0.75
        retrieval_min_similarity = 0.42
        retrieval_top_k          = 5
        offline_strict           = $true
        export_encoding          = "utf8_bom"
        stale_lock_minutes       = 12
        ocr                      = [ordered]@{
            engine         = "auto"
            rec_model_path = "core/models/ocr/latin_PP-OCRv3_rec_infer.onnx"
            dict_path      = "core/models/ocr/latin_dict.txt"
            render_dpi     = 170
            min_confidence = 0.55
        }
        llm                      = [ordered]@{
            enabled           = $false
            model_path        = ""
            model_sha256      = ""
            server_binary     = ""
            port              = 18081
            ctx_size          = 4096
            threads           = 0
            timeout_s         = 120
            max_rows_per_call = 12
        }
    }
    $config | ConvertTo-Json -Depth 5 | Set-Content -Encoding UTF8 $configPfad
    Gut "geschrieben: $configPfad"
}

# ---------------------------------------------------------------------
Schritt "6/7 Arbeitsmappe"
$mappe = Join-Path $Ziel "LIMS-Probenassistent.xlsm"
$bauSkript = Join-Path $PSScriptRoot "build_workbook.ps1"

if ($OhneMappe) {
    Warnung "uebersprungen (-OhneMappe)"
    $offenePunkte.Add("Arbeitsmappe erzeugen: build_workbook.ps1 oder docs\EXCEL_SETUP.md")
} elseif ((Test-Path $mappe) -and -not $Ueberschreiben) {
    Gut "vorhanden, bleibt unveraendert"
} elseif (-not (Test-Path $bauSkript)) {
    Warnung "build_workbook.ps1 liegt nicht neben diesem Skript - uebersprungen."
    $offenePunkte.Add("Arbeitsmappe erzeugen: siehe docs\EXCEL_SETUP.md")
} else {
    # Erst pruefen, ob Excel ueberhaupt da ist - sonst waere die
    # Fehlermeldung der COM-Automation fuer Anwender unverstaendlich.
    $excelDa = $false
    try {
        $probe = New-Object -ComObject Excel.Application
        $probe.Quit()
        [System.Runtime.InteropServices.Marshal]::ReleaseComObject($probe) | Out-Null
        $excelDa = $true
    } catch {
        $excelDa = $false
    }

    if (-not $excelDa) {
        Warnung "Excel ist auf diesem Rechner nicht verfuegbar."
        Warnung "Die Mappe muss auf einem Rechner mit Excel erzeugt werden."
        $offenePunkte.Add("Arbeitsmappe auf einem Rechner mit Excel erzeugen (docs\ERSTE_SCHRITTE.md, Schritt 2)")
    } else {
        Gut "Excel gefunden, erzeuge Arbeitsmappe ..."
        try {
            # $LASTEXITCODE gilt nur fuer native Programme; ein Skriptaufruf
            # meldet Fehler ueber Ausnahmen ($ErrorActionPreference = Stop).
            & $bauSkript -Ziel $mappe
            if (-not (Test-Path $mappe)) { throw "Die Mappe wurde nicht erzeugt." }
            Gut "erzeugt: $mappe"
        } catch {
            Warnung "Die Mappe konnte nicht automatisch erzeugt werden:"
            Warnung "  $($_.Exception.Message)"
            Warnung "Der noetige Trust-Center-Schalter wird eigentlich automatisch"
            Warnung "gesetzt und danach zurueckgenommen. Schlaegt das fehl, sperrt"
            Warnung "ihn meist eine Gruppenrichtlinie der IT."
            $offenePunkte.Add("Arbeitsmappe von Hand erzeugen: docs\EXCEL_SETUP.md, Weg B (ca. 5 Minuten)")
        }
    }
}

# Verknuepfung auf dem Desktop, damit der taegliche Start ein Klick ist.
if (Test-Path $mappe) {
    try {
        $desktop = [Environment]::GetFolderPath("Desktop")
        $lnk = Join-Path $desktop "LIMS-Probenassistent.lnk"
        $shell = New-Object -ComObject WScript.Shell
        $verknuepfung = $shell.CreateShortcut($lnk)
        $verknuepfung.TargetPath = $mappe
        $verknuepfung.WorkingDirectory = $Ziel
        $verknuepfung.Description = "LIMS-Probenassistent oeffnen"
        $verknuepfung.Save()
        [System.Runtime.InteropServices.Marshal]::ReleaseComObject($shell) | Out-Null
        Gut "Verknuepfung auf dem Desktop angelegt"
    } catch {
        Warnung "Desktop-Verknuepfung nicht moeglich: $($_.Exception.Message)"
    }
}

# ---------------------------------------------------------------------
Schritt "7/7 Selbsttest"
$exe = Join-Path $coreDir "lims_core.exe"
& $exe --version | Out-Null
if ($LASTEXITCODE -ne 0) { throw "lims_core.exe --version fehlgeschlagen." }

$roh = & $exe --config $configPfad health | Out-String
if ($LASTEXITCODE -ne 0) { throw "Selbstauskunft (health) fehlgeschlagen." }
$health = $roh | ConvertFrom-Json
if (-not $health.ok) { throw "Selbstauskunft meldet einen Fehler." }
Gut "Kern antwortet, Version $($health.result.app_version)"
Gut "OCR: $($health.result.ocr.engine)"
if (-not $health.result.ocr.available) {
    Warnung "OCR steht NICHT zur Verfuegung - Scans und Fotos liefern keine Zeilen."
    $offenePunkte.Add("OCR pruefen: lims_core.exe --config config.json health")
} elseif ($health.result.ocr.detail -notmatch "latin") {
    $offenePunkte.Add("Optional fuer saubere deutsche Umlaute in Scans: provision_offline.ps1 -Step model")
}

# ---------------------------------------------------------------------
Write-Host ""
if (Test-Path $mappe) {
    Write-Host "Fertig - der Probenassistent ist einsatzbereit." -ForegroundColor Green
    Write-Host ""
    Write-Host "Zum Starten: Verknuepfung 'LIMS-Probenassistent' auf dem Desktop"
    Write-Host "oder $mappe"
    Write-Host "Beim Oeffnen fragt Excel nach Makros - diese zulassen."
} else {
    Write-Host "Der Rechenkern ist eingerichtet, die Arbeitsmappe fehlt noch." -ForegroundColor Yellow
    Write-Host "Ordner: $Ziel"
}

if ($offenePunkte.Count -gt 0) {
    Write-Host ""
    Write-Host "Offen:" -ForegroundColor Yellow
    foreach ($punkt in $offenePunkte) { Write-Host "  - $punkt" }
}
Write-Host ""
Write-Host "Bedienung: docs\BEDIENUNG.md   Einrichtung im Detail: docs\ERSTE_SCHRITTE.md"
