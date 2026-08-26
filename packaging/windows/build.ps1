# =====================================================================
# build.ps1 - reproduzierbarer Windows-x64-Build der portablen Core-EXE
# Voraussetzungen: Windows 11 x64, Python 3.12+ (nur auf dem BUILD-Rechner;
# Zielrechner brauchen kein Python), Internet nur fuer diesen Build-Schritt.
# Ergebnis: dist\lims_core\ (onedir) + hashes.json Manifest
# Aufruf:  powershell -ExecutionPolicy Bypass -File packaging\windows\build.ps1
# =====================================================================

$ErrorActionPreference = "Stop"
$repo = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location $repo

Write-Host "== 1/5 Virtuelle Build-Umgebung" -ForegroundColor Cyan
if (-not (Test-Path ".venv-build")) {
    python -m venv .venv-build
}
$py = Join-Path $repo ".venv-build\Scripts\python.exe"
& $py -m pip install --upgrade pip | Out-Null

Write-Host "== 2/5 Abhaengigkeiten (inkl. OCR) installieren" -ForegroundColor Cyan
# Gegen exakte Versionen aufloesen, damit zwei Builds dieselbe EXE ergeben.
$constraints = Join-Path $repo "packaging\windows\constraints-windows-x64.txt"
& $py -m pip install -c $constraints -e ".[ocr]" pyinstaller

Write-Host "== 3/5 Tests (Kern) auf dem Build-Rechner" -ForegroundColor Cyan
& $py -m pip install -c $constraints -e ".[dev]"
& $py -m pytest core/tests -q
if ($LASTEXITCODE -ne 0) { throw "Tests fehlgeschlagen - Build abgebrochen." }

Write-Host "== 4/5 PyInstaller onedir" -ForegroundColor Cyan
& $py -m PyInstaller --clean --noconfirm packaging\windows\lims_core.spec
if ($LASTEXITCODE -ne 0) { throw "PyInstaller fehlgeschlagen." }

Write-Host "== 5/5 Smoke-Test + Hash-Manifest" -ForegroundColor Cyan
$exe = Join-Path $repo "dist\lims_core\lims_core.exe"
& $exe health | Out-String | Write-Host
if ($LASTEXITCODE -ne 0) { throw "EXE-Smoke-Test (health) fehlgeschlagen." }

# Hash-Manifest ueber alle Paketdateien (Startpruefung im Betrieb)
$distDir = Join-Path $repo "dist\lims_core"
$manifest = @{}
Get-ChildItem -Path $distDir -Recurse -File | ForEach-Object {
    $rel = $_.FullName.Substring($distDir.Length + 1) -replace "\\", "/"
    $manifest[$rel] = (Get-FileHash -Algorithm SHA256 -Path $_.FullName).Hash.ToLower()
}
$manifest | ConvertTo-Json -Depth 3 | Set-Content -Encoding UTF8 (Join-Path $distDir "hashes.json")
Write-Host ("Manifest: {0} Dateien" -f $manifest.Count)

Write-Host ""
Write-Host "Fertig: dist\lims_core\  -> in den gemeinsamen Ordner unter '\core\' kopieren." -ForegroundColor Green
Write-Host "Danach: packaging\windows\provision_offline.ps1 fuer OCR-Latin-Modell/LLM ausfuehren."
