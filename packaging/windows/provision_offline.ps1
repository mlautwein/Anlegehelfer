# =====================================================================
# provision_offline.ps1 - laedt Begleitartefakte VOR der Offline-
# Bereitstellung (einmalig, auf einem Rechner mit Internet):
#   1) OCR-Latin-Modell (deutsche Umlaute) fuer RapidOCR
#   2) llama.cpp llama-server (Windows x64) - gepinntes Release
#   3) LLM-GGUF-Kandidaten fuer den Benchmark
# Jede Datei wird per SHA-256 gehasht; die Hashes werden in
# packaging/models/manifest.json eingetragen (BEIM_PROVISIONIEREN_...).
# Zur Laufzeit findet KEIN Download statt.
#
# Aufruf-Beispiele:
#   powershell -File provision_offline.ps1 -Step ocr
#   powershell -File provision_offline.ps1 -Step llama -LlamaUrl "https://github.com/ggml-org/llama.cpp/releases/download/bXXXX/llama-bXXXX-bin-win-avx2-x64.zip"
#   powershell -File provision_offline.ps1 -Step model -ModelUrl "<GGUF-URL Qwen3-4B-Instruct-2507 Q4_K_M>"
# =====================================================================

param(
    [Parameter(Mandatory = $true)][ValidateSet("ocr", "llama", "model", "hash")] [string]$Step,
    [string]$LlamaUrl = "",
    [string]$ModelUrl = "",
    [string]$OcrRecUrl = "",
    [string]$OcrDictUrl = "",
    [string]$Target = ""
)

$ErrorActionPreference = "Stop"
$repo = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$coreDir = Join-Path $repo "dist\lims_core"

function Get-Sha256([string]$Path) {
    (Get-FileHash -Algorithm SHA256 -Path $Path).Hash.ToLower()
}

function Download([string]$Url, [string]$Dest) {
    Write-Host ("Lade {0}" -f $Url)
    Invoke-WebRequest -Uri $Url -OutFile $Dest -UseBasicParsing
    Write-Host ("  -> {0}  SHA256={1}" -f $Dest, (Get-Sha256 $Dest)) -ForegroundColor Green
}

switch ($Step) {
    "ocr" {
        if (-not $OcrRecUrl) {
            Write-Host "Bitte -OcrRecUrl (latin_PP-OCRv3_rec_infer.onnx) und -OcrDictUrl (latin_dict.txt) angeben."
            Write-Host "Quellen: RapidOCR-Modellzoo, siehe packaging/models/manifest.json"
            exit 1
        }
        $ocrDir = Join-Path $coreDir "models\ocr"
        New-Item -ItemType Directory -Force -Path $ocrDir | Out-Null
        Download $OcrRecUrl (Join-Path $ocrDir "latin_PP-OCRv3_rec_infer.onnx")
        if ($OcrDictUrl) { Download $OcrDictUrl (Join-Path $ocrDir "latin_dict.txt") }
        Write-Host "config.json ergaenzen:"
        Write-Host '  "ocr": {"rec_model_path": "core/models/ocr/latin_PP-OCRv3_rec_infer.onnx", "dict_path": "core/models/ocr/latin_dict.txt"}'
    }
    "llama" {
        if (-not $LlamaUrl) { Write-Host "Bitte -LlamaUrl eines gepinnten llama.cpp-Windows-Releases angeben."; exit 1 }
        $llmDir = Join-Path $coreDir "llm"
        New-Item -ItemType Directory -Force -Path $llmDir | Out-Null
        $zip = Join-Path $env:TEMP "llama-release.zip"
        Download $LlamaUrl $zip
        Expand-Archive -Path $zip -DestinationPath $llmDir -Force
        Remove-Item $zip -Force
        Write-Host "config.json ergaenzen:"
        Write-Host '  "llm": {"enabled": true, "server_binary": "core/llm/llama-server.exe", "model_path": "...", "model_sha256": "..."}'
    }
    "model" {
        if (-not $ModelUrl) { Write-Host "Bitte -ModelUrl der GGUF-Datei angeben (siehe manifest.json Kandidaten)."; exit 1 }
        $modelsDir = Join-Path $coreDir "models\llm"
        New-Item -ItemType Directory -Force -Path $modelsDir | Out-Null
        $name = Split-Path $ModelUrl -Leaf
        Download $ModelUrl (Join-Path $modelsDir $name)
        Write-Host "SHA-256 in packaging/models/manifest.json eintragen und Benchmark ausfuehren:"
        Write-Host "  python scripts\benchmark_llm.py --model dist\lims_core\models\llm\$name"
    }
    "hash" {
        if (-not $Target) { Write-Host "Bitte -Target <Datei> angeben."; exit 1 }
        Write-Host ("SHA256({0}) = {1}" -f $Target, (Get-Sha256 $Target))
    }
}
